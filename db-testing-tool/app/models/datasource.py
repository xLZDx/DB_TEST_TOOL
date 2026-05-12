"""DataSource model stub."""
from sqlalchemy import Column, Integer, String, Text, Boolean
from app.database import Base


class DataSource(Base):
    """DataSource model - stub for unblocking app startup."""
    __tablename__ = "datasources"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    db_type = Column(String(50), nullable=False)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    password = Column(Text, nullable=True)
    extra_params = Column(Text, nullable=True)
    status = Column(String(50), default="unknown")
    is_active = Column(Boolean, default=True)
    last_tested_at = Column(Text, nullable=True)
