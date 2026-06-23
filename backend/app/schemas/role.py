from pydantic import BaseModel
from typing import Optional


class RoleCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    tag_only_view: int = 0
    menu_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[int] = None
    tag_only_view: Optional[int] = None
    menu_ids: Optional[list[int]] = None


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: str
    is_enabled: int
    tag_only_view: int = 0
    menu_ids: list[int] = []

    class Config:
        from_attributes = True
