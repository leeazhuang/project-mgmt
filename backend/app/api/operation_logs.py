from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models.user import SysUser
from app.models.operation_log import SysOperationLog
from app.schemas.common import ResponseModel, PageResult

router = APIRouter(prefix="/api/operation-logs", tags=["操作日志"])


def _log_to_dict(log: SysOperationLog) -> dict:
    user_info = None
    if log.user:
        user_info = {
            "id": log.user.id,
            "username": log.user.username,
            "real_name": log.user.real_name,
        }
    after = log.after_data or {}
    status = after.get("status") if isinstance(after, dict) else None
    description = ""
    if isinstance(after, dict) and after.get("path"):
        description = f"{after.get('method', '')} {after.get('path', '')}"
        if log.target_id:
            description += f" (ID:{log.target_id})"
    return {
        "id": log.id,
        "user": user_info,
        "module": log.module or "",
        "action": log.action or "",
        "target_id": log.target_id,
        "target_type": log.target_type or "",
        "before_data": log.before_data,
        "after_data": log.after_data,
        "description": description,
        "success": status < 400 if isinstance(status, int) else True,
        "ip_address": log.ip_address or "",
        "user_agent": log.user_agent or "",
        "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
    }


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    module: str = Query(""),
    user_id: str = Query(""),
    action: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    current_user: SysUser = Depends(require_permission("log:list")),
    db: Session = Depends(get_db),
):
    query = db.query(SysOperationLog)

    if module:
        query = query.filter(SysOperationLog.module == module)
    if user_id:
        query = query.filter(SysOperationLog.user_id == int(user_id))
    if action:
        query = query.filter(SysOperationLog.action == action)
    if date_from:
        query = query.filter(SysOperationLog.created_at >= date_from + " 00:00:00")
    if date_to:
        query = query.filter(SysOperationLog.created_at <= date_to + " 23:59:59")

    total = query.count()
    logs = query.order_by(SysOperationLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_log_to_dict(lg) for lg in logs]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)
