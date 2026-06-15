from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class SysOperationLog(Base):
    __tablename__ = "sys_operation_log"
    __table_args__ = {"comment": "操作日志表（全局中间件自动记录写操作）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=True, comment="操作人ID（登录等无token操作为空）")
    module = Column(String(50), default="", comment="操作模块：user/role/menu/project/requirement/task/bug/worklog/system等")
    action = Column(String(20), default="", comment="操作类型：create新增/update修改/delete删除/login登录等")
    target_id = Column(Integer, default=0, comment="操作目标ID")
    target_type = Column(String(50), default="", comment="操作目标类型")
    before_data = Column(JSON, nullable=True, comment="变更前数据（JSON）")
    after_data = Column(JSON, nullable=True, comment="请求信息（JSON：method/path/status）")
    ip_address = Column(String(50), default="", comment="操作IP地址")
    user_agent = Column(String(500), default="", comment="浏览器User-Agent")
    created_at = Column(DateTime, default=datetime.now, comment="操作时间")

    user = relationship("SysUser")
