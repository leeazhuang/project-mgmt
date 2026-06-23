from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BizBug(Base):
    __tablename__ = "biz_bug"
    __table_args__ = {"comment": "Bug缺陷表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(Integer, ForeignKey("biz_project.id"), nullable=False, comment="所属项目ID")
    title = Column(String(200), nullable=False, comment="Bug标题")
    description = Column(Text, default="", comment="Bug描述/复现步骤")
    status = Column(String(20), default="pending", comment="状态：pending待处理/assigned已指派/fixing修复中/fixed已修复/verified已验证/rejected已驳回/reopened重新打开")
    severity = Column(String(20), default="minor", comment="严重程度：critical致命/major严重/minor一般/trivial轻微")
    priority = Column(String(20), default="medium", comment="优先级：urgent紧急/high高/medium中/low低")
    creator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="创建人ID")
    assignee_id = Column(Integer, ForeignKey("sys_user.id"), nullable=True, comment="处理人ID")
    assignee_display_tag = Column(String(64), nullable=False, default="", server_default="", comment="分配时选的展示标签快照，受限角色只见此标签")
    reject_reason = Column(Text, default="", comment="驳回原因")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    resolved_at = Column(DateTime, nullable=True, comment="修复时间")
    closed_at = Column(DateTime, nullable=True, comment="关闭时间")

    project = relationship("BizProject")
    creator = relationship("SysUser", foreign_keys=[creator_id])
    assignee = relationship("SysUser", foreign_keys=[assignee_id])


class BizBugLog(Base):
    """Bug流转记录"""
    __tablename__ = "biz_bug_log"
    __table_args__ = {"comment": "Bug流转记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    bug_id = Column(Integer, ForeignKey("biz_bug.id"), nullable=False, comment="Bug ID")
    operator_id = Column(Integer, ForeignKey("sys_user.id"), nullable=False, comment="操作人ID")
    action = Column(String(30), nullable=False, comment="动作：create创建/assign指派/reject驳回/start_fix开始修复/fixed修复完成/verify_pass验证通过/verify_fail验证不通过/reassign改派")
    remark = Column(Text, default="", comment="备注说明")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    bug = relationship("BizBug")
    operator = relationship("SysUser", foreign_keys=[operator_id])
