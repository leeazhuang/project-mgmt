from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.project import BizProject, BizProjectMember
from app.models.requirement import BizRequirement
from app.models.task import BizTask
from app.models.bug import BizBug
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _is_project_leader(db: Session, user_id: int, project_id: int = None) -> bool:
    """判断用户是否是任意项目（或指定项目）的负责人/技术负责人"""
    query = db.query(BizProject)
    if project_id:
        query = query.filter(BizProject.id == project_id)
    projects = query.all()
    for p in projects:
        if user_id in (p.owner_id, p.tech_leader_id):
            return True
    return False


@router.get("/overview", response_model=ResponseModel[dict])
def overview(
    project_id: str = Query(""),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_

    req_query = db.query(BizRequirement)
    task_query = db.query(BizTask)
    bug_query = db.query(BizBug)

    pid = int(project_id) if project_id and project_id.isdigit() else None

    is_leader = _is_super_admin(current_user) or _is_project_leader(db, current_user.id, pid)

    if is_leader:
        # 项目负责人/技术负责人/超管：看项目整体数据
        if not _is_super_admin(current_user):
            member_project_ids = db.query(BizProjectMember.project_id).filter(
                BizProjectMember.user_id == current_user.id
            ).subquery()
            req_query = req_query.filter(BizRequirement.project_id.in_(member_project_ids))
            task_query = task_query.filter(BizTask.project_id.in_(member_project_ids))
            bug_query = bug_query.filter(BizBug.project_id.in_(member_project_ids))
    else:
        # 其他角色：只看和自己相关的
        uid = current_user.id
        req_query = req_query.filter(BizRequirement.creator_id == uid)
        task_query = task_query.filter(BizTask.assignee_id == uid)
        bug_query = bug_query.filter(or_(BizBug.creator_id == uid, BizBug.assignee_id == uid))

    if pid:
        req_query = req_query.filter(BizRequirement.project_id == pid)
        task_query = task_query.filter(BizTask.project_id == pid)
        bug_query = bug_query.filter(BizBug.project_id == pid)

    today = date.today()

    # Requirements stats
    req_stats = {
        "total": req_query.count(),
        "draft": req_query.filter(BizRequirement.status == "draft").count(),
        "pending": req_query.filter(BizRequirement.status == "pending").count(),
        "approved": req_query.filter(BizRequirement.status == "approved").count(),
        "rejected": req_query.filter(BizRequirement.status == "rejected").count(),
        "developing": req_query.filter(BizRequirement.status == "developing").count(),
        "done": req_query.filter(BizRequirement.status == "done").count(),
        "overdue": req_query.filter(
            BizRequirement.deadline < today,
            BizRequirement.status.notin_(["done", "closed"]),
        ).count(),
    }

    # Tasks stats
    task_stats = {
        "total": task_query.count(),
        "pending": task_query.filter(BizTask.status == "pending").count(),
        "in_progress": task_query.filter(BizTask.status == "in_progress").count(),
        "done": task_query.filter(BizTask.status == "done").count(),
        "overdue": task_query.filter(
            BizTask.end_date < today,
            BizTask.status != "done",
        ).count(),
    }

    # Bugs stats
    bug_stats = {
        "total": bug_query.count(),
        "pending": bug_query.filter(BizBug.status == "pending").count(),
        "assigned": bug_query.filter(BizBug.status == "assigned").count(),
        "fixing": bug_query.filter(BizBug.status == "fixing").count(),
        "fixed": bug_query.filter(BizBug.status == "fixed").count(),
        "verified": bug_query.filter(BizBug.status == "verified").count(),
        "rejected": bug_query.filter(BizBug.status == "rejected").count(),
        "reopened": bug_query.filter(BizBug.status == "reopened").count(),
    }

    return ResponseModel(data={
        "requirements": req_stats,
        "tasks": task_stats,
        "bugs": bug_stats,
    })


@router.get("/my-todo", response_model=ResponseModel[dict])
def my_todo(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 待我处理的需求（仅项目负责人/技术负责人/超管）
    pending_approval_items = []
    if _is_super_admin(current_user) or _is_project_leader(db, current_user.id):
        owned_project_ids = db.query(BizProject.id).filter(
            BizProject.owner_id == current_user.id
        ).subquery()

        pending_approvals = db.query(BizRequirement).filter(
            BizRequirement.project_id.in_(owned_project_ids),
            BizRequirement.status == "pending",
        ).order_by(BizRequirement.id.desc()).limit(10).all()

        pending_approval_items = [
            {
                "id": r.id,
                "title": r.title,
                "project_id": r.project_id,
                "project_name": r.project.name if r.project else "",
                "priority": r.priority,
                "creator": _user_brief(r.creator),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            }
            for r in pending_approvals
        ]

    # My pending/in_progress tasks
    my_tasks = db.query(BizTask).filter(
        BizTask.assignee_id == current_user.id,
        BizTask.status.in_(["pending", "in_progress"]),
    ).order_by(BizTask.end_date.asc()).limit(10).all()

    my_task_items = [
        {
            "id": t.id,
            "title": t.title,
            "project_id": t.project_id,
            "requirement_id": t.requirement_id,
            "status": t.status,
            "priority": t.priority,
            "end_date": t.end_date.isoformat() if t.end_date else None,
        }
        for t in my_tasks
    ]

    # My assigned/fixing bugs
    my_bugs = db.query(BizBug).filter(
        BizBug.assignee_id == current_user.id,
        BizBug.status.in_(["assigned", "fixing"]),
    ).order_by(BizBug.id.desc()).limit(10).all()

    my_bug_items = [
        {
            "id": b.id,
            "title": b.title,
            "project_id": b.project_id,
            "status": b.status,
            "severity": b.severity,
            "priority": b.priority,
        }
        for b in my_bugs
    ]

    # Bugs waiting for my verification (I created, status=fixed)
    bugs_to_verify = db.query(BizBug).filter(
        BizBug.creator_id == current_user.id,
        BizBug.status == "fixed",
    ).order_by(BizBug.id.desc()).limit(10).all()

    bugs_to_verify_items = [
        {
            "id": b.id,
            "title": b.title,
            "project_id": b.project_id,
            "status": b.status,
            "severity": b.severity,
            "assignee": _user_brief(b.assignee) if b.assignee else None,
        }
        for b in bugs_to_verify
    ]

    return ResponseModel(data={
        "pending_approvals": pending_approval_items,
        "my_tasks": my_task_items,
        "my_bugs": my_bug_items,
        "bugs_to_verify": bugs_to_verify_items,
    })
