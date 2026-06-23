from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, case

from app.database import get_db
from app.services.data_permission import is_tag_only_viewer
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.project import BizProject, BizProjectMember
from app.models.requirement import BizRequirement
from app.models.task import BizTask, BizTaskLog, BizTaskAssignee
from app.services.notify_service import send as notify, send_to_many as notify_many
from app.schemas.common import ResponseModel, PageResult
from app.schemas.task import TaskCreate, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _assignee_to_dict(ta: BizTaskAssignee, tag_only: bool = False) -> dict:
    tag = ta.display_tag or ""
    # 受限角色（仅看标签）+ 该分配有标签快照 → 彻底隐藏真实指派人（抓包也拿不到真名/user_id）
    hide = tag_only and bool(tag)
    return {
        "id": ta.id,
        "user_id": None if hide else ta.user_id,
        "user": None if hide else _user_brief(ta.user),
        "display_tag": tag,
        "status": ta.status,
        "start_date": ta.start_date.strftime("%Y-%m-%d %H:%M:%S") if ta.start_date else None,
        "completed_at": ta.completed_at.strftime("%Y-%m-%d %H:%M:%S") if ta.completed_at else None,
    }


def _task_to_dict(task: BizTask, tag_only: bool = False) -> dict:
    project = task.project
    assignee_list = [_assignee_to_dict(ta, tag_only) for ta in (task.assignees or [])]
    # 向前兼容：如果有旧的 assignee_id 但没有子表数据（无标签快照，按真名展示）
    if not assignee_list and task.assignee_id and task.assignee:
        assignee_list = [{"id": 0, "user_id": task.assignee_id, "user": _user_brief(task.assignee),
                          "display_tag": "", "status": task.status, "start_date": None, "completed_at": None}]
    primary_assignee = assignee_list[0]["user"] if assignee_list else None
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project_name": project.name if project else "",
        "project_owner_id": project.owner_id if project else None,
        "project_tech_leader_id": project.tech_leader_id if project else None,
        "requirement_id": task.requirement_id,
        "requirement_title": task.requirement.title if task.requirement else "",
        "title": task.title,
        "description": task.description or "",
        "status": task.status,
        "priority": task.priority,
        "assignees": assignee_list,
        # 向前兼容单人字段（从已脱敏的 assignee_list 取，受限角色不会泄露真名）
        "assignee": primary_assignee,
        "assigner": _user_brief(task.assigner),
        "estimated_hours": float(task.estimated_hours) if task.estimated_hours else 0,
        "actual_hours": float(task.actual_hours) if task.actual_hours else 0,
        "planned_start_date": task.planned_start_date.isoformat() if task.planned_start_date else None,
        "start_date": task.start_date.strftime("%Y-%m-%d %H:%M:%S") if task.start_date else None,
        "end_date": task.end_date.isoformat() if task.end_date else None,
        "completed_at": task.completed_at.strftime("%Y-%m-%d %H:%M:%S") if task.completed_at else None,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "",
    }


def _is_super_admin(user: SysUser) -> bool:
    return any(r.code == "super_admin" for r in user.roles)


def _is_tech_leader(db: Session, project_id: int, user_id: int) -> bool:
    project = db.query(BizProject).filter(BizProject.id == project_id).first()
    return project is not None and project.tech_leader_id == user_id


def _is_project_member(db: Session, project_id: int, user_id: int) -> bool:
    return db.query(BizProjectMember).filter(
        BizProjectMember.project_id == project_id,
        BizProjectMember.user_id == user_id,
    ).first() is not None


def _get_task_stakeholder_ids(db: Session, task: BizTask) -> list[int]:
    """所有干系人：子表被分配人 + 技术负责人 + 项目负责人"""
    ids = [ta.user_id for ta in (task.assignees or [])]
    if task.assignee_id and task.assignee_id not in ids:
        ids.append(task.assignee_id)
    project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
    if project:
        if project.tech_leader_id:
            ids.append(project.tech_leader_id)
        if project.owner_id:
            ids.append(project.owner_id)
    return ids


def _sync_task_status(db: Session, task: BizTask):
    """根据子表状态同步主任务状态"""
    if not task.assignees:
        return
    statuses = [ta.status for ta in task.assignees]
    if all(s == "done" for s in statuses):
        if task.status != "done":
            task.status = "done"
            task.completed_at = datetime.now()
    elif any(s == "in_progress" for s in statuses):
        if task.status not in ("in_progress", "done"):
            task.status = "in_progress"
            if not task.start_date:
                task.start_date = datetime.now()
    # pending: 如果所有人都还是pending，主任务也是pending（不回退已开始的）


def _add_task_log(db: Session, task_id: int, operator_id: int, action: str,
                  remark: str = "", old_value: str = "", new_value: str = ""):
    log = BizTaskLog(
        task_id=task_id, operator_id=operator_id, action=action,
        remark=remark, old_value=old_value, new_value=new_value,
    )
    db.add(log)


# ==================== LIST ====================

@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    project_id: str = Query(""),
    requirement_id: str = Query(""),
    status: str = Query(""),
    assignee_id: str = Query(""),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BizTask)

    if not _is_super_admin(current_user):
        # 判断是否只有开发角色（没有负责人/技术负责人身份）
        role_codes = [r.code for r in current_user.roles]
        is_developer_only = 'developer' in role_codes and \
            not db.query(BizProject.id).filter(
                (BizProject.owner_id == current_user.id) | (BizProject.tech_leader_id == current_user.id)
            ).first()

        if is_developer_only:
            # 开发角色：只看分配给自己的（主表或子表）
            my_task_ids = db.query(BizTaskAssignee.task_id).filter(
                BizTaskAssignee.user_id == current_user.id
            ).subquery()
            query = query.filter(
                or_(BizTask.assignee_id == current_user.id, BizTask.id.in_(my_task_ids))
            )
        else:
            # 其他角色：看所在项目全部任务
            member_project_ids = db.query(BizProjectMember.project_id).filter(
                BizProjectMember.user_id == current_user.id
            ).subquery()
            query = query.filter(BizTask.project_id.in_(member_project_ids))

    if project_id:
        query = query.filter(BizTask.project_id == int(project_id))
    if requirement_id and requirement_id.isdigit():
        query = query.filter(BizTask.requirement_id == int(requirement_id))
    if status:
        query = query.filter(BizTask.status == status)
    if assignee_id:
        aid = int(assignee_id)
        sub = db.query(BizTaskAssignee.task_id).filter(BizTaskAssignee.user_id == aid).subquery()
        query = query.filter(or_(BizTask.assignee_id == aid, BizTask.id.in_(sub)))

    total = query.count()
    # 排序：未处理 > 进行中 > 已完成（含作废），同桶内按创建时间倒序
    status_order = case(
        (BizTask.status == "pending", 0),
        (BizTask.status == "in_progress", 1),
        else_=2,
    )
    tasks = query.order_by(status_order, BizTask.created_at.desc(), BizTask.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    tag_only = is_tag_only_viewer(current_user)
    items = [_task_to_dict(t, tag_only) for t in tasks]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


# ==================== BOARD ====================

@router.get("/board", response_model=ResponseModel[dict])
def get_board(
    project_id: str = Query(""),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BizTask)

    if project_id and project_id.isdigit():
        query = query.filter(BizTask.project_id == int(project_id))

    if not _is_super_admin(current_user):
        # 与任务列表保持一致：开发角色只看分配给自己的，其他角色看所在项目全部
        role_codes = [r.code for r in current_user.roles]
        is_developer_only = 'developer' in role_codes and \
            not db.query(BizProject.id).filter(
                (BizProject.owner_id == current_user.id) | (BizProject.tech_leader_id == current_user.id)
            ).first()

        if is_developer_only:
            my_task_ids = db.query(BizTaskAssignee.task_id).filter(
                BizTaskAssignee.user_id == current_user.id
            ).subquery()
            query = query.filter(
                or_(BizTask.assignee_id == current_user.id, BizTask.id.in_(my_task_ids))
            )
        else:
            member_project_ids = db.query(BizProjectMember.project_id).filter(
                BizProjectMember.user_id == current_user.id
            ).subquery()
            query = query.filter(BizTask.project_id.in_(member_project_ids))

    tasks = query.all()
    tag_only = is_tag_only_viewer(current_user)
    board = {"pending": [], "in_progress": [], "done": [], "voided": []}
    for t in tasks:
        td = _task_to_dict(t, tag_only)
        board.get(t.status, board["pending"]).append(td)
    return ResponseModel(data=board)


# ==================== CREATE ====================

@router.post("", response_model=ResponseModel[dict])
def create_task(
    body: TaskCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(BizRequirement).filter(BizRequirement.id == body.requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")
    if req.status not in ("approved", "developing"):
        raise HTTPException(status_code=400, detail="只有已审批或开发中的需求才能创建任务")

    project = db.query(BizProject).filter(BizProject.id == req.project_id).first()
    is_leader = project and current_user.id in (project.tech_leader_id, project.owner_id)
    if not _is_super_admin(current_user) and not is_leader:
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人才能创建任务")
    if not req.estimated_deadline:
        raise HTTPException(status_code=400, detail="请先设置需求的预计截止时间后再创建任务")

    if not body.assignee_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个指派人")

    for uid in body.assignee_ids:
        if not _is_project_member(db, req.project_id, uid):
            raise HTTPException(status_code=400, detail=f"指派人(id={uid})必须是项目成员")

    planned_start = date.fromisoformat(body.planned_start_date) if body.planned_start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None

    task = BizTask(
        project_id=req.project_id,
        requirement_id=body.requirement_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        assignee_id=body.assignee_ids[0],  # 主表存第一个，兼容旧逻辑
        assigner_id=current_user.id,
        estimated_hours=body.estimated_hours,
        planned_start_date=planned_start,
        end_date=end,
    )
    db.add(task)
    db.flush()

    # 创建多人子表，记录分配时选的展示标签快照
    tags = body.assignee_tags or {}
    for uid in body.assignee_ids:
        db.add(BizTaskAssignee(task_id=task.id, user_id=uid, display_tag=tags.get(uid, "") or ""))

    # 需求状态联动
    from app.models.requirement import BizApprovalLog
    existing_tasks = db.query(BizTask).filter(BizTask.requirement_id == body.requirement_id).count()
    assignee_names = []
    for uid in body.assignee_ids:
        u = db.query(SysUser).filter(SysUser.id == uid).first()
        if u:
            assignee_names.append(u.real_name)

    names_str = "、".join(assignee_names)
    if existing_tasks <= 1:
        req.status = "developing"
        db.add(BizApprovalLog(
            requirement_id=body.requirement_id, operator_id=current_user.id,
            action="assign_task", remark=f"分配任务《{task.title}》给 {names_str}，需求进入开发中",
        ))
    else:
        db.add(BizApprovalLog(
            requirement_id=body.requirement_id, operator_id=current_user.id,
            action="assign_task", remark=f"新增任务《{task.title}》，指派给 {names_str}",
        ))

    _add_task_log(db, task.id, current_user.id, "create", f"创建任务，分配给 {names_str}")

    # 通知所有被分配人
    notify_many(db, body.assignee_ids, "新任务指派", f"您有新的任务《{task.title}》",
                type="task", related_id=task.id, related_type="task",
                exclude_user_id=current_user.id)

    db.commit()
    db.refresh(task)
    return ResponseModel(data=_task_to_dict(task, is_tag_only_viewer(current_user)))


# ==================== GET ====================

@router.get("/{task_id}", response_model=ResponseModel[dict])
def get_task(
    task_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 允许：超管、项目成员、被分配人
    is_assignee = db.query(BizTaskAssignee).filter(
        BizTaskAssignee.task_id == task_id, BizTaskAssignee.user_id == current_user.id
    ).first() is not None
    if not _is_super_admin(current_user) and not is_assignee and \
       not _is_project_member(db, task.project_id, current_user.id) and \
       task.assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有访问权限")

    return ResponseModel(data=_task_to_dict(task, is_tag_only_viewer(current_user)))


# ==================== UPDATE / STATUS ====================

@router.put("/{task_id}", response_model=ResponseModel[dict])
def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not _is_super_admin(current_user) and not _is_project_member(db, task.project_id, current_user.id):
        # 也允许子表被分配人操作状态
        is_assignee = db.query(BizTaskAssignee).filter(
            BizTaskAssignee.task_id == task_id, BizTaskAssignee.user_id == current_user.id
        ).first() is not None
        if not is_assignee:
            raise HTTPException(status_code=403, detail="没有访问权限")

    # 编辑/重新指派的状态判断基于本次操作前的原始状态
    original_status = task.status

    # 重新指派（多人）- 差量更新：保留未变动人员的状态，只增删变化的人
    if body.assignee_ids is not None:
        # 已完成/已作废的任务不允许重新指派
        if original_status in ("done", "voided"):
            raise HTTPException(status_code=400, detail="已完成或已作废的任务不能重新指派")
        # 重新指派只允许超管/项目负责人/技术负责人
        project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
        if not _is_super_admin(current_user) and \
           (not project or current_user.id not in (project.owner_id, project.tech_leader_id)):
            raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以重新指派")

        old_names = [ta.user.real_name for ta in task.assignees if ta.user] if task.assignees else []
        existing = {ta.user_id: ta for ta in (task.assignees or [])}
        new_ids = list(dict.fromkeys(body.assignee_ids))  # 去重保序

        # 删除被移除的人
        for uid, ta in existing.items():
            if uid not in new_ids:
                db.delete(ta)
        # 添加新人（状态 pending），已存在的人保持原状态不动
        tags = body.assignee_tags or {}
        new_names = []
        for uid in new_ids:
            if not _is_project_member(db, task.project_id, uid):
                raise HTTPException(status_code=400, detail=f"指派人(id={uid})必须是项目成员")
            if uid not in existing:
                db.add(BizTaskAssignee(task_id=task_id, user_id=uid, display_tag=tags.get(uid, "") or ""))
            elif uid in tags:
                existing[uid].display_tag = tags.get(uid, "") or ""
            u = db.query(SysUser).filter(SysUser.id == uid).first()
            if u:
                new_names.append(u.real_name)

        task.assignee_id = new_ids[0] if new_ids else None

        # 根据剩余人员状态重算主任务状态（不影响未变动人员的进度）
        db.flush()
        remaining = db.query(BizTaskAssignee).filter(BizTaskAssignee.task_id == task_id).all()
        statuses = [a.status for a in remaining]
        if statuses and all(s == "done" for s in statuses):
            if task.status != "done":
                task.status = "done"
                task.completed_at = datetime.now()
        elif any(s in ("in_progress", "done") for s in statuses):
            task.status = "in_progress"
            if not task.start_date:
                task.start_date = datetime.now()
            task.completed_at = None
        else:
            task.status = "pending"
            task.start_date = None
            task.completed_at = None

        old_str = "、".join(old_names) or "未指派"
        new_str = "、".join(new_names) or "未指派"
        _add_task_log(db, task.id, current_user.id, "reassign",
                      f"重新指派: {old_str} → {new_str}", old_str, new_str)
        notify_many(db, new_ids + _get_task_stakeholder_ids(db, task),
                    "任务重新指派", f"任务《{task.title}》已重新指派: {old_str} → {new_str}",
                    type="task", related_id=task.id, related_type="task",
                    exclude_user_id=current_user.id)

    # 编辑基本信息：仅"待开始"状态可编辑，已开始/已完成/已作废一律锁定
    _basic_changed = any(v is not None for v in (
        body.title, body.description, body.priority,
        body.estimated_hours, body.planned_start_date, body.end_date,
    ))
    if _basic_changed:
        if original_status != "pending":
            raise HTTPException(status_code=400, detail="只有待开始的任务才能编辑基本信息")
        if body.title is not None:
            task.title = body.title
        if body.description is not None:
            task.description = body.description
        if body.priority is not None:
            task.priority = body.priority
        if body.estimated_hours is not None:
            task.estimated_hours = body.estimated_hours
        if body.planned_start_date is not None:
            task.planned_start_date = date.fromisoformat(body.planned_start_date)
        if body.end_date is not None:
            task.end_date = date.fromisoformat(body.end_date)

    # 状态变更（个人操作 → 改自己子表记录，然后同步主任务）
    if body.status is not None:
        my_assignee = db.query(BizTaskAssignee).filter(
            BizTaskAssignee.task_id == task_id,
            BizTaskAssignee.user_id == current_user.id,
        ).first()

        if my_assignee:
            # 有子表记录：更新自己的状态
            if body.status == "in_progress" and my_assignee.status == "pending":
                my_assignee.status = "in_progress"
                my_assignee.start_date = datetime.now()
                # 主任务实际开始时间 = 第一个点击开始的人的时间（只记一次，不被后续人覆盖）
                if not task.start_date:
                    task.start_date = datetime.now()
                _add_task_log(db, task.id, current_user.id, "start",
                              f"{current_user.real_name} 开始任务")
                project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
                if project and project.tech_leader_id:
                    notify(db, project.tech_leader_id, "任务已开始",
                           f"{current_user.real_name}已开始任务《{task.title}》",
                           type="task", related_id=task.id, related_type="task")

            elif body.status == "done" and my_assignee.status == "in_progress":
                my_assignee.status = "done"
                my_assignee.completed_at = datetime.now()
                _add_task_log(db, task.id, current_user.id, "done",
                              f"{current_user.real_name} 完成任务")
                # 通知在下方同步主任务状态后统一发送：
                # 全部完成→通知指派人/负责人；否则→通知技术负责人个人进度

            elif body.status == "pending" and my_assignee.status in ("in_progress", "done"):
                my_assignee.status = "pending"
                my_assignee.start_date = None
                my_assignee.completed_at = None
                _add_task_log(db, task.id, current_user.id, "reopen", "重新打开任务")

            # 同步主任务状态
            db.flush()
            # 重新查询所有子表
            all_assignees = db.query(BizTaskAssignee).filter(BizTaskAssignee.task_id == task_id).all()
            statuses = [a.status for a in all_assignees]
            if all(s == "done" for s in statuses):
                task.status = "done"
                task.completed_at = datetime.now()
                project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
                if len(all_assignees) <= 1:
                    # 单人任务：指派人点完成即完成，只记一条记录（上面个人 done 日志），
                    # 只发一条「任务完成」通知给 技术负责人+项目负责人，不再重复"所有人完成"
                    recipients = [project.tech_leader_id, project.owner_id] if project else []
                    notify_many(db, [i for i in recipients if i],
                                "任务完成", f"任务《{task.title}》已完成",
                                type="task", related_id=task.id, related_type="task",
                                exclude_user_id=current_user.id)
                else:
                    _add_task_log(db, task.id, current_user.id, "done", "所有人已完成，任务自动完成")
                    # 通知指派人和项目/技术负责人（不通知已完成的成员）
                    leader_ids = [task.assigner_id]
                    if project:
                        leader_ids += [project.tech_leader_id, project.owner_id]
                    notify_many(db, [i for i in leader_ids if i],
                                "任务已全部完成", f"任务《{task.title}》所有成员已完成",
                                type="task", related_id=task.id, related_type="task",
                                exclude_user_id=current_user.id)
            else:
                if body.status == "done":
                    # 个人完成但还有人未完成：通知技术负责人个人进度
                    project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
                    if project and project.tech_leader_id:
                        notify(db, project.tech_leader_id, "成员完成任务",
                               f"{current_user.real_name}已完成任务《{task.title}》中自己的部分",
                               type="task", related_id=task.id, related_type="task")
                if any(s == "in_progress" for s in statuses):
                    if task.status == "pending":
                        task.status = "in_progress"
                        if not task.start_date:
                            task.start_date = datetime.now()
        else:
            # 不在指派列表中：只有超管/项目负责人/技术负责人可直接改主任务状态
            # （防止被移出任务的人用未刷新的旧页面继续操作）
            project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
            is_leader = project and current_user.id in (project.owner_id, project.tech_leader_id)
            if not _is_super_admin(current_user) and not is_leader:
                raise HTTPException(status_code=403, detail="您已不是该任务的被分配人，无法操作任务状态")
            if task.assignees:
                raise HTTPException(status_code=400, detail="多人任务请通过重新指派调整，不能直接修改主状态")
            old_status = task.status
            task.status = body.status
            if body.status == "in_progress":
                if not task.start_date:
                    task.start_date = datetime.now()
                _add_task_log(db, task.id, current_user.id, "start", "开始任务")
            elif body.status == "done":
                task.completed_at = datetime.now()
                _add_task_log(db, task.id, current_user.id, "done", "完成任务")
            elif body.status == "pending" and old_status in ("in_progress", "done"):
                _add_task_log(db, task.id, current_user.id, "reopen", "重新打开任务")

    db.commit()
    db.refresh(task)
    return ResponseModel(data=_task_to_dict(task, is_tag_only_viewer(current_user)))


# ==================== DELETE ====================

@router.delete("/{task_id}", response_model=ResponseModel[None])
def delete_task(
    task_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not _is_super_admin(current_user) and not _is_tech_leader(db, task.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="只有技术负责人才能删除任务")
    db.delete(task)
    db.commit()
    return ResponseModel(message="删除成功")


# ==================== LOGS ====================

@router.get("/{task_id}/logs", response_model=ResponseModel[list])
def get_task_logs(
    task_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    from app.services.data_permission import ensure_project_access
    ensure_project_access(db, task.project_id, current_user)
    logs = db.query(BizTaskLog).filter(BizTaskLog.task_id == task_id).order_by(BizTaskLog.id.asc()).all()
    items = [{
        "id": lg.id, "operator": _user_brief(lg.operator), "action": lg.action,
        "remark": lg.remark or "", "old_value": lg.old_value or "",
        "new_value": lg.new_value or "",
        "created_at": lg.created_at.strftime("%Y-%m-%d %H:%M:%S") if lg.created_at else "",
    } for lg in logs]
    # 受限角色（仅看标签）：日志里有标签的人的真名替换成标签，无标签的保持真名
    if is_tag_only_viewer(current_user):
        from app.services.data_permission import mask_log_items
        ctx = {ta.user.real_name: ta.display_tag for ta in (task.assignees or [])
               if ta.display_tag and ta.user}
        items = mask_log_items(db, items, ctx)
    return ResponseModel(data=items)


# ==================== DELAY ====================

class DelayRequest(BaseModel):
    new_end_date: str
    reason: str = ""

@router.post("/{task_id}/delay", response_model=ResponseModel[dict])
def delay_task(
    task_id: int,
    body: DelayRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ("done", "voided"):
        raise HTTPException(status_code=400, detail="已完成或已作废的任务不能延期")

    project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
    if not _is_super_admin(current_user) and current_user.id not in (project.owner_id, project.tech_leader_id):
        raise HTTPException(status_code=403, detail="只有项目负责人或技术负责人可以延期")

    old_end = task.end_date.isoformat() if task.end_date else "未设置"
    task.end_date = date.fromisoformat(body.new_end_date)
    reason = body.reason or "任务延期"
    _add_task_log(db, task.id, current_user.id, "delay",
                  f"延期: {old_end} → {body.new_end_date}，原因: {reason}", old_end, body.new_end_date)

    notify_many(db, _get_task_stakeholder_ids(db, task),
                "任务延期通知", f"任务《{task.title}》延期至 {body.new_end_date}，原因: {reason}",
                type="task", related_id=task.id, related_type="task",
                exclude_user_id=current_user.id)

    db.commit()
    db.refresh(task)
    return ResponseModel(data=_task_to_dict(task, is_tag_only_viewer(current_user)))


# ==================== VOID ====================

class VoidRequest(BaseModel):
    reason: str = ""

@router.post("/{task_id}/void", response_model=ResponseModel[dict])
def void_task(
    task_id: int,
    body: VoidRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(BizTask).filter(BizTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status == "voided":
        raise HTTPException(status_code=400, detail="任务已经是作废状态")

    project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
    if not _is_super_admin(current_user) and current_user.id not in (project.tech_leader_id, project.owner_id):
        raise HTTPException(status_code=403, detail="只有技术负责人或项目负责人可以作废任务")

    task.status = "voided"
    reason = body.reason or "任务作废"
    _add_task_log(db, task.id, current_user.id, "void", f"作废任务，原因: {reason}", task.status, "voided")

    notify_many(db, _get_task_stakeholder_ids(db, task),
                "任务已作废", f"任务《{task.title}》已被作废，原因: {reason}",
                type="task", related_id=task.id, related_type="task",
                exclude_user_id=current_user.id)

    db.commit()
    db.refresh(task)
    return ResponseModel(data=_task_to_dict(task, is_tag_only_viewer(current_user)))
