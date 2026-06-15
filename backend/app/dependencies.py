from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser
from app.services.auth_service import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> SysUser:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的token")
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if user is None or user.is_enabled != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def require_permission(permission_code: str):
    def checker(current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
        role_codes = [r.code for r in current_user.roles]
        if "super_admin" in role_codes:
            return current_user

        user_permissions = set()
        for role in current_user.roles:
            for menu in role.menus:
                if menu.permission_code:
                    user_permissions.add(menu.permission_code)

        if permission_code not in user_permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有操作权限")
        return current_user

    return checker
