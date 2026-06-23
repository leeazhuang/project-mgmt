"""
数据权限统一校验工具

规则：非超管用户只能访问自己所在项目（biz_project_member）的数据。
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import SysUser
from app.models.project import BizProjectMember


def is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def is_tag_only_viewer(user: SysUser) -> bool:
    """该用户是否为「仅看分配标签」视角：任一角色开启 tag_only_view，且非超管。

    用于任务/Bug 数据返回时屏蔽真实指派人，只展示分配标签快照——
    即使直接抓接口响应也拿不到真实姓名/user_id。
    """
    if is_super_admin(user):
        return False
    return any(getattr(r, "tag_only_view", 0) == 1 for r in user.roles)


def mask_log_items(db: Session, items: list, context_name_tag: dict) -> list:
    """对流转记录做脱敏：把「有标签的用户」的真实姓名替换成展示标签。

    规则（与指派人展示一致）：有标签的用户→显示标签、不显示真名/user_id；无标签→保持真名。
    覆盖 operator 字段、remark、以及 old_value/new_value（重新指派会写名字）。

    context_name_tag: 当前任务/Bug 指派人的 {真名: 标签} 映射（优先用本对象的标签快照）；
    再用全局「有标签用户」补充历史名字（如改派走掉的人），保证日志里任何带标签的人都被替换。
    """
    from app.models.user import SysUser as _U
    name_tag = dict(context_name_tag or {})
    for u in db.query(_U).filter(_U.display_tags != "").all():
        first = (u.display_tags or "").split(",")[0].strip()
        if u.real_name and first and u.real_name not in name_tag:
            name_tag[u.real_name] = first
    if not name_tag:
        return items
    # 长名字优先替换，避免姓名互相包含时替换错
    names_by_len = sorted((n for n in name_tag if n), key=len, reverse=True)

    def _mask_text(text: str) -> str:
        if not text:
            return text
        for nm in names_by_len:
            if nm in text:
                text = text.replace(nm, name_tag[nm])
        return text

    for it in items:
        op = it.get("operator") or {}
        rn = op.get("real_name")
        if rn and rn in name_tag:
            # 隐藏真实 id/username，只留标签当作姓名展示
            it["operator"] = {"id": None, "username": "", "real_name": name_tag[rn]}
        if "remark" in it:
            it["remark"] = _mask_text(it.get("remark") or "")
        for k in ("old_value", "new_value"):
            if it.get(k):
                it[k] = _mask_text(it[k])
    return items


def is_project_member(db: Session, project_id: int, user_id: int) -> bool:
    return db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first() is not None


def ensure_project_access(db: Session, project_id: int, user: SysUser):
    """非项目成员（且非超管）访问项目数据 → 403"""
    if is_super_admin(user):
        return
    if not is_project_member(db, project_id, user.id):
        raise HTTPException(status_code=403, detail="没有访问权限")


def get_target_project_id(db: Session, target_type: str, target_id: int) -> Optional[int]:
    """由业务对象（requirement/task/bug/comment）回溯所属项目ID"""
    if not target_id:
        return None
    if target_type == "requirement":
        from app.models.requirement import BizRequirement
        obj = db.query(BizRequirement.project_id).filter(BizRequirement.id == target_id).first()
    elif target_type == "task":
        from app.models.task import BizTask
        obj = db.query(BizTask.project_id).filter(BizTask.id == target_id).first()
    elif target_type == "bug":
        from app.models.bug import BizBug
        obj = db.query(BizBug.project_id).filter(BizBug.id == target_id).first()
    elif target_type == "project":
        return target_id
    elif target_type == "comment":
        from app.models.comment import BizComment
        comment = db.query(BizComment).filter(BizComment.id == target_id).first()
        if comment:
            return get_target_project_id(db, comment.target_type, comment.target_id)
        return None
    else:
        return None
    return obj[0] if obj else None


def ensure_target_access(db: Session, target_type: str, target_id: int, user: SysUser):
    """校验用户是否可访问某业务对象（按其所属项目成员判断）"""
    project_id = get_target_project_id(db, target_type, target_id)
    if project_id:
        ensure_project_access(db, project_id, user)
