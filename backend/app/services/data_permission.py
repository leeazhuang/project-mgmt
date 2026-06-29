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


def mask_text(text: str, name_tag: dict) -> str:
    """把文本里出现的真名替换成对应标签。长名字优先，避免姓名互相包含时替换错。"""
    if not text or not name_tag:
        return text
    for nm in sorted((n for n in name_tag if n), key=len, reverse=True):
        if nm in text:
            text = text.replace(nm, name_tag[nm])
    return text


def build_assignment_tag_map(db: Session, related_type: str, related_id: int) -> dict:
    """构建某 task/bug「按标签分配」的人的 {真名: 标签} 映射。

    只收录分配时选了标签（display_tag 非空）的人——按真名分配的不收录、保持真名。
    用于评论/日志/推送的脱敏，使展示严格跟随「分配时的选择」（需求#2/#3）。
    requirement 等无指派标签快照的对象返回空 map（不脱敏）。
    """
    name_tag: dict = {}
    if not related_id:
        return name_tag
    if related_type == "task":
        from app.models.task import BizTaskAssignee
        rows = db.query(BizTaskAssignee).filter(
            BizTaskAssignee.task_id == related_id,
            BizTaskAssignee.display_tag != "",
        ).all()
        for r in rows:
            if r.user and r.user.real_name and r.display_tag:
                name_tag[r.user.real_name] = r.display_tag
    elif related_type == "bug":
        from app.models.bug import BizBug
        bug = db.query(BizBug).filter(BizBug.id == related_id).first()
        if bug and bug.assignee and bug.assignee.real_name and bug.assignee_display_tag:
            name_tag[bug.assignee.real_name] = bug.assignee_display_tag
    elif related_type == "requirement":
        # 需求本身无指派标签快照，聚合其下所有任务「按标签分配」的人
        from app.models.task import BizTask, BizTaskAssignee
        task_ids = [tid for (tid,) in db.query(BizTask.id).filter(BizTask.requirement_id == related_id).all()]
        if task_ids:
            rows = db.query(BizTaskAssignee).filter(
                BizTaskAssignee.task_id.in_(task_ids),
                BizTaskAssignee.display_tag != "",
            ).all()
            for r in rows:
                if r.user and r.user.real_name and r.display_tag:
                    name_tag[r.user.real_name] = r.display_tag
    return name_tag


def mask_user_brief(user_brief: dict, name_tag: dict) -> dict:
    """若 user_brief（含 real_name）是「按标签分配的人」，隐藏真实 id/username，只留标签当姓名。

    用于评论作者、附件上传人等单个用户展示的脱敏，使其与任务/Bug 指派展示一致。
    非按标签分配的人保持原样。
    """
    if not user_brief or not name_tag:
        return user_brief
    rn = user_brief.get("real_name")
    if rn and rn in name_tag:
        return {"id": None, "username": "", "real_name": name_tag[rn]}
    return user_brief


def mask_log_items(db: Session, items: list, context_name_tag: dict) -> list:
    """对流转记录做脱敏：把「按标签分配的人」的真实姓名替换成展示标签。

    规则（严格跟随分配时的选择）：分配时选了标签→显示标签、隐藏真名/user_id；
    选了真名（或本对象无标签快照）→ 保持真名。覆盖 operator 字段、remark、old_value/new_value。

    context_name_tag: 本任务/Bug「按标签分配」人的 {真名: 标签} 映射（来自分配快照）。
    不再全局扫描「凡有标签的用户」——避免把按真名分配的人也错误地换成标签（需求#2）。
    """
    name_tag = dict(context_name_tag or {})
    if not name_tag:
        return items

    for it in items:
        op = it.get("operator") or {}
        rn = op.get("real_name")
        if rn and rn in name_tag:
            # 隐藏真实 id/username，只留标签当作姓名展示
            it["operator"] = {"id": None, "username": "", "real_name": name_tag[rn]}
        if "remark" in it:
            it["remark"] = mask_text(it.get("remark") or "", name_tag)
        for k in ("old_value", "new_value"):
            if it.get(k):
                it[k] = mask_text(it[k], name_tag)
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
