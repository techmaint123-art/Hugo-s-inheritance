from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/leave_system.db")

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
    type_code = Column(String(30), unique=True, nullable=False)
    type_name = Column(String(50), nullable=False)
    unit = Column(String(10), default="hour")
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
    gender = Column(String(10), default="male")  # male / female
    department = Column(String(50), default="General")
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

    # Ensure all leave types exist (add missing ones)
    existing_codes = {t.type_code for t in db.query(LeaveType).all()}
    all_types = [
        ("personal", "Personal Leave", "hour", False, None, False,
         "Personal affairs leave, unpaid, calculated in hours"),
        ("sick", "Sick Leave", "hour", True, 30.0, True,
         "Sick leave, medical certificate required, max 30 days per year"),
        ("annual", "Annual Leave", "day", True, None, False,
         "Annual leave based on seniority, paid"),
        ("official", "Official Leave", "day", True, None, True,
         "Official or statutory leave, supporting documents required"),
        ("bereavement", "Bereavement Leave", "day", True, 15.0, True,
         "Bereavement leave for deceased relatives, 3-15 days depending on relationship"),
        ("business", "Business Leave", "day", True, None, True,
         "Business trip or company business leave, paid, supporting documents required"),
        ("errand", "Errand Leave", "hour", True, None, False,
         "Short errand / outdoor duty leave, paid, calculated in hours"),
        ("menstrual", "Menstrual Leave", "day", True, 12.0, False,
         "Menstrual leave for female employees, 1 day per month (half-pay), max 12 days/year"),
    ]
    for code, name, unit, paid, maxd, proof, desc in all_types:
        if code not in existing_codes:
            db.add(LeaveType(
                type_code=code, type_name=name, unit=unit, is_paid=paid,
                max_days_per_year=maxd, need_proof=proof, description=desc
            ))
    db.commit()

    if db.query(Employee).count() == 0:
        employees = [
            Employee(emp_no="E001", name="Wang Xiaoming", gender="male",
                     department="R&D", hire_date="2022-03-15", annual_leave_days=14.0),
            Employee(emp_no="E002", name="Li Meihua", gender="female",
                     department="HR", hire_date="2021-07-01", annual_leave_days=15.0),
            Employee(emp_no="E003", name="Chen Dawen", gender="male",
                     department="Sales", hire_date="2023-01-10", annual_leave_days=10.0),
        ]
        db.add_all(employees)
        db.commit()

        types = db.query(LeaveType).all()
        emps = db.query(Employee).all()
        for emp in emps:
            for t in types:
                # Menstrual leave only for female
                if t.type_code == "menstrual" and emp.gender != "female":
                    continue
                quota = 999.0
                if t.type_code == "annual":
                    quota = emp.annual_leave_days
                elif t.type_code == "sick":
                    quota = 30.0 * 8
                elif t.type_code == "bereavement":
                    quota = 15.0
                elif t.type_code == "menstrual":
                    quota = 12.0  # 1 day/month
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
