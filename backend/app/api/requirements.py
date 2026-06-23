from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, case
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.project import BizProject, BizProjectMember
from app.models.requirement import BizRequirement, BizApprovalLog
from app.services.notify_service import send as notify
from app.schemas.common import ResponseModel, PageResult
from app.schemas.requirement import RequirementCreate, RequirementUpdate, ApprovalRequest

router = APIRouter(prefix="/api/requirements", tags=["需求管理"])


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _req_to_dict(req: BizRequirement) -> dict:
    return {
        "id": req.id,
        "project_id": req.project_id,
        "project_name": req.project.name if req.project else "",
        "title": req.title,
        "description": req.description or "",
        "status": req.status,
        "priority": req.priority,
        "creator": _user_brief(req.creator),
        "reject_reason": req.reject_reason or "",
        "deadline": req.deadline.isoformat() if req.deadline else None,
        "estimated_deadline": req.estimated_deadline.isoformat() if req.estimated_deadline else None,
        "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "",
        "updated_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.updated_at else "",
    }


def _is_project_member(db: Session, project_id: int, user_id: int) -> bool:
    return db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first() is not None


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _notify_req(db: Session, user_id: int, title: str, content: str, req_id: int):
    notify(db, user_id, title, content, type="approval", related_id=req_id, related_type="requirement")


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_requirements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    project_id: str = Query(""),
    status: str = Query(""),
    priority: str = Query(""),
    keyword: str = Query(""),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BizRequirement)

    if not _is_super_admin(current_user):
        member_project_ids = db.query(BizProjectMember.project_id).filter(
            BizProjectMember.user_id == current_user.id
        ).subquery()
        query = query.filter(BizRequirement.project_id.in_(member_project_ids))
        # 草稿（未提交）只有创建人自己可见，项目负责人/技术负责人等都看不到
        query = query.filter(
            or_(BizRequirement.status != "draft", BizRequirement.creator_id == current_user.id)
        )

    if project_id and project_id.isdigit():
        query = query.filter(BizRequirement.project_id == int(project_id))
    if status:
        if "," in status:
            query = query.filter(BizRequirement.status.in_(status.split(",")))
        else:
            query = query.filter(BizRequirement.status == status)
    if priority:
        query = query.filter(BizRequirement.priority == priority)
    if keyword:
        query = query.filter(BizRequirement.title.contains(keyword))

    total = query.count()
    # 排序：未处理(草稿/待审批/已通过) > 进行中(开发中) > 已完成(完成/关闭/拒绝/作废)，同桶内创建时间倒序
    status_order = case(
        (BizRequirement.status.in_(["draft", "pending", "approved"]), 0),
        (BizRequirement.status == "developing", 1),
        else_=2,
    )
    reqs = query.order_by(status_order, BizRequirement.created_at.desc(), BizRequirement.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    items = [_req_to_dict(r) for r in reqs]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel[dict])
def create_requirement(
    body: RequirementCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(BizProject).filter(BizProject.id == body.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not _is_super_admin(current_user) and not _is_project_member(db, body.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有项目成员才能创建需求")

    deadline = date.fromisoformat(body.deadline) if body.deadline else None

    req = BizRequirement(
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        creator_id=current_user.id,
        deadline=deadline,
    )
    # 创建人若是该项目的技术负责人，需求直接进入"已接受"，无需提交审批、不通知项目负责人
    is_tech_leader = project.tech_leader_id == current_user.id
    if is_tech_leader:
        req.status = "approved"
    db.add(req)
    db.flush()
    if is_tech_leader:
        db.add(BizApprovalLog(
            requirement_id=req.id,
            operator_id=current_user.id,
            action="approve",
            remark="技术负责人创建需求，直接进入已接受",
        ))

    # 技术负责人新建需求时直接建任务：设预计截止 + 自动建任务，全程不发任何通知
    if is_tech_leader and body.assignee_ids:
        if not body.estimated_deadline:
            raise HTTPException(status_code=400, detail="直接建任务时请设置需求预计截止时间")
        req.estimated_deadline = date.fromisoformat(body.estimated_deadline)
        for uid in body.assignee_ids:
            if not _is_project_member(db, body.project_id, uid):
                raise HTTPException(status_code=400, detail=f"指派人(id={uid})必须是项目成员")

        from app.models.task import BizTask, BizTaskAssignee, BizTaskLog
        from app.models.attachment import BizAttachment
        task = BizTask(
            project_id=req.project_id,
            requirement_id=req.id,
            title=req.title,
            description=req.description,
            priority=req.priority,
            assignee_id=body.assignee_ids[0],
            assigner_id=current_user.id,
            estimated_hours=body.estimated_hours or 0,
            planned_start_date=date.today(),
            end_date=date.fromisoformat(body.task_end_date) if body.task_end_date else None,
        )
        db.add(task)
        db.flush()

        tags = body.assignee_tags or {}
        assignee_names = []
        for uid in body.assignee_ids:
            db.add(BizTaskAssignee(task_id=task.id, user_id=uid, display_tag=tags.get(uid, "") or ""))
            u = db.query(SysUser).filter(SysUser.id == uid).first()
            if u:
                assignee_names.append(u.real_name)

        # 复制需求附件到任务（同文件路径，复制一份行）
        if body.attachment_ids:
            atts = db.query(BizAttachment).filter(
                BizAttachment.id.in_(body.attachment_ids),
                BizAttachment.target_id == 0,
                BizAttachment.uploader_id == current_user.id,
            ).all()
            for a in atts:
                a.target_id = req.id
                a.target_type = "requirement"
                db.add(BizAttachment(
                    target_id=task.id, target_type="task",
                    file_name=a.file_name, file_path=a.file_path,
                    file_size=a.file_size, file_type=a.file_type,
                    storage=a.storage, uploader_id=a.uploader_id,
                ))

        names_str = "、".join(assignee_names)
        req.status = "developing"
        db.add(BizApprovalLog(
            requirement_id=req.id, operator_id=current_user.id,
            action="assign_task", remark=f"创建需求并直接分配任务《{task.title}》给 {names_str}，需求进入开发中",
        ))
        db.add(BizTaskLog(
            task_id=task.id, operator_id=current_user.id,
            action="create", remark=f"由需求直接创建，分配给 {names_str}",
        ))
        # 不发任何通知（需求2.3）

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.get("/{req_id}", response_model=ResponseModel[dict])
def get_requirement(
    req_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if not _is_super_admin(current_user) and not _is_project_member(db, req.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="没有访问权限")

    # 草稿（未提交）仅创建人可见
    if req.status == "draft" and req.creator_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="草稿需求仅创建人可见")

    return ResponseModel(data=_req_to_dict(req))


@router.put("/{req_id}", response_model=ResponseModel[dict])
def update_requirement(
    req_id: int,
    body: RequirementUpdate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="只有草稿或被拒绝的需求才能编辑")

    if not _is_super_admin(current_user) and req.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有创建人才能编辑需求")

    if body.title is not None:
        req.title = body.title
    if body.description is not None:
        req.description = body.description
    if body.priority is not None:
        req.priority = body.priority
    if body.deadline is not None:
        req.deadline = date.fromisoformat(body.deadline)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.delete("/{req_id}", response_model=ResponseModel[None])
def delete_requirement(
    req_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="只有草稿或被拒绝的需求才能删除")

    if not _is_super_admin(current_user) and req.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有删除权限")

    db.delete(req)
    db.commit()
    return ResponseModel(message="删除成功")


@router.post("/{req_id}/submit", response_model=ResponseModel[dict])
def submit_requirement(
    req_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail="只有草稿或被拒绝的需求才能提交审批")

    if req.creator_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="只有创建人才能提交需求")

    req.status = "pending"
    log = BizApprovalLog(
        requirement_id=req_id,
        operator_id=current_user.id,
        action="submit",
        remark="提交审批",
    )
    db.add(log)

    # Notify project owner
    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    if project and project.owner_id:
        _notify_req(db, project.owner_id, "新需求待处理",
                    f"需求《{req.title}》已提交，等待您处理", req_id)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.post("/{req_id}/approve", response_model=ResponseModel[dict])
def approve_requirement(
    req_id: int,
    body: ApprovalRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status != "pending":
        raise HTTPException(status_code=400, detail="需求不处于待审批状态")

    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if project.owner_id != current_user.id and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="只有项目负责人才能审批需求")

    if body.action == "approve":
        req.status = "approved"
        req.reject_reason = ""
    elif body.action == "reject":
        req.status = "rejected"
        req.reject_reason = body.remark
    else:
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")

    log = BizApprovalLog(
        requirement_id=req_id,
        operator_id=current_user.id,
        action=body.action,
        remark=body.remark,
    )
    db.add(log)

    # Notify creator
    action_text = "已接受" if body.action == "approve" else "已拒绝"
    # 通知需求创建人
    _notify_req(db, req.creator_id, f"需求{action_text}",
                f"您的需求《{req.title}》{action_text}", req_id)
    # 接受时同时通知技术负责人
    if body.action == "approve" and project.tech_leader_id and project.tech_leader_id != current_user.id:
        _notify_req(db, project.tech_leader_id, "新需求已接受",
                    f"需求《{req.title}》已接受，请设置预计截止时间并分配任务", req_id)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.get("/{req_id}/approval-logs", response_model=ResponseModel[list])
def get_approval_logs(
    req_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    from app.services.data_permission import ensure_project_access
    ensure_project_access(db, req.project_id, current_user)

    logs = db.query(BizApprovalLog).filter(
        BizApprovalLog.requirement_id == req_id
    ).order_by(BizApprovalLog.id.asc()).all()

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
    return ResponseModel(data=items)


@router.post("/{req_id}/change-status", response_model=ResponseModel[dict])
def change_requirement_status(
    req_id: int,
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """状态变更：closed(标记完成), developing(重开)"""
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    new_status = body.get("status")
    valid_transitions = {
        "developing": ["closed", "voided"],
        "closed": ["developing"],
        "approved": ["voided"],
        "pending": ["voided"],
        "draft": ["voided"],
        "rejected": ["voided"],
        "done": ["closed", "developing", "voided"],
    }

    allowed = valid_transitions.get(req.status, [])
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"当前状态 {req.status} 不能变更为 {new_status}")

    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    is_admin = _is_super_admin(current_user)

    if new_status == "closed":
        if not is_admin and current_user.id != project.tech_leader_id:
            raise HTTPException(status_code=403, detail="只有技术负责人可以标记完成")
        from app.models.task import BizTask
        unfinished = db.query(BizTask).filter(
            BizTask.requirement_id == req_id,
            BizTask.status.notin_(["done", "voided"]),
        ).count()
        if unfinished > 0:
            raise HTTPException(status_code=400, detail=f"还有 {unfinished} 个未完成的任务，请先完成所有任务再标记需求完成")
    elif new_status == "developing":
        if not is_admin and current_user.id not in (project.owner_id, project.tech_leader_id):
            raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以重新打开")
    elif new_status == "voided":
        if not is_admin and current_user.id not in (project.owner_id, project.tech_leader_id):
            raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以作废需求")

    remark_text = body.get("remark", "")

    action_map = {"closed": "closed", "developing": "reopen", "voided": "voided"}
    default_remark = {"closed": "标记完成", "developing": "重新打开需求", "voided": f"作废需求，原因: {remark_text}"}

    req.status = new_status
    db.add(BizApprovalLog(
        requirement_id=req_id,
        operator_id=current_user.id,
        action=action_map[new_status],
        remark=remark_text or default_remark[new_status],
    ))

    # 作废：关联任务全部作废 + 通知相关人
    if new_status == "voided":
        from app.models.task import BizTask, BizTaskLog
        tasks = db.query(BizTask).filter(
            BizTask.requirement_id == req_id,
            BizTask.status != "voided",
        ).all()
        notify_uids = set()
        if req.creator_id:
            notify_uids.add(req.creator_id)
        for task in tasks:
            task.status = "voided"
            db.add(BizTaskLog(
                task_id=task.id, operator_id=current_user.id,
                action="void", remark=f"需求作废，关联任务自动作废",
            ))
            if task.assignee_id:
                notify_uids.add(task.assignee_id)
        from app.services.notify_service import send_to_many as notify_many
        notify_many(db, list(notify_uids),
                    "需求已作废", f"需求《{req.title}》已作废，原因: {remark_text}，关联任务已全部作废",
                    type="approval", related_id=req_id, related_type="requirement",
                    exclude_user_id=current_user.id)
    elif new_status == "closed":
        # 通知创建人 + 项目负责人（去重、排除操作人）
        from app.services.notify_service import send_to_many as notify_many
        notify_uids = [req.creator_id]
        if project and project.owner_id:
            notify_uids.append(project.owner_id)
        notify_many(db, notify_uids, "需求已完成",
                    f"需求《{req.title}》已标记完成",
                    type="approval", related_id=req_id, related_type="requirement",
                    exclude_user_id=current_user.id)
    elif new_status == "developing":
        if project and project.tech_leader_id:
            _notify_req(db, project.tech_leader_id, "需求重新打开",
                        f"需求《{req.title}》已被重新打开", req_id)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.post("/{req_id}/set-estimated-deadline", response_model=ResponseModel[dict])
def set_estimated_deadline(
    req_id: int,
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """技术负责人设置预计截止时间"""
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status not in ("approved", "developing"):
        raise HTTPException(status_code=400, detail="只有已审批或开发中的需求才能设置预计截止时间")

    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    if not _is_super_admin(current_user) and current_user.id != project.tech_leader_id:
        raise HTTPException(status_code=403, detail="只有技术负责人可以设置预计截止时间")

    estimated_deadline = body.get("estimated_deadline")
    if not estimated_deadline:
        raise HTTPException(status_code=400, detail="请提供预计截止时间")

    req.estimated_deadline = date.fromisoformat(estimated_deadline)

    db.add(BizApprovalLog(
        requirement_id=req_id,
        operator_id=current_user.id,
        action="set_deadline",
        remark=f"设置预计截止时间: {estimated_deadline}",
    ))

    # 通知需求创建人
    _notify_req(db, req.creator_id, "预计截止时间已设置",
                f"您的需求《{req.title}》预计截止时间已设置为 {estimated_deadline}", req_id)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))


@router.post("/{req_id}/delay", response_model=ResponseModel[dict])
def delay_requirement(
    req_id: int,
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """项目负责人/技术负责人延期需求的预计截止时间"""
    req = db.query(BizRequirement).filter(BizRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if req.status != "developing":
        raise HTTPException(status_code=400, detail="只有开发中的需求才能延期")

    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    if not _is_super_admin(current_user) and current_user.id not in (project.owner_id, project.tech_leader_id):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以延期")

    new_deadline = body.get("estimated_deadline")
    if not new_deadline:
        raise HTTPException(status_code=400, detail="请提供新的预计截止时间")
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="请填写延期原因")

    old_deadline = req.estimated_deadline.isoformat() if req.estimated_deadline else "未设置"
    req.estimated_deadline = date.fromisoformat(new_deadline)

    db.add(BizApprovalLog(
        requirement_id=req_id,
        operator_id=current_user.id,
        action="delay",
        remark=f"延期: {old_deadline} → {new_deadline}，原因: {reason}",
    ))

    # 通知创建人 + 技术负责人 + 项目负责人（操作人自己除外）
    from app.services.notify_service import send_to_many as notify_many
    notify_uids = set()
    if req.creator_id:
        notify_uids.add(req.creator_id)
    if project.tech_leader_id:
        notify_uids.add(project.tech_leader_id)
    if project.owner_id:
        notify_uids.add(project.owner_id)
    notify_many(db, list(notify_uids),
                "需求延期通知",
                f"需求《{req.title}》预计截止时间延期至 {new_deadline}，原因: {reason}",
                type="approval", related_id=req_id, related_type="requirement",
                exclude_user_id=current_user.id)

    db.commit()
    db.refresh(req)
    return ResponseModel(data=_req_to_dict(req))
