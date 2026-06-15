from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BizComment(Base):
    __tablename__ = "biz_comment"
    __table_args__ = {"comment": "评论表（需求/任务/Bug通用）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    target_id = Column(Integer, nullable=False, comment="关联业务ID")
    target_type = Column(String(20), nullable=False, comment="关联业务类型：requirement需求/task任务/bug缺陷")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="评论人ID")
    content = Column(Text, nullable=False, comment="评论内容")
    parent_id = Column(Integer, default=None, nullable=True, comment="父评论ID（回复用）")
    mention_user_ids = Column(String(500), default="", comment="被@的用户ID列表，逗号分隔")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    user = relationship("SysUser")
