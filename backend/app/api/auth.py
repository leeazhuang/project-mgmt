from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.user import LoginRequest, LoginResponse, UserInfo
from app.services.auth_service import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _build_menu_tree(menus: list, parent_id: int = 0) -> list:
    tree = []
    for menu in menus:
        if menu.parent_id == parent_id:
            node = {
                "id": menu.id,
                "parent_id": menu.parent_id,
                "name": menu.name,
                "type": menu.type,
                "path": menu.path,
                "component": menu.component,
                "permission_code": menu.permission_code,
                "icon": menu.icon,
                "sort_order": menu.sort_order,
                "is_visible": menu.is_visible,
                "children": _build_menu_tree(menus, menu.id),
            }
            tree.append(node)
    tree.sort(key=lambda x: x["sort_order"])
    return tree


@router.post("/login", response_model=ResponseModel[LoginResponse])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(SysUser).filter(SysUser.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.is_enabled != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(user.id)
    data = LoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        real_name=user.real_name,
    )
    return ResponseModel(data=data)


@router.get("/userinfo", response_model=ResponseModel[UserInfo])
def get_userinfo(current_user: SysUser = Depends(get_current_user)):
    role_codes = [r.code for r in current_user.roles]
    permissions = set()
    all_menus = []
    seen_menu_ids = set()

    for role in current_user.roles:
        for menu in role.menus:
            if menu.permission_code:
                permissions.add(menu.permission_code)
            if menu.id not in seen_menu_ids and menu.is_enabled == 1:
                all_menus.append(menu)
                seen_menu_ids.add(menu.id)

    menu_tree = _build_menu_tree(all_menus)

    data = UserInfo(
        id=current_user.id,
        username=current_user.username,
        real_name=current_user.real_name,
        avatar=current_user.avatar or "",
        roles=role_codes,
        permissions=list(permissions),
        menus=menu_tree,
    )
    return ResponseModel(data=data)
