from pydantic import BaseModel
from typing import Optional


class TaskCreate(BaseModel):
    requirement_id: int
    title: str
    description: str = ""
    priority: str = "medium"
    assignee_ids: list[int] = []
    estimated_hours: float = 0
    planned_start_date: Optional[str] = None
    end_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_ids: Optional[list[int]] = None
    estimated_hours: Optional[float] = None
    planned_start_date: Optional[str] = None
    end_date: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    project_id: int
    requirement_id: int
    requirement_title: str
    title: str
    description: str
    status: str
    priority: str
    assignees: list[dict] = []
    assigner: dict
    estimated_hours: float
    actual_hours: float
    planned_start_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True
