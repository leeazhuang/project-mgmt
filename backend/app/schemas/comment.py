from pydantic import BaseModel
from typing import Optional


class CommentCreate(BaseModel):
    target_id: int
    target_type: str
    content: str
    parent_id: Optional[int] = None
    mention_user_ids: Optional[list[int]] = []


class CommentOut(BaseModel):
    id: int
    target_id: int
    target_type: str
    user: dict
    content: str
    parent_id: Optional[int] = None
    created_at: str
    children: list["CommentOut"] = []

    class Config:
        from_attributes = True
