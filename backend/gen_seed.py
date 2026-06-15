# -*- coding: utf-8 -*-
"""
从当前数据库导出"系统初始化种子数据" → app/seed_data.sql
导出内容（反映当前最新状态）：
- sys_menu      全部菜单
- sys_role      全部角色
- sys_role_menu 角色-菜单权限关联
- sys_user      仅超级管理员 admin
- sys_user_role admin 的角色关联
- sys_config    全部配置项（值清空，仅保留 key/description）

业务数据（项目/需求/任务/Bug等）不导出，由 create_all 建空表。
菜单/角色变动后重新运行本脚本即可刷新种子。
"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
from app.config import settings

conn = pymysql.connect(
    host=settings.DB_HOST, port=settings.DB_PORT,
    user=settings.DB_USER, password=settings.DB_PASSWORD,
    database=settings.DB_NAME, charset='utf8mb4',
)
cur = conn.cursor()


def dump(table, where='', value_override=None):
    cur.execute(f"SELECT * FROM {table} {where}")
    cols = [d[0] for d in cur.description]
    lines = [f"-- {table}"]
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        if value_override:
            value_override(d)
        vals = ', '.join(conn.escape(d[c]) for c in cols)
        col_list = ', '.join(f"`{c}`" for c in cols)
        lines.append(f"INSERT INTO `{table}` ({col_list}) VALUES ({vals});")
    return lines


def clear_config(d):
    # config 值清空：保留 key 与说明，值留空（oss_enabled 给默认 false）
    if d.get('config_key') == 'oss_enabled':
        d['config_value'] = 'false'
    else:
        d['config_value'] = ''


out = ["-- 系统初始化种子数据（自动生成，请勿手改；改菜单/角色后重跑 gen_seed.py）"]
out += dump('sys_menu')
out += dump('sys_role')
def _clear_admin_bind(d):
    for k in ('wx_room_id', 'wx_user_id', 'wx_user_name', 'wx_room_name'):
        if k in d:
            d[k] = ''
out += dump('sys_user', "WHERE username='admin'", value_override=_clear_admin_bind)
out += dump('sys_role_menu')
out += dump('sys_user_role', "WHERE user_id IN (SELECT id FROM sys_user WHERE username='admin')")
out += dump('sys_config', value_override=clear_config)

seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'seed_data.sql')
with open(seed_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')

cur.close()
conn.close()
print(f"种子数据已生成: {seed_path}")
print(f"共 {len([l for l in out if l.startswith('INSERT')])} 条 INSERT")
