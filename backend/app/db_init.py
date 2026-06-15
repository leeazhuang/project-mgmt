"""
启动时数据库自动初始化：
1. 数据库不存在 → 自动创建
2. 建所有表（create_all）
3. 空库（无任何用户）→ 导入系统种子数据（超管 admin / 角色 / 菜单 / 权限 / config 空值）

别人部署只需提供数据库连接地址、账号密码、库名，启动容器即开箱即用。
"""
import os
import logging

from sqlalchemy import create_engine, text

from app.config import settings
from app.database import engine, SessionLocal, Base

logger = logging.getLogger(__name__)

_SEED_FILE = os.path.join(os.path.dirname(__file__), "seed_data.sql")


def _ensure_database():
    """目标数据库不存在则创建（用不带库名的连接）"""
    server_url = (
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/?charset=utf8mb4"
    )
    tmp_engine = create_engine(server_url)
    try:
        with tmp_engine.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            ))
            conn.commit()
        logger.info(f"数据库 {settings.DB_NAME} 已就绪")
    finally:
        tmp_engine.dispose()


def _seed_if_empty():
    """库里没有任何用户时，导入种子数据（超管/角色/菜单/config）"""
    from app.models.user import SysUser
    db = SessionLocal()
    try:
        if db.query(SysUser).count() > 0:
            return  # 已有数据，跳过初始化
    finally:
        db.close()

    if not os.path.exists(_SEED_FILE):
        logger.warning("未找到种子文件 seed_data.sql，跳过初始化")
        return

    with open(_SEED_FILE, encoding="utf-8") as f:
        content = f.read()

    # 按分号拆分逐条执行，过滤注释行；用 exec_driver_sql 避免 SQLAlchemy 解析 % 占位符
    statements = []
    for raw in content.split(";"):
        body = "\n".join(
            line for line in raw.splitlines() if not line.strip().startswith("--")
        ).strip()
        if body:
            statements.append(body)

    with engine.begin() as conn:
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        for stmt in statements:
            conn.exec_driver_sql(stmt)
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")

    logger.info(f"种子数据初始化完成（{len(statements)} 条），默认管理员 admin")


def init_database():
    """容器/服务启动时调用：建库 → 建表 → 按需初始化"""
    _ensure_database()
    import app.models  # noqa: 确保所有模型注册到 Base
    Base.metadata.create_all(bind=engine)
    _seed_if_empty()
