from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from app.database import Base


class SysConfig(Base):
    """系统配置表 - 键值对存储"""
    __tablename__ = "sys_config"
    __table_args__ = {"comment": "系统配置表（键值对）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    config_key = Column(String(100), unique=True, nullable=False, comment="配置键")
    config_value = Column(Text, default="", comment="配置值")
    description = Column(String(200), default="", comment="配置说明")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
