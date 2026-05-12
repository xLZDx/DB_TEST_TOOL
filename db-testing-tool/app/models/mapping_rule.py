"""MappingRule model stub."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class MappingRule(Base):
    """Mapping rule model - stub for unblocking app startup."""
    __tablename__ = "mapping_rules"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    source_column = Column(String(255), nullable=True)
    target_column = Column(String(255), nullable=True)
    transformation_logic = Column(Text, nullable=True)
    is_active = Column(String(1), default="Y")
