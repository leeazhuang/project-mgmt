from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    real_name: str


class UserInfo(BaseModel):
    id: int
    username: str
    real_name: str
    avatar: str
    roles: list[str]
    permissions: list[str]
    menus: list[dict]
    tag_only_view: bool = False  # 仅看分配标签角色：前端据此隐藏流转记录等

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    wx_room_id: str = ""
    wx_room_name: str = ""
    wx_user_id: str = ""
    wx_user_name: str = ""
    role_ids: list[int] = []
    display_tags: list[str] = []


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    wx_room_id: Optional[str] = None
    wx_room_name: Optional[str] = None
    wx_user_id: Optional[str] = None
    wx_user_name: Optional[str] = None
    is_enabled: Optional[int] = None
    role_ids: Optional[list[int]] = None
    display_tags: Optional[list[str]] = None


class UserListItem(BaseModel):
    id: int
    username: str
    real_name: str
    is_enabled: int
    created_at: str
    roles: list[dict]

    class Config:
        from_attributes = True
