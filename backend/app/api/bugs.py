from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.database import get_db
from app.services.data_permission import is_tag_only_viewer
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.project import BizProject, BizProjectMember
from app.models.bug import BizBug, BizBugLog
from app.services.notify_service import send as notify, send_to_many as notify_many
from app.schemas.common import ResponseModel, PageResult
from app.schemas.bug import BugCreate, BugUpdate, BugAssign, BugReject, BugVerify, BugFixed

router = APIRouter(prefix="/api/bugs", tags=["Bug管理"])


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _bug_to_dict(bug: BizBug, tag_only: bool = False) -> dict:
    tag = bug.assignee_display_tag or ""
    # 受限角色（仅看标签）+ 有标签快照 → 彻底隐藏真实处理人（抓包也拿不到真名）
    hide = tag_only and bool(tag)
    return {
        "id": bug.id,
        "project_id": bug.project_id,
        "project": {"id": bug.project_id, "name": bug.project.name} if bug.project else None,
        "title": bug.title,
        "description": bug.description or "",
        "environment": "",
        "status": bug.status,
        "severity": bug.severity,
        "priority": bug.priority,
        "creator": _user_brief(bug.creator),
        "assignee": None if hide else (_user_brief(bug.assignee) if bug.assignee else None),
        "assignee_display_tag": tag,
        "reject_reason": bug.reject_reason or "",
        "updated_at": bug.updated_at.strftime("%Y-%m-%d %H:%M:%S") if bug.updated_at else "",
        "created_at": bug.created_at.strftime("%Y-%m-%d %H:%M:%S") if bug.created_at else "",
        "resolved_at": bug.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if bug.resolved_at else None,
        "closed_at": bug.closed_at.strftime("%Y-%m-%d %H:%M:%S") if bug.closed_at else None,
    }


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _is_tech_leader(db: Session, project_id: int, user_id: int) -> bool:
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    return project is not None and (project.tech_leader_id == user_id or project.owner_id == user_id)


def _is_project_member(db: Session, project_id: int, user_id: int) -> bool:
    return db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first() is not None


def _project_prefix(db: Session, project_id: int) -> str:
    """通知内容的所属项目前缀，如 '【项目名】'"""
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    return f"【{project.name}】" if project else ""


def _notify_bug(db: Session, user_id: int, title: str, content: str, bug_id: int, project_id: int = 0):
    prefix = _project_prefix(db, project_id) if project_id else ""
    notify(db, user_id, title, f"{prefix}{content}", type="bug", related_id=bug_id, related_type="bug")


def _add_bug_log(db: Session, bug_id: int, operator_id: int, action: str, remark: str = ""):
    log = BizBugLog(bug_id=bug_id, operator_id=operator_id, action=action, remark=remark)
    db.add(log)


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_bugs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    project_id: str = Query(""),
    status: str = Query(""),
    severity: str = Query(""),
    assignee_id: int = Query(0),
    my: int = Query(0, description="1=只看我提出的和分配给我的"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BizBug)

    if my == 1:
        # 我的Bug：只看分配给自己的
        query = query.filter(BizBug.assignee_id == current_user.id)
    elif not _is_super_admin(current_user):
        # Bug列表：项目成员可见所在项目的全部Bug
        member_project_ids = db.query(BizProjectMember.project_id).filter(
            BizProjectMember.user_id == current_user.id
        ).subquery()
        query = query.filter(BizBug.project_id.in_(member_project_ids))

    if project_id:
        query = query.filter(BizBug.project_id == int(project_id))
    if status:
        query = query.filter(BizBug.status == status)
    if severity:
        query = query.filter(BizBug.severity == severity)
    if assignee_id:
        query = query.filter(BizBug.assignee_id == assignee_id)

    total = query.count()
    # 排序：未处理(待处理) > 进行中(已指派/修复中/重开) > 已完成(已修复/已验证/已驳回)，同桶内创建时间倒序
    status_order = case(
        (BizBug.status == "pending", 0),
        (BizBug.status.in_(["assigned", "fixing", "reopened"]), 1),
        else_=2,
    )
    bugs = query.order_by(status_order, BizBug.created_at.desc(), BizBug.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    tag_only = is_tag_only_viewer(current_user)
    items = [_bug_to_dict(b, tag_only) for b in bugs]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel[dict])
def create_bug(
    body: BugCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == body.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not _is_super_admin(current_user) and not _is_project_member(db, body.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有项目成员才能提交Bug")

    bug = BizBug(
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        priority=body.priority,
        creator_id=current_user.id,
    )
    db.add(bug)
    db.flush()

    _add_bug_log(db, bug.id, current_user.id, "create", f"创建Bug《{bug.title}》")

    if project.tech_leader_id:
        _notify_bug(db, project.tech_leader_id, "新Bug提交", f"新Bug《{bug.title}》待处理", bug.id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.get("/{bug_id}", response_model=ResponseModel[dict])
def get_bug(
    bug_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    from app.services.data_permission import ensure_project_access
    ensure_project_access(db, bug.project_id, current_user)

    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.put("/{bug_id}", response_model=ResponseModel[dict])
def update_bug(
    bug_id: int,
    body: BugUpdate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    # 修复中不可编辑
    if bug.status in ("fixing",):
        raise HTTPException(status_code=400, detail="修复中的Bug不可编辑基本信息")

    if not _is_super_admin(current_user) and bug.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建人才能编辑Bug基本信息")

    if body.title is not None:
        bug.title = body.title
    if body.description is not None:
        bug.description = body.description
    if body.severity is not None:
        bug.severity = body.severity
    if body.priority is not None:
        bug.priority = body.priority

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.delete("/{bug_id}", response_model=ResponseModel[None])
def delete_bug(
    bug_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if not _is_super_admin(current_user) and bug.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有删除权限")

    db.delete(bug)
    db.commit()
    return ResponseModel(message="删除成功")


@router.post("/{bug_id}/assign", response_model=ResponseModel[dict])
def assign_bug(
    bug_id: int,
    body: BugAssign,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status not in ("pending", "reopened"):
        raise HTTPException(status_code=400, detail="只有待处理或重新打开的Bug才能指派")

    if not _is_super_admin(current_user) and not _is_tech_leader(db, bug.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人才能指派Bug")

    if not _is_project_member(db, bug.project_id, body.assignee_id):
        raise HTTPException(status_code=400, detail="指派人必须是项目成员")

    assignee = db.query(SysUser).filter(SysUser.id == body.assignee_id).first()
    assignee_name = assignee.real_name if assignee else ""

    bug.assignee_id = body.assignee_id
    bug.assignee_display_tag = body.display_tag or ""
    bug.status = "assigned"

    _add_bug_log(db, bug.id, current_user.id, "assign", f"指派给 {assignee_name}")
    _notify_bug(db, body.assignee_id, "Bug指派", f"Bug《{bug.title}》已指派给您处理", bug_id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.post("/{bug_id}/reassign", response_model=ResponseModel[dict])
def reassign_bug(
    bug_id: int,
    body: BugAssign,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重新指派Bug，状态回到assigned"""
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status in ("verified", "rejected"):
        raise HTTPException(status_code=400, detail="已关闭或已拒绝的Bug不能重新指派")

    if not _is_super_admin(current_user) and not _is_tech_leader(db, bug.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人才能重新指派Bug")

    if not _is_project_member(db, bug.project_id, body.assignee_id):
        raise HTTPException(status_code=400, detail="指派人必须是项目成员")

    old_assignee = db.query(SysUser).filter(SysUser.id == bug.assignee_id).first() if bug.assignee_id else None
    new_assignee = db.query(SysUser).filter(SysUser.id == body.assignee_id).first()
    old_name = old_assignee.real_name if old_assignee else "未指派"
    new_name = new_assignee.real_name if new_assignee else ""

    bug.assignee_id = body.assignee_id
    bug.assignee_display_tag = body.display_tag or ""
    bug.status = "assigned"
    bug.resolved_at = None

    _add_bug_log(db, bug.id, current_user.id, "reassign", f"重新指派: {old_name} → {new_name}")
    _notify_bug(db, body.assignee_id, "Bug重新指派", f"Bug《{bug.title}》已重新指派给您处理", bug_id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.post("/{bug_id}/reject", response_model=ResponseModel[dict])
def reject_bug(
    bug_id: int,
    body: BugReject,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status != "pending":
        raise HTTPException(status_code=400, detail="只有待处理的Bug才能拒绝")

    if not _is_super_admin(current_user) and not _is_tech_leader(db, bug.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人才能拒绝Bug")

    bug.status = "rejected"
    bug.reject_reason = body.reason

    _add_bug_log(db, bug.id, current_user.id, "reject", f"拒绝Bug，原因: {body.reason}")
    _notify_bug(db, bug.creator_id, "Bug被拒绝", f"您提交的Bug《{bug.title}》已被拒绝：{body.reason}", bug_id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.post("/{bug_id}/start-fix", response_model=ResponseModel[dict])
def start_fix(
    bug_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status != "assigned":
        raise HTTPException(status_code=400, detail="只有已指派的Bug才能开始修复")

    if bug.assignee_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="只有指派人才能开始修复")

    bug.status = "fixing"

    _add_bug_log(db, bug.id, current_user.id, "start_fix", "开始修复")

    # 通知Bug创建人
    _notify_bug(db, bug.creator_id, "Bug开始修复",
                f"您提交的Bug《{bug.title}》已开始修复", bug.id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.post("/{bug_id}/fixed", response_model=ResponseModel[dict])
def mark_fixed(
    bug_id: int,
    body: BugFixed,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status != "fixing":
        raise HTTPException(status_code=400, detail="只有修复中的Bug才能标记为已修复")

    if bug.assignee_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="只有指派人才能标记修复完成")

    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写Bug出现的具体原因")

    bug.status = "verified"
    bug.resolved_at = datetime.now()
    bug.closed_at = datetime.now()

    _add_bug_log(db, bug.id, current_user.id, "fixed", f"标记已解决，Bug已关闭。原因：{reason}")
    _notify_bug(db, bug.creator_id, "Bug已解决",
                f"Bug《{bug.title}》已解决。原因：{reason}", bug.id, bug.project_id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


class ReopenRequest(BaseModel):
    reason: str = ""


@router.post("/{bug_id}/reopen", response_model=ResponseModel[dict])
def reopen_bug(
    bug_id: int,
    body: ReopenRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发起人重开Bug（标记已解决但未实际解决时）"""
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    if bug.status != "verified":
        raise HTTPException(status_code=400, detail="只有已关闭的Bug才能重开")

    if bug.creator_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="只有Bug发起人才能重开")

    # 保留assignee，状态回到assigned
    bug.status = "assigned"
    bug.resolved_at = None
    bug.closed_at = None

    reason = body.reason or "问题未解决"
    _add_bug_log(db, bug.id, current_user.id, "reopen", f"重开Bug，原因: {reason}")
    # 通知被分配人 + 技术负责人
    recipients = []
    if bug.assignee_id:
        recipients.append(bug.assignee_id)
    project = db.query(BizProject).filter(BizProject.id == bug.project_id).first()
    if project:
        if project.tech_leader_id:
            recipients.append(project.tech_leader_id)
        if project.owner_id:
            recipients.append(project.owner_id)
    notify_many(db, recipients, "Bug被重开", f"{_project_prefix(db, bug.project_id)}Bug《{bug.title}》被重开，原因: {reason}",
                type="bug", related_id=bug_id, related_type="bug",
                exclude_user_id=current_user.id)

    db.commit()
    db.refresh(bug)
    return ResponseModel(data=_bug_to_dict(bug, is_tag_only_viewer(current_user)))


@router.get("/{bug_id}/logs", response_model=ResponseModel[list])
def get_bug_logs(
    bug_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取Bug流转记录"""
    bug = db.query(BizBug).filter(BizBug.id == bug_id).first()
    if not bug:
        raise HTTPException(status_code=404, detail="Bug不存在")

    from app.services.data_permission import ensure_project_access
    ensure_project_access(db, bug.project_id, current_user)

    logs = db.query(BizBugLog).filter(BizBugLog.bug_id == bug_id).order_by(BizBugLog.id.asc()).all()
    items = [
        {
            "id": lg.id,
            "operator": _user_brief(lg.operator),
            "action": lg.action,
            "remark": lg.remark or "",
            "created_at": lg.created_at.strftime("%Y-%m-%d %H:%M:%S") if lg.created_at else "",
        }
        for lg in logs
    ]
    # 受限角色（仅看标签）：日志里有标签的人的真名替换成标签，无标签的保持真名
    if is_tag_only_viewer(current_user):
        from app.services.data_permission import mask_log_items
        ctx = {}
        if bug.assignee and bug.assignee_display_tag:
            ctx[bug.assignee.real_name] = bug.assignee_display_tag
        items = mask_log_items(db, items, ctx)
    return ResponseModel(data=items)
