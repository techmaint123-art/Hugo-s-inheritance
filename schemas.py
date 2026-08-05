from pydantic import BaseModel
from typing import Optional


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


class EmployeeCreate(BaseModel):
    emp_no: str
    name: str
    department: str = "一般部門"
    hire_date: str = "2024-01-01"
    annual_leave_days: float = 10.0


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[str] = None
    annual_leave_days: Optional[float] = None


class LeaveRequestCreate(BaseModel):
    emp_id: int
    type_id: int
    start_datetime: str
    end_datetime: str
    total_hours: float = 0.0
    total_days: float = 0.0
    reason: Optional[str] = None


class ApproveRequest(BaseModel):
    request_id: int
    action: str
    comment: Optional[str] = None
