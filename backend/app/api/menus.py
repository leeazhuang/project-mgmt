from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models.user import SysUser, SysMenu
from app.schemas.common import ResponseModel
from app.schemas.menu import MenuCreate, MenuUpdate

router = APIRouter(prefix="/api/menus", tags=["菜单管理"])


def _menu_to_dict(menu: SysMenu) -> dict:
    return {
        "id": menu.id,
        "parent_id": menu.parent_id,
        "name": menu.name,
        "type": menu.type,
        "path": menu.path or "",
        "component": menu.component or "",
        "permission_code": menu.permission_code or "",
        "icon": menu.icon or "",
        "sort_order": menu.sort_order,
        "is_visible": menu.is_visible,
        "is_enabled": menu.is_enabled,
        "children": [],
    }


def _build_tree(menus: list, parent_id: int = 0) -> list:
    tree = []
    for m in menus:
        if m["parent_id"] == parent_id:
            m["children"] = _build_tree(menus, m["id"])
            tree.append(m)
    tree.sort(key=lambda x: x["sort_order"])
    return tree


@router.get("", response_model=ResponseModel[list])
def list_menus(
    current_user: SysUser = Depends(require_permission("menu:list")),
    db: Session = Depends(get_db),
):
    menus = db.query(SysMenu).order_by(SysMenu.sort_order.asc()).all()
    menu_dicts = [_menu_to_dict(m) for m in menus]
    tree = _build_tree(menu_dicts)
    return ResponseModel(data=tree)


@router.post("", response_model=ResponseModel[dict])
def create_menu(
    body: MenuCreate,
    current_user: SysUser = Depends(require_permission("menu:create")),
    db: Session = Depends(get_db),
):
    if body.parent_id != 0:
        parent = db.query(SysMenu).filter(SysMenu.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父菜单不存在")

    menu = SysMenu(
        parent_id=body.parent_id,
        name=body.name,
        type=body.type,
        path=body.path,
        component=body.component,
        permission_code=body.permission_code,
        icon=body.icon,
        sort_order=body.sort_order,
        is_visible=body.is_visible,
    )
    db.add(menu)
    db.commit()
    db.refresh(menu)
    return ResponseModel(data=_menu_to_dict(menu))


@router.get("/{menu_id}", response_model=ResponseModel[dict])
def get_menu(
    menu_id: int,
    current_user: SysUser = Depends(require_permission("menu:list")),
    db: Session = Depends(get_db),
):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    return ResponseModel(data=_menu_to_dict(menu))


@router.put("/{menu_id}", response_model=ResponseModel[dict])
def update_menu(
    menu_id: int,
    body: MenuUpdate,
    current_user: SysUser = Depends(require_permission("menu:update")),
    db: Session = Depends(get_db),
):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")

    if body.parent_id is not None:
        menu.parent_id = body.parent_id
    if body.name is not None:
        menu.name = body.name
    if body.type is not None:
        menu.type = body.type
    if body.path is not None:
        menu.path = body.path
    if body.component is not None:
        menu.component = body.component
    if body.permission_code is not None:
        menu.permission_code = body.permission_code
    if body.icon is not None:
        menu.icon = body.icon
    if body.sort_order is not None:
        menu.sort_order = body.sort_order
    if body.is_visible is not None:
        menu.is_visible = body.is_visible
    if body.is_enabled is not None:
        menu.is_enabled = body.is_enabled

    db.commit()
    db.refresh(menu)
    return ResponseModel(data=_menu_to_dict(menu))


@router.delete("/{menu_id}", response_model=ResponseModel[None])
def delete_menu(
    menu_id: int,
    current_user: SysUser = Depends(require_permission("menu:delete")),
    db: Session = Depends(get_db),
):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")

    children = db.query(SysMenu).filter(SysMenu.parent_id == menu_id).first()
    if children:
        raise HTTPException(status_code=400, detail="该菜单下有子菜单，无法删除")

    db.delete(menu)
    db.commit()
    return ResponseModel(message="删除成功")
