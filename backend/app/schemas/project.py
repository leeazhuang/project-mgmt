from pydantic import BaseModel
from typing import Optional


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    owner_id: int
    tech_leader_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    member_ids: list[int] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[int] = None
    tech_leader_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    member_ids: Optional[list[int]] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    status: str
    owner: dict
    tech_leader: dict
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    member_count: int
    created_at: str

    class Config:
        from_attributes = True


class ProjectMemberOut(BaseModel):
    id: int
    user_id: int
    username: str
    real_name: str
    joined_at: str


class AddMembersRequest(BaseModel):
    user_ids: list[int]
