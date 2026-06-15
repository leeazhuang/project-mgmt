from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BizProject(Base):
    __tablename__ = "biz_project"
    __table_args__ = {"comment": "项目表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(100), nullable=False, comment="项目名称")
    description = Column(Text, default="", comment="项目描述")
    status = Column(String(20), default="active", comment="状态：active进行中/archived已归档/suspended已暂停")
    owner_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="项目负责人ID")
    tech_leader_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="技术负责人ID")
    creator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="创建人ID")
    start_date = Column(Date, nullable=True, comment="项目开始日期")
    end_date = Column(Date, nullable=True, comment="项目结束日期")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    owner = relationship("SysUser", foreign_keys=[owner_id])
    tech_leader = relationship("SysUser", foreign_keys=[tech_leader_id])
    creator = relationship("SysUser", foreign_keys=[creator_id])
    members = relationship("BizProjectMember", back_populates="project", cascade="all, delete-orphan")


class BizProjectMember(Base):
    __tablename__ = "biz_project_member"
    __table_args__ = {"comment": "项目成员表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, ForeignKey("biz_project.id"), nullable=False, comment="项目ID")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="成员用户ID")
    joined_at = Column(DateTime, default=datetime.now, comment="加入时间")

    project = relationship("BizProject", back_populates="members")
    user = relationship("SysUser")
