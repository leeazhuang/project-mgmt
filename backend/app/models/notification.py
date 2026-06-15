from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, SmallInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SysNotification(Base):
    __tablename__ = "sys_notification"
    __table_args__ = {"comment": "站内通知表（已改为机器人群艾特，本表保留历史数据）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="接收人ID")
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, default="", comment="通知内容")
    type = Column(String(20), default="system", comment="通知类型：approval审批/task任务/bug缺陷/comment评论/system系统")
    related_id = Column(Integer, default=0, comment="关联业务ID")
    related_type = Column(String(20), default="", comment="关联业务类型：requirement/task/bug/project")
    is_read = Column(SmallInteger, default=0, comment="是否已读：0未读/1已读")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    user = relationship("SysUser")
