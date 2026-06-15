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


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    wx_room_id: Optional[str] = None
    wx_room_name: Optional[str] = None
    wx_user_id: Optional[str] = None
    wx_user_name: Optional[str] = None
    is_enabled: Optional[int] = None
    role_ids: Optional[list[int]] = None


class UserListItem(BaseModel):
    id: int
    username: str
    real_name: str
    is_enabled: int
    created_at: str
    roles: list[dict]

    class Config:
        from_attributes = True
