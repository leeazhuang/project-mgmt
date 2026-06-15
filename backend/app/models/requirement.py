from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BizRequirement(Base):
    __tablename__ = "biz_requirement"
    __table_args__ = {"comment": "需求表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, ForeignKey("biz_project.id"), nullable=False, comment="所属项目ID")
    title = Column(String(200), nullable=False, comment="需求标题")
    description = Column(Text, default="", comment="需求描述")
    status = Column(String(20), default="draft", comment="状态：draft草稿/pending待审批/approved已通过/rejected已拒绝/developing开发中/done已完成/closed已关闭")
    priority = Column(String(20), default="medium", comment="优先级：urgent紧急/high高/medium中/low低")
    creator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="创建人ID")
    reject_reason = Column(Text, default="", comment="拒绝原因")
    deadline = Column(Date, nullable=True, comment="期望截止日期")
    estimated_deadline = Column(Date, nullable=True, comment="预计截止时间，由技术负责人设置")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    project = relationship("BizProject")
    creator = relationship("SysUser")
    tasks = relationship("BizTask", back_populates="requirement")


class BizApprovalLog(Base):
    __tablename__ = "biz_approval_log"
    __table_args__ = {"comment": "需求审批记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    requirement_id = Column(Integer, ForeignKey("biz_requirement.id"), nullable=False, comment="需求ID")
    operator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="操作人ID")
    action = Column(String(20), nullable=False, comment="动作：submit提交/approve通过/reject拒绝")
    remark = Column(Text, default="", comment="备注说明")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    operator = relationship("SysUser")
