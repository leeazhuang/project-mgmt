"""清除业务数据 + 创建角色 + 分配菜单权限"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.user import SysUser, SysRole, SysMenu, sys_user_role, sys_role_menu
from app.models.project import BizProject, BizProjectMember
from app.models.requirement import BizRequirement, BizApprovalLog
from app.models.task import BizTask
from app.models.bug import BizBug
from app.models.comment import BizComment
from app.models.attachment import BizAttachment
from app.models.work_log import BizWorkLog
from app.models.notification import SysNotification
from app.models.operation_log import SysOperationLog

db = SessionLocal()

# ========== 1. 清除业务数据 ==========
print("清除业务数据...")
db.query(BizWorkLog).delete()
db.query(BizComment).delete()
db.query(BizAttachment).delete()
db.query(BizApprovalLog).delete()
db.query(BizTask).delete()
db.query(BizBug).delete()
db.query(BizRequirement).delete()
db.query(BizProjectMember).delete()
db.query(BizProject).delete()
db.query(SysNotification).delete()
db.query(SysOperationLog).delete()
db.commit()
print("业务数据已清除")

# ========== 2. 修复菜单按钮归属（init_data.py 的 bug） ==========
# 把挂错位置的按钮权限重新归位
print("\n修复菜单按钮归属...")

# 先获取所有菜单
menus = {m.id: m for m in db.query(SysMenu).all()}
menu_by_perm = {m.permission_code: m for m in menus.values() if m.permission_code}

# 找到各个父菜单
user_mgmt = next((m for m in menus.values() if m.name == "用户管理" and m.type == "menu"), None)
role_mgmt = next((m for m in menus.values() if m.name == "角色管理" and m.type == "menu"), None)
menu_mgmt = next((m for m in menus.values() if m.name == "菜单管理" and m.type == "menu"), None)

# 修复按钮归属
fixes = {
    "user:create": user_mgmt,
    "user:update": user_mgmt,
    "user:delete": user_mgmt,
    "role:create": role_mgmt,
    "role:update": role_mgmt,
    "role:delete": role_mgmt,
    "menu:create": menu_mgmt,
    "menu:update": menu_mgmt,
    "menu:delete": menu_mgmt,
}
for perm_code, parent in fixes.items():
    btn = menu_by_perm.get(perm_code)
    if btn and parent and btn.parent_id != parent.id:
        print(f"  修复 {perm_code}: parent {btn.parent_id} -> {parent.id}")
        btn.parent_id = parent.id

db.commit()

# ========== 3. 清除旧角色（保留超级管理员） ==========
print("\n清除旧角色...")
old_roles = db.query(SysRole).filter(SysRole.code != "super_admin").all()
for r in old_roles:
    r.menus = []
    r.users = []
    db.delete(r)
db.commit()

# ========== 4. 获取所有菜单ID ==========
all_menus = db.query(SysMenu).all()
menu_map = {}
for m in all_menus:
    menu_map[m.permission_code or m.name] = m

def get_menu_ids(*keys):
    """根据 permission_code 或 name 获取菜单ID列表，包含其子菜单"""
    ids = set()
    for key in keys:
        m = menu_map.get(key)
        if m:
            ids.add(m.id)
            # 添加所有子菜单
            for child in all_menus:
                if child.parent_id == m.id:
                    ids.add(child.id)
                    # 孙子菜单
                    for grandchild in all_menus:
                        if grandchild.parent_id == child.id:
                            ids.add(grandchild.id)
    return list(ids)

# 首页菜单
home_menu = next((m for m in all_menus if m.name == "首页"), None)
home_id = [home_menu.id] if home_menu else []

# ========== 5. 创建角色并分配菜单 ==========
print("\n创建角色...")

# --- 项目负责人 ---
# 可以看到：首页、项目管理、需求管理（含审批）、任务管理、Bug管理、工时统计
pm_menu_ids = home_id + get_menu_ids(
    "project:list", "project:create", "project:update",
    "requirement:list", "requirement:create",
    "任务管理",  # directory，会包含子菜单
    "task:list", "task:create",
    "bug:list", "bug:create",
    "worklog:list",
)
pm_role = SysRole(name="项目负责人", code="project_owner", description="审批需求，管理项目全局")
db.add(pm_role)
db.flush()
pm_menus = db.query(SysMenu).filter(SysMenu.id.in_(pm_menu_ids)).all()
pm_role.menus = pm_menus
print(f"  项目负责人: {len(pm_menus)} 个菜单")

# --- 技术负责人 ---
# 可以看到：首页、项目管理（只看）、需求管理（只看）、任务管理（含创建）、Bug管理（含分配）、工时统计
tech_menu_ids = home_id + get_menu_ids(
    "project:list",
    "requirement:list",
    "任务管理",
    "task:list", "task:create",
    "bug:list", "bug:create",
    "worklog:list",
)
tech_role = SysRole(name="技术负责人", code="tech_leader", description="分配任务、处理Bug、管理技术团队")
db.add(tech_role)
db.flush()
tech_menus = db.query(SysMenu).filter(SysMenu.id.in_(tech_menu_ids)).all()
tech_role.menus = tech_menus
print(f"  技术负责人: {len(tech_menus)} 个菜单")

# --- 普通成员 ---
# 可以看到：首页、项目管理（只看）、需求管理（可提需求）、任务管理（只看自己的）、Bug管理（可提Bug）、工时统计
member_menu_ids = home_id + get_menu_ids(
    "project:list",
    "requirement:list", "requirement:create",
    "任务管理",
    "task:list",
    "bug:list", "bug:create",
    "worklog:list",
)
member_role = SysRole(name="普通成员", code="member", description="参与开发、提交需求和Bug、填报工时")
db.add(member_role)
db.flush()
member_menus = db.query(SysMenu).filter(SysMenu.id.in_(member_menu_ids)).all()
member_role.menus = member_menus
print(f"  普通成员: {len(member_menus)} 个菜单")

db.commit()

# ========== 6. 给现有用户分配角色 ==========
print("\n给用户分配角色...")
users = db.query(SysUser).all()
admin_role = db.query(SysRole).filter(SysRole.code == "super_admin").first()

for user in users:
    if user.username == "admin":
        # admin 保持超级管理员
        user.roles = [admin_role]
        print(f"  {user.username}({user.real_name}): 超级管理员")
    else:
        # 其他用户先设为普通成员，你可以在前端调整
        user.roles = [member_role]
        print(f"  {user.username}({user.real_name}): 普通成员")

db.commit()

# ========== 7. 汇总 ==========
print("\n" + "=" * 50)
print("重置完成！")
print(f"角色：超级管理员、项目负责人、技术负责人、普通成员")
print(f"所有业务数据已清除（项目/需求/任务/Bug/评论/附件/工时/通知/日志）")
print(f"所有非admin用户已设为普通成员，请在前端管理中分配正确角色")
print("=" * 50)

db.close()
