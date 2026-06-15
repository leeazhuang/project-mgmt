from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models.user import SysUser, SysRole, SysMenu
from app.schemas.common import ResponseModel, PageResult
from app.schemas.role import RoleCreate, RoleUpdate, RoleOut

router = APIRouter(prefix="/api/roles", tags=["角色管理"])


def _role_to_dict(role: SysRole) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description or "",
        "is_enabled": role.is_enabled,
        "menu_ids": [m.id for m in role.menus],
    }


@router.get("", response_model=ResponseModel[PageResult[dict]])
def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str = Query(""),
    current_user: SysUser = Depends(require_permission("role:list")),
    db: Session = Depends(get_db),
):
    query = db.query(SysRole)
    if keyword:
        query = query.filter(
            (SysRole.name.contains(keyword)) | (SysRole.code.contains(keyword))
        )
    total = query.count()
    roles = query.order_by(SysRole.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [_role_to_dict(r) for r in roles]
    result = PageResult(items=items, total=total, page=page, page_size=page_size)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel[dict])
def create_role(
    body: RoleCreate,
    current_user: SysUser = Depends(require_permission("role:create")),
    db: Session = Depends(get_db),
):
    existing = db.query(SysRole).filter(SysRole.code == body.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="角色编码已存在")

    role = SysRole(
        name=body.name,
        code=body.code,
        description=body.description,
    )

    if body.menu_ids:
        menus = db.query(SysMenu).filter(SysMenu.id.in_(body.menu_ids)).all()
        role.menus = menus

    db.add(role)
    db.commit()
    db.refresh(role)
    return ResponseModel(data=_role_to_dict(role))


@router.get("/{role_id}", response_model=ResponseModel[dict])
def get_role(
    role_id: int,
    current_user: SysUser = Depends(require_permission("role:list")),
    db: Session = Depends(get_db),
):
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return ResponseModel(data=_role_to_dict(role))


@router.put("/{role_id}", response_model=ResponseModel[dict])
def update_role(
    role_id: int,
    body: RoleUpdate,
    current_user: SysUser = Depends(require_permission("role:update")),
    db: Session = Depends(get_db),
):
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.is_enabled is not None:
        role.is_enabled = body.is_enabled

    if body.menu_ids is not None:
        menus = db.query(SysMenu).filter(SysMenu.id.in_(body.menu_ids)).all()
        role.menus = menus

    db.commit()
    db.refresh(role)
    return ResponseModel(data=_role_to_dict(role))


@router.delete("/{role_id}", response_model=ResponseModel[None])
def delete_role(
    role_id: int,
    current_user: SysUser = Depends(require_permission("role:delete")),
    db: Session = Depends(get_db),
):
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.users:
        raise HTTPException(status_code=400, detail="该角色下还有用户，无法删除")

    db.delete(role)
    db.commit()
    return ResponseModel(message="删除成功")
