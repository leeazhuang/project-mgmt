from pydantic import BaseModel
from typing import Optional


class RequirementCreate(BaseModel):
    project_id: int
    title: str
    description: str = ""
    priority: str = "medium"
    deadline: Optional[str] = None
    # 技术负责人新建需求时可一并直接建任务（全程不通知）
    estimated_deadline: Optional[str] = None       # 需求预计截止时间
    assignee_ids: Optional[list[int]] = None       # 任务指派人（提供则触发自动建任务）
    assignee_tags: Optional[dict[int, str]] = None  # 指派人对应展示标签快照
    estimated_hours: Optional[float] = None        # 任务预估工时
    task_end_date: Optional[str] = None            # 任务截止日期
    attachment_ids: Optional[list[int]] = None     # 需求附件ID（复制到任务）


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
