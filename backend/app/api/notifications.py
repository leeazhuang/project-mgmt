from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.notification import SysNotification
from app.schemas.common import ResponseModel, PageResult

router = APIRouter(prefix="/api/notifications", tags=["通知"])


def _notif_to_dict(n: SysNotification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content or "",
        "type": n.type,
        "related_id": n.related_id,
        "related_type": n.related_type or "",
        "is_read": n.is_read,
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
    }


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    is_read: int = Query(-1, description="-1=全部, 0=未读, 1=已读"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SysNotification).filter(SysNotification.user_id == current_user.id)

    if is_read != -1:
        query = query.filter(SysNotification.is_read == is_read)

    total = query.count()
    items = query.order_by(SysNotification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = PageResult(
        items=[_notif_to_dict(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=result)


@router.get("/unread-count", response_model=ResponseModel[dict])
def unread_count(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(SysNotification).filter(
        SysNotification.user_id == current_user.id,
        SysNotification.is_read == 0,
    ).count()
    return ResponseModel(data={"count": count})


@router.post("/{notification_id}/read", response_model=ResponseModel[None])
def mark_read(
    notification_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(SysNotification).filter(
        SysNotification.id == notification_id,
        SysNotification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")

    n.is_read = 1
    db.commit()
    return ResponseModel(message="已标记为已读")


@router.post("/read-all", response_model=ResponseModel[None])
def mark_all_read(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(SysNotification).filter(
        SysNotification.user_id == current_user.id,
        SysNotification.is_read == 0,
    ).update({"is_read": 1})
    db.commit()
    return ResponseModel(message="全部已读")
