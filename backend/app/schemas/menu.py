from pydantic import BaseModel
from typing import Optional


class MenuCreate(BaseModel):
    parent_id: int = 0
    name: str
    type: str
    path: str = ""
    component: str = ""
    permission_code: str = ""
    icon: str = ""
    sort_order: int = 0
    is_visible: int = 1


class MenuUpdate(BaseModel):
    parent_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    path: Optional[str] = None
    component: Optional[str] = None
    permission_code: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[int] = None
    is_enabled: Optional[int] = None


class MenuOut(BaseModel):
    id: int
    parent_id: int
    name: str
    type: str
    path: str
    component: str
    permission_code: str
    icon: str
    sort_order: int
    is_visible: int
    is_enabled: int
    children: list["MenuOut"] = []

    class Config:
        from_attributes = True
