from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.user import SysUser
from app.models.project import BizProject, BizProjectMember
from app.schemas.common import ResponseModel, PageResult
from app.schemas.project import ProjectCreate, ProjectUpdate, AddMembersRequest
from app.services.notify_service import send as notify

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _can_manage_members(project: BizProject, user: SysUser) -> bool:
    """只有超管、项目负责人、技术负责人可以增减成员"""
    if _is_super_admin(user):
        return True
    return user.id in (project.owner_id, project.tech_leader_id)


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _project_to_dict(project: BizProject) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description or "",
        "status": project.status,
        "owner": _user_brief(project.owner),
        "tech_leader": _user_brief(project.tech_leader),
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "member_count": len(project.members),
        "created_at": project.created_at.strftime("%Y-%m-%d %H:%M:%S") if project.created_at else "",
    }


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _ensure_member(db: Session, project_id: int, user_id: int):
    exists = db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first()
    if not exists:
        db.add(BizProjectMember(project_id=project_id, user_id=user_id))


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str = Query(""),
    status: str = Query(""),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BizProject)

    if not _is_super_admin(current_user):
        member_project_ids = db.query(BizProjectMember.project_id).filter(
            BizProjectMember.user_id == current_user.id
        ).subquery()
        query = query.filter(BizProject.id.in_(member_project_ids))

    if keyword:
        query = query.filter(BizProject.name.contains(keyword))
    if status:
        query = query.filter(BizProject.status == status)

    total = query.count()
    projects = query.order_by(BizProject.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_project_to_dict(p) for p in projects]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel[dict])
def create_project(
    body: ProjectCreate,
    current_user: SysUser = Depends(require_permission("project:create")),
    db: Session = Depends(get_db),
):
    start = date.fromisoformat(body.start_date) if body.start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None

    project = BizProject(
        name=body.name,
        description=body.description,
        owner_id=body.owner_id,
        tech_leader_id=body.tech_leader_id,
        creator_id=current_user.id,
        start_date=start,
        end_date=end,
    )
    db.add(project)
    db.flush()

    # Auto-add owner and tech_leader as members
    member_ids = set(body.member_ids)
    member_ids.add(body.owner_id)
    if body.tech_leader_id:
        member_ids.add(body.tech_leader_id)

    for uid in member_ids:
        if uid:
            db.add(BizProjectMember(project_id=project.id, user_id=uid))

    db.commit()
    db.refresh(project)
    return ResponseModel(data=_project_to_dict(project))


@router.get("/{project_id}", response_model=ResponseModel[dict])
def get_project(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not _is_super_admin(current_user):
        member = db.query(BizProjectMember).filter(
            BizProjectMember.project_id == project_id,
            BizProjectMember.user_id == current_user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="没有访问权限")

    return ResponseModel(data=_project_to_dict(project))


@router.put("/{project_id}", response_model=ResponseModel[dict])
def update_project(
    project_id: int,
    body: ProjectUpdate,
    current_user: SysUser = Depends(require_permission("project:update")),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.status is not None:
        project.status = body.status
    if body.owner_id is not None:
        project.owner_id = body.owner_id
        _ensure_member(db, project_id, body.owner_id)
    if body.tech_leader_id is not None:
        project.tech_leader_id = body.tech_leader_id
        _ensure_member(db, project_id, body.tech_leader_id)
    if body.start_date is not None:
        project.start_date = date.fromisoformat(body.start_date)
    if body.end_date is not None:
        project.end_date = date.fromisoformat(body.end_date)

    # 同步项目成员
    if body.member_ids is not None:
        if not _can_manage_members(project, current_user):
            raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以管理成员")
        # 确保负责人和技术负责人在成员列表中
        new_member_ids = set(body.member_ids)
        if project.owner_id:
            new_member_ids.add(project.owner_id)
        if project.tech_leader_id:
            new_member_ids.add(project.tech_leader_id)

        # 删除不在新列表中的成员（但保留负责人和技术负责人）
        db.query(BizProjectMember).filter(
            BizProjectMember.project_id == project_id,
            BizProjectMember.user_id.notin_(new_member_ids),
        ).delete(synchronize_session=False)

        # 添加新成员
        existing_ids = {
            m.user_id for m in
            db.query(BizProjectMember).filter(BizProjectMember.project_id == project_id).all()
        }
        for uid in new_member_ids:
            if uid not in existing_ids:
                db.add(BizProjectMember(project_id=project_id, user_id=uid))

    db.commit()
    db.refresh(project)
    return ResponseModel(data=_project_to_dict(project))


@router.delete("/{project_id}", response_model=ResponseModel[None])
def delete_project(
    project_id: int,
    current_user: SysUser = Depends(require_permission("project:delete")),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    db.delete(project)
    db.commit()
    return ResponseModel(message="删除成功")


@router.get("/{project_id}/members", response_model=ResponseModel[list])
def list_members(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from app.services.data_permission import ensure_project_access
    ensure_project_access(db, project_id, current_user)

    members = db.query(BizProjectMember).filter(BizProjectMember.project_id == project_id).all()
    items = [
        {
            "id": m.id,
            "user_id": m.user_id,
            "username": m.user.username if m.user else "",
            "real_name": m.user.real_name if m.user else "",
            "joined_at": m.joined_at.strftime("%Y-%m-%d %H:%M:%S") if m.joined_at else "",
        }
        for m in members
    ]
    return ResponseModel(data=items)


@router.post("/{project_id}/members", response_model=ResponseModel[None])
def add_members(
    project_id: int,
    body: AddMembersRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not _can_manage_members(project, current_user):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以管理成员")

    added = []
    for uid in body.user_ids:
        exists = db.query(BizProjectMember).filter(
            BizProjectMember.project_id == project_id,
            BizProjectMember.user_id == uid,
        ).first()
        if not exists:
            db.add(BizProjectMember(project_id=project_id, user_id=uid))
            added.append(uid)

    # 通知被添加的成员（纯告知，不带详情链接）
    for uid in added:
        notify(db, uid, "加入项目", f"您已被添加到项目《{project.name}》", type="system")

    db.commit()
    return ResponseModel(message="成员添加成功")


@router.delete("/{project_id}/members/{user_id}", response_model=ResponseModel[None])
def remove_member(
    project_id: int,
    user_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not _can_manage_members(project, current_user):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以管理成员")

    if user_id in (project.owner_id, project.tech_leader_id):
        raise HTTPException(status_code=400, detail="不能移除项目负责人或技术负责人")

    member = db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    db.delete(member)

    # 通知被移除的成员（纯告知，不带详情链接）
    notify(db, user_id, "移出项目", f"您已被移出项目《{project.name}》", type="system")

    db.commit()
    return ResponseModel(message="成员已移除")
