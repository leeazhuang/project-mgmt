"""
企业微信 HOOK 机器人工具包

通过 HTTP+JSON 调用机器人服务（地址存 sys_config: wx_bot_url）：
- 获取群列表    type=100208
- 获取群成员    type=100214
- 群艾特消息    type=100108（at_list 为空时降级为 100100 普通群文本）

所有发送类调用静默失败（仅记日志），不影响业务流程。
"""
import logging
from typing import Optional

import requests
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_TIMEOUT = 5


def _bot_url(db: Session) -> str:
    """从系统配置表读取机器人 API 地址（完整地址，含 /api）"""
    from app.models.sys_config import SysConfig
    config = db.query(SysConfig).filter(SysConfig.config_key == "wx_bot_url").first()
    return config.config_value.strip() if config and config.config_value else ""


def _call(db: Session, payload: dict) -> dict:
    """统一请求入口，返回机器人响应 JSON（失败抛异常，由调用方决定是否吞掉）"""
    url = _bot_url(db)
    if not url:
        raise RuntimeError("未配置机器人地址 wx_bot_url")
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    response = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT, proxies={"http": None, "https": None})
    response.raise_for_status()
    return response.json()


def get_groups(db: Session) -> list[dict]:
    """获取群列表，返回 [{room_id, nickname, total, ...}]"""
    result = _call(db, {"type": 100208})
    return result.get("list", [])


def get_group_members(db: Session, room_id: str) -> list[dict]:
    """获取群成员列表，返回 [{user_id, realname, nickname, avatar, ...}]"""
    result = _call(db, {"type": 100214, "data": {"room_id": room_id}})
    return result.get("member_list", [])


def send_group_at(db: Session, room_id: str, msg: str, at_user_ids: Optional[list] = None) -> bool:
    """
    发送群消息。at_user_ids 非空发群艾特消息，否则发普通群文本。
    静默失败，返回是否发送成功。
    """
    at_user_ids = [uid for uid in (at_user_ids or []) if uid]
    if at_user_ids:
        payload = {
            "type": 100108,
            "data": {"sendId": room_id, "msg": msg, "at_list": at_user_ids},
        }
    else:
        payload = {
            "type": 100100,
            "data": {"sendId": room_id, "msg": msg},
        }
    try:
        _call(db, payload)
        return True
    except Exception as e:
        logger.error(f"机器人群消息发送失败 room_id={room_id}: {e}")
        return False
