from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.user import SysUser, SysRole
from app.schemas.common import ResponseModel, PageResult
from app.schemas.user import UserCreate, UserUpdate, UserListItem
from app.services.auth_service import hash_password

router = APIRouter(prefix="/api/users", tags=["用户管理"])


def _split_tags(value: str) -> list:
    return [t.strip() for t in (value or "").split(",") if t.strip()]


def _user_to_dict(user: SysUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "wx_room_id": user.wx_room_id or "",
        "wx_room_name": user.wx_room_name or "",
        "wx_user_id": user.wx_user_id or "",
        "wx_user_name": user.wx_user_name or "",
        "display_tags": _split_tags(user.display_tags),
        "is_enabled": user.is_enabled,
        "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
        "roles": [{"id": r.id, "name": r.name, "code": r.code} for r in user.roles],
    }


@router.get("/options", response_model=ResponseModel[list])
def user_options(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """用户下拉选项，只返回id和姓名，只需登录不需要user:list权限，排除admin"""
    users = db.query(SysUser).filter(
        SysUser.is_enabled == 1,
        SysUser.username != "admin",
    ).all()
    return ResponseModel(data=[
        {"id": u.id, "username": u.username, "real_name": u.real_name,
         "display_tags": _split_tags(u.display_tags)}
        for u in users
    ])


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str = Query("", description="按用户名或真实姓名搜索"),
    current_user: SysUser = Depends(require_permission("user:list")),
    db: Session = Depends(get_db),
):
    query = db.query(SysUser)
    if keyword:
        query = query.filter(
            (SysUser.username.contains(keyword)) | (SysUser.real_name.contains(keyword))
        )
    total = query.count()
    users = query.order_by(SysUser.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [_user_to_dict(u) for u in users]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel[dict])
def create_user(
    body: UserCreate,
    current_user: SysUser = Depends(require_permission("user:create")),
    db: Session = Depends(get_db),
):
    existing = db.query(SysUser).filter(SysUser.username == body.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = SysUser(
        username=body.username,
        password_hash=hash_password(body.password),
        real_name=body.real_name,
        wx_room_id=body.wx_room_id,
        wx_room_name=body.wx_room_name,
        wx_user_id=body.wx_user_id,
        wx_user_name=body.wx_user_name,
        display_tags=",".join(t.strip() for t in (body.display_tags or []) if t.strip()),
    )

    if body.role_ids:
        roles = db.query(SysRole).filter(SysRole.id.in_(body.role_ids)).all()
        user.roles = roles

    db.add(user)
    db.commit()
    db.refresh(user)
    return ResponseModel(data=_user_to_dict(user))


@router.get("/{user_id}", response_model=ResponseModel[dict])
def get_user(
    user_id: int,
    current_user: SysUser = Depends(require_permission("user:list")),
    db: Session = Depends(get_db),
):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ResponseModel(data=_user_to_dict(user))


@router.put("/{user_id}", response_model=ResponseModel[dict])
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: SysUser = Depends(require_permission("user:update")),
    db: Session = Depends(get_db),
):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.real_name is not None:
        user.real_name = body.real_name
    if body.wx_room_id is not None:
        user.wx_room_id = body.wx_room_id
    if body.wx_room_name is not None:
        user.wx_room_name = body.wx_room_name
    if body.wx_user_id is not None:
        user.wx_user_id = body.wx_user_id
    if body.wx_user_name is not None:
        user.wx_user_name = body.wx_user_name
    if body.is_enabled is not None:
        user.is_enabled = body.is_enabled
    if body.display_tags is not None:
        user.display_tags = ",".join(t.strip() for t in body.display_tags if t.strip())

    if body.role_ids is not None:
        roles = db.query(SysRole).filter(SysRole.id.in_(body.role_ids)).all()
        user.roles = roles

    db.commit()
    db.refresh(user)
    return ResponseModel(data=_user_to_dict(user))


@router.delete("/{user_id}", response_model=ResponseModel[None])
def delete_user(
    user_id: int,
    current_user: SysUser = Depends(require_permission("user:delete")),
    db: Session = Depends(get_db),
):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    db.delete(user)
    db.commit()
    return ResponseModel(message="删除成功")


class ResetPasswordRequest(BaseModel):
    new_password: str = "123456"


@router.post("/{user_id}/reset-password", response_model=ResponseModel[None])
def reset_password(
    user_id: int,
    body: ResetPasswordRequest = None,
    current_user: SysUser = Depends(require_permission("user:update")),
    db: Session = Depends(get_db),
):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    new_pwd = (body.new_password if body and body.new_password else None) or "123456"
    user.password_hash = hash_password(new_pwd)
    user.token_version = (user.token_version or 0) + 1  # 作废该用户所有已签发的旧 token
    db.commit()
    return ResponseModel(message="密码重置成功")


@router.put("/{user_id}/roles", response_model=ResponseModel[dict])
def assign_roles(
    user_id: int,
    role_ids: list[int],
    current_user: SysUser = Depends(require_permission("user:update")),
    db: Session = Depends(get_db),
):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    roles = db.query(SysRole).filter(SysRole.id.in_(role_ids)).all()
    user.roles = roles
    db.commit()
    db.refresh(user)
    return ResponseModel(data=_user_to_dict(user))
