from pydantic import BaseModel
from typing import Optional


class RequirementCreate(BaseModel):
    project_id: int
    title: str
    description: str = ""
    priority: str = "medium"
    deadline: Optional[str] = None


class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[str] = None


class ApprovalRequest(BaseModel):
    action: str
    remark: str = ""


class RequirementOut(BaseModel):
    id: int
    project_id: int
    project_name: str
    title: str
    description: str
    status: str
    priority: str
    creator: dict
    reject_reason: str
    deadline: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ApprovalLogOut(BaseModel):
    id: int
    operator: dict
    action: str
    remark: str
    created_at: str
