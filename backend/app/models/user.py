from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, SmallInteger, Table, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


sys_user_role = Table(
    "sys_user_role",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, comment="主键ID"),
    Column("user_id", Integer, ForeignKey("sys_user.id"), nullable=False, comment="用户ID"),
    Column("role_id", Integer, ForeignKey("sys_role.id"), nullable=False, comment="角色ID"),
    comment="用户-角色关联表",
)

sys_role_menu = Table(
    "sys_role_menu",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True, comment="主键ID"),
    Column("role_id", Integer, ForeignKey("sys_role.id"), nullable=False, comment="角色ID"),
    Column("menu_id", Integer, ForeignKey("sys_menu.id"), nullable=False, comment="菜单ID"),
    comment="角色-菜单权限关联表",
)


class SysUser(Base):
    __tablename__ = "sys_user"
    __table_args__ = {"comment": "系统用户表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    username = Column(String(50), unique=True, nullable=False, comment="登录用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    real_name = Column(String(50), nullable=False, comment="真实姓名")
    wx_room_id = Column(String(64), default="", comment="机器人通知群ID")
    wx_room_name = Column(String(64), default="", comment="绑定群名称(回显)")
    wx_user_id = Column(String(64), default="", comment="机器人通知群成员ID")
    wx_user_name = Column(String(64), default="", comment="群成员昵称(回显)")
    avatar = Column(String(255), default="", comment="头像URL")
    is_enabled = Column(SmallInteger, default=1, comment="是否启用：0禁用/1启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    roles = relationship("SysRole", secondary=sys_user_role, back_populates="users")


class SysRole(Base):
    __tablename__ = "sys_role"
    __table_args__ = {"comment": "系统角色表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(50), nullable=False, comment="角色名称")
    code = Column(String(50), unique=True, nullable=False, comment="角色编码，如super_admin")
    description = Column(String(255), default="", comment="角色描述")
    is_enabled = Column(SmallInteger, default=1, comment="是否启用：0禁用/1启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    users = relationship("SysUser", secondary=sys_user_role, back_populates="roles")
    menus = relationship("SysMenu", secondary=sys_role_menu, back_populates="roles")


class SysMenu(Base):
    __tablename__ = "sys_menu"
    __table_args__ = {"comment": "系统菜单/权限表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    parent_id = Column(Integer, default=0, comment="父菜单ID，0为顶级")
    name = Column(String(50), nullable=False, comment="菜单名称")
    type = Column(String(20), nullable=False, comment="类型：directory目录/menu菜单/button按钮")
    path = Column(String(200), default="", comment="前端路由路径")
    component = Column(String(200), default="", comment="前端组件路径")
    permission_code = Column(String(100), default="", comment="权限标识，如task:list")
    icon = Column(String(50), default="", comment="菜单图标")
    sort_order = Column(Integer, default=0, comment="排序号")
    is_visible = Column(SmallInteger, default=1, comment="是否显示：0隐藏/1显示")
    is_enabled = Column(SmallInteger, default=1, comment="是否启用：0禁用/1启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    roles = relationship("SysRole", secondary=sys_role_menu, back_populates="menus")
