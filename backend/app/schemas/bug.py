from pydantic import BaseModel
from typing import Optional


class BugCreate(BaseModel):
    project_id: int
    title: str
    description: str = ""
    severity: str = "minor"
    priority: str = "medium"
    environment: str = ""

    model_config = {"extra": "ignore"}


class BugUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None


class BugAssign(BaseModel):
    assignee_id: int
    # 分配时为该人选的展示标签快照，无标签则空
    display_tag: str = ""


class BugFixed(BaseModel):
    # Bug 完成时填写的出现原因（必填）
    reason: str = ""


class BugReject(BaseModel):
    reason: str


class BugVerify(BaseModel):
    passed: bool


class BugOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    status: str
    severity: str
    priority: str
    creator: dict
    assignee: Optional[dict] = None
    reject_reason: str
    created_at: str
    resolved_at: Optional[str] = None
    closed_at: Optional[str] = None

    class Config:
        from_attributes = True
