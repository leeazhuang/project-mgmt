"""初始化超级管理员 + 默认角色 + 基础菜单"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app.models.user import SysUser, SysRole, SysMenu
from app.services.auth_service import hash_password

# 导入所有模型确保表创建
from app.models import *  # noqa


def init():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(SysUser).filter(SysUser.username == "admin").first():
        print("数据已初始化，跳过")
        db.close()
        return

    # 创建超级管理员角色
    admin_role = SysRole(name="超级管理员", code="super_admin", description="拥有所有权限")
    db.add(admin_role)
    db.flush()

    # 创建菜单
    menus_data = [
        {"name": "首页", "type": "menu", "path": "/dashboard", "component": "dashboard/index", "icon": "Monitor", "sort_order": 0},
        {"name": "项目管理", "type": "menu", "path": "/project", "component": "project/index", "icon": "Folder", "sort_order": 1, "permission_code": "project:list"},
        {"name": "需求管理", "type": "menu", "path": "/requirement", "component": "requirement/index", "icon": "Document", "sort_order": 2, "permission_code": "requirement:list"},
        {"name": "任务管理", "type": "directory", "path": "/task", "icon": "List", "sort_order": 3},
        {"name": "Bug管理", "type": "menu", "path": "/bug", "component": "bug/index", "icon": "Warning", "sort_order": 4, "permission_code": "bug:list"},
        {"name": "工时统计", "type": "menu", "path": "/worklog", "component": "worklog/index", "icon": "Timer", "sort_order": 5, "permission_code": "worklog:list"},
        {"name": "系统管理", "type": "directory", "path": "/system", "icon": "Setting", "sort_order": 10},
    ]

    created_menus = []
    for m in menus_data:
        menu = SysMenu(**m)
        db.add(menu)
        db.flush()
        created_menus.append(menu)

    # 任务子菜单
    task_parent = created_menus[3]
    task_children = [
        {"name": "任务列表", "type": "menu", "path": "/task", "component": "task/index", "parent_id": task_parent.id, "sort_order": 0, "permission_code": "task:list"},
        {"name": "任务看板", "type": "menu", "path": "/task/board", "component": "task/board", "parent_id": task_parent.id, "sort_order": 1, "permission_code": "task:list"},
    ]
    for m in task_children:
        menu = SysMenu(**m)
        db.add(menu)
        db.flush()
        created_menus.append(menu)

    # 系统管理子菜单
    sys_parent = created_menus[6]
    sys_children = [
        {"name": "用户管理", "type": "menu", "path": "/system/user", "component": "system/user/index", "parent_id": sys_parent.id, "sort_order": 0, "permission_code": "user:list"},
        {"name": "角色管理", "type": "menu", "path": "/system/role", "component": "system/role/index", "parent_id": sys_parent.id, "sort_order": 1, "permission_code": "role:list"},
        {"name": "菜单管理", "type": "menu", "path": "/system/menu", "component": "system/menu/index", "parent_id": sys_parent.id, "sort_order": 2, "permission_code": "menu:list"},
        {"name": "操作日志", "type": "menu", "path": "/log", "component": "log/index", "parent_id": sys_parent.id, "sort_order": 3, "permission_code": "log:list"},
    ]
    for m in sys_children:
        menu = SysMenu(**m)
        db.add(menu)
        db.flush()
        created_menus.append(menu)

    # 添加按钮级权限
    button_permissions = [
        # 用户管理按钮
        {"name": "新增用户", "type": "button", "permission_code": "user:create", "parent_id": created_menus[7].id},
        {"name": "编辑用户", "type": "button", "permission_code": "user:update", "parent_id": created_menus[7].id},
        {"name": "删除用户", "type": "button", "permission_code": "user:delete", "parent_id": created_menus[7].id},
        # 角色管理按钮
        {"name": "新增角色", "type": "button", "permission_code": "role:create", "parent_id": created_menus[8].id},
        {"name": "编辑角色", "type": "button", "permission_code": "role:update", "parent_id": created_menus[8].id},
        {"name": "删除角色", "type": "button", "permission_code": "role:delete", "parent_id": created_menus[8].id},
        # 菜单管理按钮
        {"name": "新增菜单", "type": "button", "permission_code": "menu:create", "parent_id": created_menus[9].id},
        {"name": "编辑菜单", "type": "button", "permission_code": "menu:update", "parent_id": created_menus[9].id},
        {"name": "删除菜单", "type": "button", "permission_code": "menu:delete", "parent_id": created_menus[9].id},
        # 项目管理按钮
        {"name": "新增项目", "type": "button", "permission_code": "project:create", "parent_id": created_menus[1].id},
        {"name": "编辑项目", "type": "button", "permission_code": "project:update", "parent_id": created_menus[1].id},
        # 需求管理按钮
        {"name": "新增需求", "type": "button", "permission_code": "requirement:create", "parent_id": created_menus[2].id},
        # 任务管理按钮
        {"name": "新增任务", "type": "button", "permission_code": "task:create", "parent_id": created_menus[3].id},
        # Bug管理按钮
        {"name": "新增Bug", "type": "button", "permission_code": "bug:create", "parent_id": created_menus[4].id},
    ]
    for btn in button_permissions:
        menu = SysMenu(**btn)
        db.add(menu)
        db.flush()
        created_menus.append(menu)

    # 超管角色关联所有菜单
    all_menus = db.query(SysMenu).all()
    admin_role.menus = all_menus

    # 创建产品角色
    product_role = SysRole(name="产品", code="product", description="可查看需求和任务列表，不可编辑任务")
    db.add(product_role)
    db.flush()

    # 产品角色可访问的菜单：首页、项目管理、需求管理、任务列表（只读）、Bug管理
    product_menu_names = ["首页", "项目管理", "需求管理", "任务管理", "任务列表", "Bug管理",
                          "新增需求", "审批需求", "新增Bug"]
    product_menus = db.query(SysMenu).filter(SysMenu.name.in_(product_menu_names)).all()
    product_role.menus = product_menus

    # 创建Bug反馈角色
    bug_reporter_role = SysRole(name="Bug反馈", code="bug_reporter", description="只能提交和查看Bug")
    db.add(bug_reporter_role)
    db.flush()

    # Bug反馈角色可访问的菜单：首页、项目管理、Bug管理
    bug_menu_names = ["首页", "项目管理", "Bug管理", "新增Bug"]
    bug_menus = db.query(SysMenu).filter(SysMenu.name.in_(bug_menu_names)).all()
    bug_reporter_role.menus = bug_menus

    # 创建管理员用户
    admin = SysUser(
        username="admin",
        password_hash=hash_password("admin123"),
        real_name="超级管理员",
    )
    admin.roles.append(admin_role)
    db.add(admin)

    db.commit()
    print("=" * 50)
    print("初始化完成！")
    print("管理员账号: admin")
    print("管理员密码: admin123")
    print("=" * 50)
    db.close()


if __name__ == "__main__":
    init()
