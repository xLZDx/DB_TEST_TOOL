"""MappingRule model."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class MappingRule(Base):
    __tablename__ = "mapping_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    source_datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False)
    source_schema = Column(String(200), nullable=True)
    source_table = Column(String(200), nullable=False)
    source_columns = Column(Text, nullable=True)          # JSON array
    target_datasource_id = Column(Integer, ForeignKey("datasources.id"), nullable=False)
    target_schema = Column(String(200), nullable=True)
    target_table = Column(String(200), nullable=False)
    target_columns = Column(Text, nullable=True)          # JSON array
    transformation_sql = Column(Text, nullable=True)
    join_condition = Column(Text, nullable=True)
    filter_condition = Column(Text, nullable=True)
    rule_type = Column(String(100), default="direct")     # direct|aggregation|lookup|scd|custom
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    source_datasource = relationship("DataSource", foreign_keys=[source_datasource_id])
    target_datasource = relationship("DataSource", foreign_keys=[target_datasource_id])
