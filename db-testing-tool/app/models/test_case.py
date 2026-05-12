"""TestCase, TestRun, TestFolder, TestCaseFolder models."""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    test_type = Column(String(50), nullable=False)
    source_datasource_id = Column(Integer, nullable=True)
    target_datasource_id = Column(Integer, nullable=True)
    mapping_rule_id = Column(Integer, nullable=True)
    source_query = Column(Text, nullable=True)
    target_query = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    tolerance = Column(Float, default=0.0)
    severity = Column(String(50), default="medium")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_ai_generated = Column(Boolean, default=False)
    mapping_table = Column(String(255), nullable=True)
    source_filter = Column(Text, nullable=True)
    target_filter = Column(Text, nullable=True)


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, nullable=False)
    batch_id = Column(String(50), nullable=True)
    status = Column(String(50), default="running")
    mismatch_count = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    actual_result = Column(Text, nullable=True)
    source_result = Column(Text, nullable=True)
    target_result = Column(Text, nullable=True)
    mismatch_sample = Column(Text, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=True)


class TestFolder(Base):
    __tablename__ = "test_folders"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)


class TestCaseFolder(Base):
    __tablename__ = "test_case_folders"
    __table_args__ = (UniqueConstraint("test_case_id", "folder_id", name="uq_tc_folder"),)

    id = Column(Integer, primary_key=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    folder_id = Column(Integer, ForeignKey("test_folders.id", ondelete="CASCADE"), nullable=False)
