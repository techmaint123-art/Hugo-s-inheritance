from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import sys
import webbrowser
import threading
import time

from database import init_db, get_db, LeaveType, Employee, LeaveBalance, LeaveRequest
from schemas import LeaveRequestCreate, ApproveRequest, EmployeeCreate, EmployeeUpdate

app = FastAPI(title="Ansett Leave Apply System", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/api/employees")
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    exists = db.query(Employee).filter(Employee.emp_no == data.emp_no).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"Employee No. {data.emp_no} already exists")

    emp = Employee(
        emp_no=data.emp_no,
        name=data.name,
        department=data.department,
        hire_date=data.hire_date,
        annual_leave_days=data.annual_leave_days
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    types = db.query(LeaveType).all()
    for t in types:
        quota = 999.0
        if t.type_code == "annual":
            quota = data.annual_leave_days
        elif t.type_code == "sick":
            quota = 30.0 * 8
        elif t.type_code == "bereavement":
            quota = 15.0
        balance = LeaveBalance(
            emp_id=emp.emp_id, type_id=t.type_id, year=2026,
            total_quota=quota, used=0.0, remaining=quota
        )
        db.add(balance)
    db.commit()

    return {"message": f"Employee {data.name} added successfully", "emp_id": emp.emp_id, "emp_no": emp.emp_no, "name": emp.name}


@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.emp_id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if data.name is not None:
        emp.name = data.name
    if data.department is not None:
        emp.department = data.department
    if data.hire_date is not None:
        emp.hire_date = data.hire_date
    if data.annual_leave_days is not None:
        emp.annual_leave_days = data.annual_leave_days
        # 同步更新年假餘額總額
        annual_type = db.query(LeaveType).filter(LeaveType.type_code == "annual").first()
        if annual_type:
            bal = db.query(LeaveBalance).filter(
                LeaveBalance.emp_id == emp_id,
                LeaveBalance.type_id == annual_type.type_id,
                LeaveBalance.year == 2026
            ).first()
            if bal:
                bal.total_quota = data.annual_leave_days
                bal.remaining = max(0, data.annual_leave_days - bal.used)

    db.commit()
    return {"message": f"Employee {emp.name} updated successfully"}


@app.delete("/api/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.emp_id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # 檢查是否有待審或已核准的請假
    active_req = db.query(LeaveRequest).filter(
        LeaveRequest.emp_id == emp_id,
        LeaveRequest.status.in_(["pending", "approved"])
    ).first()
    if active_req:
        raise HTTPException(status_code=400, detail="This employee has active leave records and cannot be deleted.")

    # 刪除餘額
    db.query(LeaveBalance).filter(LeaveBalance.emp_id == emp_id).delete()
    # 刪除已取消/駁回的申請
    db.query(LeaveRequest).filter(LeaveRequest.emp_id == emp_id).delete()
    db.delete(emp)
    db.commit()
    return {"message": f"Employee {emp.name} deleted"}


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
            "balance_id": bal.balance_id, "emp_id": bal.emp_id, "type_id": bal.type_id,
            "type_name": ltype.type_name, "unit": ltype.unit, "year": bal.year,
            "total_quota": bal.total_quota, "used": bal.used, "remaining": bal.remaining
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
            "request_id": req.request_id, "emp_id": req.emp_id, "emp_name": emp.name,
            "type_id": req.type_id, "type_name": ltype.type_name,
            "start_datetime": req.start_datetime, "end_datetime": req.end_datetime,
            "total_hours": req.total_hours, "total_days": req.total_days,
            "reason": req.reason, "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "approver_comment": req.approver_comment
        })
    return result


@app.post("/api/requests")
def create_request(data: LeaveRequestCreate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.emp_id == data.emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    ltype = db.query(LeaveType).filter(LeaveType.type_id == data.type_id).first()
    if not ltype:
        raise HTTPException(status_code=404, detail="Leave type not found")
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.emp_id == data.emp_id, LeaveBalance.type_id == data.type_id, LeaveBalance.year == 2026
    ).first()
    if not balance:
        raise HTTPException(status_code=400, detail="Balance record not found")
    need = data.total_hours if ltype.unit == "hour" else data.total_days
    if balance.remaining < need and ltype.type_code not in ("personal", "official"):
        raise HTTPException(status_code=400, detail=f"Insufficient balance！目前剩餘 {balance.remaining}，申請需要 {need}")
    new_req = LeaveRequest(
        emp_id=data.emp_id, type_id=data.type_id,
        start_datetime=data.start_datetime, end_datetime=data.end_datetime,
        total_hours=data.total_hours, total_days=data.total_days,
        reason=data.reason, status="pending"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    return {"message": "Leave request submitted, pending approval", "request_id": new_req.request_id, "status": "pending"}


@app.post("/api/approve")
def approve_request(data: ApproveRequest, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.request_id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been processed")
    if data.action == "approve":
        req.status = "approved"
        balance = db.query(LeaveBalance).filter(
            LeaveBalance.emp_id == req.emp_id, LeaveBalance.type_id == req.type_id, LeaveBalance.year == 2026
        ).first()
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
    return {"message": f"申請已{'核准' if data.action == 'approve' else '駁回'}", "request_id": req.request_id, "status": req.status}


@app.delete("/api/requests/{request_id}")
def cancel_request(request_id: int, db: Session = Depends(get_db)):
    req = db.query(LeaveRequest).filter(LeaveRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")
    req.status = "cancelled"
    db.commit()
    return {"message": "Request cancelled"}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.2.0"}


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    if os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT"):
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        threading.Thread(target=open_browser, daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
