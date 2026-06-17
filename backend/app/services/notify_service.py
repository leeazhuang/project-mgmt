"""
统一通知服务 - 企微机器人群艾特模式

所有通知统一通过 send() / send_to_many() 发送，内部通过企业微信 HOOK 机器人
向用户绑定的群发送艾特消息（用户绑定见 sys_user.wx_room_id / wx_user_id）。

降级策略：
- 用户未绑定群（wx_room_id 为空）→ 跳过
- 绑定群但未绑定成员（wx_user_id 为空）→ 发群文本不艾特

事务一致性：
- send()/send_to_many() 不会立即发送，而是挂在数据库会话上，
  事务 commit 成功后（after_commit）才真正推送；rollback 则丢弃。
  保证"通知只在业务实际生效时发出"。

后续切换推送方式只需修改本文件，业务代码无需改动。
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import SysUser
from app.services import wx_bot_service

logger = logging.getLogger(__name__)

# 通知发送线程池：把机器人 HTTP 调用挪出请求线程，
# 避免机器人连不通时（每条最多 5s 超时 + 10s 兜底）阻塞业务接口响应
_notify_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="notify")


# ============================================================
#  事务后置发送：commit 成功才发，rollback 丢弃
# ============================================================

def _enqueue(db: Session, func):
    # 确保事务已开启：无事务时 rollback() 是空操作不会触发事件，队列会残留
    if not db.in_transaction():
        db.begin()
    db.info.setdefault("_pending_notify", []).append(func)


@event.listens_for(SessionLocal, "after_commit")
def _flush_pending_notify(session):
    pending = session.info.pop("_pending_notify", [])
    for fn in pending:
        # 丢到后台线程池异步发送，不阻塞当前请求线程（commit 后立即返回）
        def _run(fn=fn):
            try:
                fn()
            except Exception as e:
                logger.error(f"事务后通知发送失败: {e}")
        _notify_executor.submit(_run)


@event.listens_for(SessionLocal, "after_soft_rollback")
def _drop_pending_notify(session, previous_transaction):
    # after_soft_rollback 对所有 rollback() 调用都触发（包括未产生SQL的空回滚）
    dropped = session.info.pop("_pending_notify", None)
    if dropped:
        logger.info(f"事务回滚，丢弃 {len(dropped)} 条待发通知")


# ============================================================
#  URL 路由映射 - related_type → 前端页面路径
# ============================================================

_ROUTE_MAP = {
    "task": "/task/{id}",
    "bug": "/bug/{id}",
    "requirement": "/requirement/{id}",
    "project": "/project/{id}",
}

_TYPE_EMOJI = {
    "task": "📋",
    "bug": "🐛",
    "approval": "📝",
    "comment": "💬",
    "system": "🔔",
}


def _build_jump_url(related_type: str, related_id: int, base_url: str) -> str:
    """根据业务类型和ID构建前端跳转URL"""
    if not base_url or not related_type or not related_id:
        return ""
    pattern = _ROUTE_MAP.get(related_type, "")
    if not pattern:
        return base_url
    path = pattern.replace("{id}", str(related_id))
    return base_url.rstrip("/") + path


def _get_config(db: Session, key: str) -> str:
    from app.models.sys_config import SysConfig
    config = db.query(SysConfig).filter(SysConfig.config_key == key).first()
    return config.config_value if config and config.config_value else ""


def _get_site_url(db: Session) -> str:
    """从系统配置表读取前端站点地址"""
    return _get_config(db, "site_url")


def _fallback_alert(db: Session, room_id: str, receiver_names: list, msg: str):
    """
    机器人通知失败兜底：通过企微 Webhook 推送失败详情并艾特运维负责人。
    接收人 UserId 存 sys_config: notify_fallback_userid（默认 hns）。
    """
    try:
        webhook_url = _get_config(db, "wechat_work_webhook_url")
        if not webhook_url:
            logger.error("机器人通知失败且未配置 wechat_work_webhook_url，无法兜底告警")
            return
        fallback_userid = _get_config(db, "notify_fallback_userid") or "hns"
        names = "、".join(n for n in receiver_names if n) or "未知"
        content = (
            f"⚠️ 机器人通知发送失败，请检查机器人服务\n"
            f"目标群: {room_id}\n"
            f"接收人: {names}\n"
            f"------ 原通知内容 ------\n{msg}"
        )
        payload = {
            "msgtype": "text",
            "text": {"content": content, "mentioned_list": [fallback_userid]},
        }
        import requests
        requests.post(webhook_url, json=payload, timeout=10, proxies={"http": None, "https": None})
    except Exception as e:
        logger.error(f"兜底告警发送失败: {e}")


def _build_msg(db: Session, title: str, content: str, type: str, related_id: int, related_type: str) -> str:
    """构建群消息文本：emoji 标题 + 内容 + 跳转链接"""
    emoji = _TYPE_EMOJI.get(type, "🔔")
    jump_url = _build_jump_url(related_type, related_id, _get_site_url(db))
    msg = f"{emoji} {title}\n{content}"
    if jump_url:
        msg += f"\n查看详情: {jump_url}"
    return msg


# ============================================================
#  统一入口
# ============================================================

def send(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    type: str = "system",
    related_id: int = 0,
    related_type: str = "",
):
    """
    发送通知的唯一入口：向用户绑定的微信群发送艾特消息。

    Parameters:
        db: 数据库会话
        user_id: 接收人ID
        title: 通知标题
        content: 通知内容
        type: 通知类型 (approval/task/bug/comment/system)
        related_id: 关联业务ID
        related_type: 关联业务类型 (requirement/task/bug/project)
    """
    def _do_send():
        # after_commit 阶段原会话不能再发SQL，用独立会话查询（数据已提交，可见）
        ndb = SessionLocal()
        try:
            user = ndb.query(SysUser).filter(SysUser.id == user_id).first()
            if not user or not user.wx_room_id:
                return
            msg = _build_msg(ndb, title, content, type, related_id, related_type)
            at_list = [user.wx_user_id] if user.wx_user_id else []
            ok = wx_bot_service.send_group_at(ndb, user.wx_room_id, msg, at_list)
            if not ok:
                _fallback_alert(ndb, user.wx_room_id, [user.real_name], msg)
        finally:
            ndb.close()

    _enqueue(db, _do_send)


def send_to_many(
    db: Session,
    user_ids: list[int],
    title: str,
    content: str,
    type: str = "system",
    related_id: int = 0,
    related_type: str = "",
    exclude_user_id: Optional[int] = None,
):
    """
    批量发送通知，自动去重和排除操作人自己。
    同一个群的多个接收人合并为一条消息艾特多人。
    """
    seen = set()
    target_ids = []
    for uid in user_ids:
        if uid and uid not in seen and uid != exclude_user_id:
            seen.add(uid)
            target_ids.append(uid)
    if not target_ids:
        return

    def _do_send():
        # after_commit 阶段原会话不能再发SQL，用独立会话查询（数据已提交，可见）
        ndb = SessionLocal()
        try:
            users = ndb.query(SysUser).filter(SysUser.id.in_(target_ids)).all()
            # 按群分组合并：room_id → (艾特ID列表, 接收人姓名列表)
            rooms: dict = {}
            for user in users:
                if not user.wx_room_id:
                    continue
                at_list, names = rooms.setdefault(user.wx_room_id, ([], []))
                if user.wx_user_id:
                    at_list.append(user.wx_user_id)
                names.append(user.real_name)

            if not rooms:
                return
            msg = _build_msg(ndb, title, content, type, related_id, related_type)
            for room_id, (at_list, names) in rooms.items():
                ok = wx_bot_service.send_group_at(ndb, room_id, msg, at_list)
                if not ok:
                    _fallback_alert(ndb, room_id, names, msg)
        finally:
            ndb.close()

    _enqueue(db, _do_send)
