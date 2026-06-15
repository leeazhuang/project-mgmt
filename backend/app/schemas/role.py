from pydantic import BaseModel
from typing import Optional


class RoleCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    menu_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[int] = None
    menu_ids: Optional[list[int]] = None


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: str
    is_enabled: int
    menu_ids: list[int] = []

    class Config:
        from_attributes = True
