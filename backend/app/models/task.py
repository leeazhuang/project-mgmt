from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship

from app.database import Base


class BizTask(Base):
    __tablename__ = "biz_task"
    __table_args__ = {"comment": "任务表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, ForeignKey("biz_project.id"), nullable=False, comment="所属项目ID")
    requirement_id = Column(Integer, ForeignKey("biz_requirement.id"), nullable=False, comment="所属需求ID")
    title = Column(String(200), nullable=False, comment="任务标题")
    description = Column(Text, default="", comment="任务描述")
    status = Column(String(20), default="pending", comment="状态：pending待开始/in_progress进行中/done已完成/voided已作废")
    priority = Column(String(20), default="medium", comment="优先级：urgent紧急/high高/medium中/low低")
    assignee_id = Column(Integer, ForeignKey("sys_user.id"), nullable=True, comment="主负责人ID（兼容单人任务）")
    assigner_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="指派人ID")
    estimated_hours = Column(DECIMAL(6, 1), default=0, comment="预估工时（小时）")
    actual_hours = Column(DECIMAL(6, 1), default=0, comment="实际工时（小时）")
    planned_start_date = Column(Date, nullable=True, comment="预计开始日期")
    start_date = Column(DateTime, nullable=True, comment="实际开始时间，点击开始时记录")
    end_date = Column(Date, nullable=True, comment="截止日期")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    project = relationship("BizProject")
    requirement = relationship("BizRequirement", back_populates="tasks")
    assignee = relationship("SysUser", foreign_keys=[assignee_id])
    assigner = relationship("SysUser", foreign_keys=[assigner_id])
    assignees = relationship("BizTaskAssignee", back_populates="task", cascade="all, delete-orphan")


class BizTaskAssignee(Base):
    """多人任务子表 - 每个被分配人独立状态"""
    __tablename__ = "biz_task_assignee"
    __table_args__ = {"comment": "任务多人指派子表（每人独立状态）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    task_id = Column(Integer, ForeignKey("biz_task.id"), nullable=False, comment="任务ID")
    user_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="被指派人ID")
    display_tag = Column(String(64), nullable=False, default="", server_default="", comment="分配时选的展示标签快照，受限角色只见此标签")
    status = Column(String(20), default="pending", comment="个人状态：pending待开始/in_progress进行中/done已完成")
    start_date = Column(DateTime, nullable=True, comment="该人实际开始时间")
    completed_at = Column(DateTime, nullable=True, comment="该人完成时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    task = relationship("BizTask", back_populates="assignees")
    user = relationship("SysUser")


class BizTaskLog(Base):
    """任务流转记录 / 延期记录"""
    __tablename__ = "biz_task_log"
    __table_args__ = {"comment": "任务流转/延期记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    task_id = Column(Integer, ForeignKey("biz_task.id"), nullable=False, comment="任务ID")
    operator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="操作人ID")
    action = Column(String(30), nullable=False, comment="动作：create创建/start开始/done完成/delay延期/reassign改派/reopen重开/update更新")
    remark = Column(Text, default="", comment="备注说明")
    old_value = Column(String(200), default="", comment="变更前的值，如旧截止日期")
    new_value = Column(String(200), default="", comment="变更后的值，如新截止日期")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    task = relationship("BizTask")
    operator = relationship("SysUser", foreign_keys=[operator_id])
