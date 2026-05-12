"""Test case, run, and folder models."""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    test_type = Column(String(100), nullable=False)  # custom_sql | row_count | null_check | value_match
    source_datasource_id = Column(Integer, nullable=True)
    target_datasource_id = Column(Integer, nullable=True)
    source_query = Column(Text, nullable=True)
    target_query = Column(Text, nullable=True)
    expected_result = Column(Text, nullable=True)
    tolerance = Column(Float, default=0.0)
    severity = Column(String(50), default="medium")
    is_active = Column(Boolean, default=True)
    is_ai_generated = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    runs = relationship("TestRun", back_populates="test_case", cascade="all, delete-orphan")


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    batch_id = Column(String(100), nullable=True)
    status = Column(String(50), default="pending")  # pending | running | passed | failed | error
    source_result = Column(Text, nullable=True)
    target_result = Column(Text, nullable=True)
    actual_result = Column(Text, nullable=True)
    mismatch_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    test_case = relationship("TestCase", back_populates="runs")


class TestFolder(Base):
    __tablename__ = "test_folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TestCaseFolder(Base):
    __tablename__ = "test_case_folders"

    test_case_id = Column(Integer, ForeignKey("test_cases.id"), primary_key=True)
    folder_id = Column(Integer, ForeignKey("test_folders.id"), nullable=False)
