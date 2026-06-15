from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BizAttachment(Base):
    __tablename__ = "biz_attachment"
    __table_args__ = {"comment": "附件表（需求/任务/Bug/评论通用）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    target_id = Column(Integer, nullable=False, comment="关联业务ID")
    target_type = Column(String(20), nullable=False, comment="关联业务类型：requirement需求/task任务/bug缺陷/comment评论")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    file_size = Column(BigInteger, default=0, comment="文件大小（字节）")
    file_type = Column(String(100), default="", comment="文件MIME类型")
    storage = Column(String(10), default="local", comment="存储方式：local本地/oss阿里云OSS")
    uploader_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="上传人ID")
    created_at = Column(DateTime, default=datetime.now, comment="上传时间")

    uploader = relationship("SysUser")
