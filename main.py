from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
import os
import sys
import webbrowser
import threading
import time

from database import init_db, get_db, LeaveType, Employee, LeaveBalance, LeaveRequest
from schemas import LeaveRequestCreate, ApproveRequest

app = FastAPI(title="公司請假系統", version="2.0.0")

# 允許跨網域（多機同步必要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 支援 PyInstaller 打包後的路徑
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

static_path = os.path.join(base_path, "static")
templates_path = os.path.join(base_path, "templates")
os.makedirs(static_path, exist_ok=True)
os.makedirs(templates_path, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/leave-types")
def get_leave_types(db: Session = Depends(get_db)):
    return db.query(LeaveType).all()


@app.get("/api/employees")
def get_employees(db: Session = Depends(get_db)):
    return db.query(Employee).all()


@app.get("/api/balances/{emp_id}")
def get_balances(emp_id: int, db: Session = Depends(get_db)):
    balances = (
        db.query(LeaveBalance, LeaveType)
        .join(LeaveType, LeaveBalance.type_id == LeaveType.type_id)
        .filter(LeaveBalance.emp_id == emp_id, LeaveBalance.year == 2026)
        .all()
    )
    result = []
    for bal, ltype in balances:
        result.append({
            "balance_id": bal.balance_id,
            "emp_id": bal.emp_id,
            "type_id": bal.type_id,
            "type_name": ltype.type_name,
            "unit": ltype.unit,
            "year": bal.year,
            "total_quota": bal.total_quota,
            "used": bal.used,
            "remaining": bal.remaining
        })
    return result


@app.get("/api/requests")
def get_requests(emp_id: int = None, status: str = None, db: Session = Depends(get_db)):
    query = (
        db.query(LeaveRequest, Employee, LeaveType)
        .join(Employee, LeaveRequest.emp_id == Employee.emp_id)
        .join(LeaveType, LeaveRequest.type_id == LeaveType.type_id)
    )
    if emp_id:
        query = query.filter(LeaveRequest.emp_id == emp_id)
    if status:
        query = query.filter(LeaveRequest.status == status)

    rows = query.order_by(LeaveRequest.created_at.desc()).all()
    result = []
    for req, emp, ltype in rows:
        result.append({
            "request_id": req.request_id,
            "emp_id": req.emp_id,
            "emp_name": emp.name,
            "type_id": req.type_id,
            "type_name": ltype.type_name,
            "start_datetime": req.start_datetime,
            "end_datetime": req.end_datetime,
            "total_hours": req.total_hours,
            "total_days": req.total_days,
            "reason": req.reason,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "approver_comment": req.approver_comment
        })
    return result


@app.post("/api/requests")
def create_request(data: LeaveRequestCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.emp_id == data.emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="員工不存在")

    ltype = db.query(LeaveType).filter(LeaveType.type_id == data.type_id).first()
    if not ltype:
        raise HTTPException(status_code=404, detail="假別不存在")

    balance = (
        db.query(LeaveBalance)
        .filter(LeaveBalance.emp_id == data.emp_id,
                LeaveBalance.type_id == data.type_id,
                LeaveBalance.year == 2026)
        .first()
    )
    if not balance:
        raise HTTPException(status_code=400, detail="找不到對應餘額資料")

    need = data.total_hours if ltype.unit == "hour" else data.total_days
    if balance.remaining < need and ltype.type_code not in ("personal", "official"):
        raise HTTPException(status_code=400,
                            detail=f"餘額不足！目前剩餘 {balance.remaining}，申請需要 {need}")

    new_req = LeaveRequest(
        emp_id=data.emp_id, type_id=data.type_id,
        start_datetime=data.start_datetime, end_datetime=data.end_datetime,
        total_hours=data.total_hours, total_days=data.total_days,
        reason=data.reason, status="pending"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    return {"message": "請假申請已送出，等待審核", "request_id": new_req.request_id, "status": "pending"}


@app.post("/api/approve")
def approve_request(data: ApproveRequest, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.request_id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申請單不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="此申請已處理過")

    if data.action == "approve":
        req.status = "approved"
        balance = (
            db.query(LeaveBalance)
            .filter(LeaveBalance.emp_id == req.emp_id,
                    LeaveBalance.type_id == req.type_id,
                    LeaveBalance.year == 2026)
            .first()
        )
        if balance:
            ltype = db.query(LeaveType).filter(LeaveType.type_id == req.type_id).first()
            deduct = req.total_hours if ltype.unit == "hour" else req.total_days
            balance.used += deduct
            balance.remaining = max(0, balance.total_quota - balance.used)
    elif data.action == "reject":
        req.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="action 必須是 approve 或 reject")

    req.approver_comment = data.comment
    db.commit()
    return {"message": f"申請已{'核准' if data.action == 'approve' else '駁回'}",
            "request_id": req.request_id, "status": req.status}


@app.delete("/api/requests/{request_id}")
def cancel_request(request_id: int, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申請單不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="只能取消待審核的申請")
    req.status = "cancelled"
    db.commit()
    return {"message": "申請已取消"}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    if os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT"):
        # 雲端部署時不自動開瀏覽器
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        threading.Thread(target=open_browser, daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
