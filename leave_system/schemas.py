from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class LeaveTypeOut(BaseModel):
    type_id: int
    type_code: str
    type_name: str
    unit: str
    is_paid: bool
    max_days_per_year: Optional[float]
    need_proof: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class EmployeeOut(BaseModel):
    emp_id: int
    emp_no: str
    name: str
    department: str
    hire_date: str
    annual_leave_days: float

    class Config:
        from_attributes = True


class LeaveBalanceOut(BaseModel):
    balance_id: int
    emp_id: int
    type_id: int
    type_name: str
    unit: str
    year: int
    total_quota: float
    used: float
    remaining: float

    class Config:
        from_attributes = True


class LeaveRequestCreate(BaseModel):
    emp_id: int
    type_id: int
    start_datetime: str  # "2026-08-10 09:00"
    end_datetime: str
    total_hours: float = 0.0
    total_days: float = 0.0
    reason: Optional[str] = None


class LeaveRequestOut(BaseModel):
    request_id: int
    emp_id: int
    emp_name: str
    type_id: int
    type_name: str
    start_datetime: str
    end_datetime: str
    total_hours: float
    total_days: float
    reason: Optional[str]
    status: str
    created_at: Optional[datetime]
    approver_comment: Optional[str]

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    request_id: int
    action: str  # approve / reject
    comment: Optional[str] = None
