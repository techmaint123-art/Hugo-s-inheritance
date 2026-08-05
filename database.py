from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# 支援本機 SQLite 與雲端 PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/leave_system.db")

# Render / Railway 等平台會提供 postgres://，需轉成 sqlalchemy 格式
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class LeaveType(Base):
    __tablename__ = "leave_types"

    type_id = Column(Integer, primary_key=True, index=True)
    type_code = Column(String(20), unique=True, nullable=False)
    type_name = Column(String(50), nullable=False)
    unit = Column(String(10), default="hour")  # hour / day
    is_paid = Column(Boolean, default=False)
    max_days_per_year = Column(Float, nullable=True)
    need_proof = Column(Boolean, default=False)
    description = Column(Text, nullable=True)

    requests = relationship("LeaveRequest", back_populates="leave_type")
    balances = relationship("LeaveBalance", back_populates="leave_type")


class Employee(Base):
    __tablename__ = "employees"

    emp_id = Column(Integer, primary_key=True, index=True)
    emp_no = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    department = Column(String(50), default="一般部門")
    hire_date = Column(String(20), default="2023-01-01")
    annual_leave_days = Column(Float, default=14.0)

    balances = relationship("LeaveBalance", back_populates="employee")
    requests = relationship("LeaveRequest", back_populates="employee")


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    balance_id = Column(Integer, primary_key=True, index=True)
    emp_id = Column(Integer, ForeignKey("employees.emp_id"))
    type_id = Column(Integer, ForeignKey("leave_types.type_id"))
    year = Column(Integer, default=2026)
    total_quota = Column(Float, default=0.0)
    used = Column(Float, default=0.0)
    remaining = Column(Float, default=0.0)

    employee = relationship("Employee", back_populates="balances")
    leave_type = relationship("LeaveType", back_populates="balances")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    request_id = Column(Integer, primary_key=True, index=True)
    emp_id = Column(Integer, ForeignKey("employees.emp_id"))
    type_id = Column(Integer, ForeignKey("leave_types.type_id"))
    start_datetime = Column(String(30), nullable=False)
    end_datetime = Column(String(30), nullable=False)
    total_hours = Column(Float, default=0.0)
    total_days = Column(Float, default=0.0)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    proof_file = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    approver_comment = Column(Text, nullable=True)

    employee = relationship("Employee", back_populates="requests")
    leave_type = relationship("LeaveType", back_populates="requests")


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(LeaveType).count() == 0:
        leave_types = [
            LeaveType(type_code="personal", type_name="Personal Leave", unit="hour", is_paid=False,
                      max_days_per_year=None, need_proof=False,
                      description="Personal affairs leave, unpaid, calculated in hours"),
            LeaveType(type_code="sick", type_name="Sick Leave", unit="hour", is_paid=True,
                      max_days_per_year=30.0, need_proof=True,
                      description="Sick leave, medical certificate required, max 30 days per year"),
            LeaveType(type_code="annual", type_name="Annual Leave", unit="day", is_paid=True,
                      max_days_per_year=None, need_proof=False,
                      description="Annual leave based on seniority, paid"),
            LeaveType(type_code="official", type_name="Official Leave", unit="day", is_paid=True,
                      max_days_per_year=None, need_proof=True,
                      description="Official or statutory leave, supporting documents required"),
            LeaveType(type_code="bereavement", type_name="Bereavement Leave", unit="day", is_paid=True,
                      max_days_per_year=15.0, need_proof=True,
                      description="Bereavement leave for deceased relatives, 3-15 days depending on relationship"),
        ]
        db.add_all(leave_types)
        db.commit()

    if db.query(Employee).count() == 0:
        employees = [
            Employee(emp_no="E001", name="王小明", department="研發部", hire_date="2022-03-15", annual_leave_days=14.0),
            Employee(emp_no="E002", name="李美華", department="人資部", hire_date="2021-07-01", annual_leave_days=15.0),
            Employee(emp_no="E003", name="陳大文", department="業務部", hire_date="2023-01-10", annual_leave_days=10.0),
        ]
        db.add_all(employees)
        db.commit()

        types = db.query(LeaveType).all()
        emps = db.query(Employee).all()
        for emp in emps:
            for t in types:
                quota = 999.0
                if t.type_code == "annual":
                    quota = emp.annual_leave_days
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

    db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
