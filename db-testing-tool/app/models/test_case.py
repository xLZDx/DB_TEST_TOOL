"""TestCase and TestRun model stubs."""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime
from app.database import Base


class TestCase(Base):
    """Test case model - stub for unblocking app startup."""
    __tablename__ = "test_cases"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    test_type = Column(String(50), nullable=False)
    source_datasource_id = Column(Integer, nullable=True)
    target_datasource_id = Column(Integer, nullable=True)
    source_query = Column(Text, nullable=True)
    target_query = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    tolerance = Column(Float, default=0.0)
    severity = Column(String(50), default="medium")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_ai_generated = Column(Boolean, default=False)


class TestRun(Base):
    """Test run/execution result model - stub."""
    __tablename__ = "test_runs"
    
    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, nullable=False)
    batch_id = Column(String(50), nullable=True)
    status = Column(String(50), default="running")
    mismatch_count = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    actual_result = Column(Text, nullable=True)
