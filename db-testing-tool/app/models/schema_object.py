"""SchemaObject and related model stubs."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class SchemaObject(Base):
    """Schema object model - stub for unblocking app startup."""
    __tablename__ = "schema_objects"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    object_type = Column(String(50), nullable=False)
    datasource_id = Column(Integer, nullable=True)
    definition = Column(Text, nullable=True)


class ColumnProfile(Base):
    """Column profile model - stub."""
    __tablename__ = "column_profiles"
    
    id = Column(Integer, primary_key=True)
    column_name = Column(String(255), nullable=False)
    schema_object_id = Column(Integer, nullable=True)


class LineageEdge(Base):
    """Lineage edge model - stub."""
    __tablename__ = "lineage_edges"
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, nullable=True)
    target_id = Column(Integer, nullable=True)
