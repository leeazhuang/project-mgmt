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
