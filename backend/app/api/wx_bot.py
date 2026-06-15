from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import ResponseModel
from app.services import wx_bot_service

router = APIRouter(prefix="/api/wxbot", tags=["微信机器人"])


@router.get("/groups", response_model=ResponseModel[list])
def list_groups(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """获取机器人所在的群列表（用户管理绑定下拉用）"""
    try:
        groups = wx_bot_service.get_groups(db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取群列表失败: {e}")
    return ResponseModel(data=[
        {"room_id": g.get("room_id", ""), "nickname": g.get("nickname", ""), "total": g.get("total", "")}
        for g in groups
    ])


@router.get("/groups/{room_id}/members", response_model=ResponseModel[list])
def list_group_members(
    room_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """获取指定群的成员列表（用户管理绑定下拉用）"""
    try:
        members = wx_bot_service.get_group_members(db, room_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取群成员失败: {e}")
    return ResponseModel(data=[
        {
            "user_id": m.get("user_id", ""),
            "realname": m.get("realname", ""),
            "nickname": m.get("nickname", ""),
            "avatar": m.get("avatar", ""),
        }
        for m in members
    ])


class BotTestRequest(BaseModel):
    room_id: str
    at_user_id: str = ""


@router.post("/test", response_model=ResponseModel[dict])
def test_send(
    body: BotTestRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """发送测试消息到指定群（可选艾特成员），验证机器人通知链路"""
    msg = "🔔 机器人通知测试\n这是一条测试消息，如果您看到此消息说明机器人配置正确。"
    at_list = [body.at_user_id] if body.at_user_id else []
    ok = wx_bot_service.send_group_at(db, body.room_id, msg, at_list)
    if not ok:
        raise HTTPException(status_code=502, detail="发送失败，请检查机器人地址和服务状态")
    return ResponseModel(data={"success": True}, message="测试消息已发送，请查看微信群")
