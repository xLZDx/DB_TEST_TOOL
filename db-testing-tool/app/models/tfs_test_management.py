"""TFS Test Management models."""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, UniqueConstraint
)
from app.database import Base


class TfsTestManagement(Base):
    """Legacy stub — kept to avoid Alembic table conflicts."""
    __tablename__ = "tfs_test_management"

    id = Column(Integer, primary_key=True)
    test_plan_id = Column(Integer, nullable=True)
    test_suite_id = Column(Integer, nullable=True)
    test_case_id = Column(Integer, nullable=True)
    status = Column(String(50), default="Not Run")


class TfsTestPlan(Base):
    __tablename__ = "tfs_test_plans"
    __table_args__ = (UniqueConstraint("plan_id", "project", name="uq_plan_project"),)

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, nullable=False)
    name = Column(String(512), nullable=False, default="")
    project = Column(String(255), nullable=False)
    state = Column(String(100), default="Active")
    description = Column(Text, nullable=True)
    area_path = Column(String(512), nullable=True)
    iteration_path = Column(String(512), nullable=True)
    owner = Column(String(255), nullable=True)
    created_date = Column(DateTime(timezone=True), nullable=True)
    root_suite_id = Column(Integer, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)


class TfsTestSuite(Base):
    __tablename__ = "tfs_test_suites"
    __table_args__ = (UniqueConstraint("suite_id", "project", name="uq_suite_project"),)

    id = Column(Integer, primary_key=True)
    suite_id = Column(Integer, nullable=False)
    plan_id = Column(Integer, nullable=False)
    parent_suite_id = Column(Integer, nullable=True)
    name = Column(String(512), nullable=False, default="")
    project = Column(String(255), nullable=False)
    suite_type = Column(String(100), default="StaticTestSuite")
    test_case_count = Column(Integer, default=0)
    is_heavy = Column(Boolean, default=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)


class TfsTestPoint(Base):
    __tablename__ = "tfs_test_points"
    __table_args__ = (UniqueConstraint("test_point_id", "project", name="uq_point_project"),)

    id = Column(Integer, primary_key=True)
    test_point_id = Column(Integer, nullable=False)
    test_case_id = Column(Integer, nullable=True)
    suite_id = Column(Integer, nullable=True)
    plan_id = Column(Integer, nullable=True)
    project = Column(String(255), nullable=False)
    title = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    state = Column(String(100), default="Active")
    priority = Column(Integer, default=3)
    automation_status = Column(String(100), nullable=True)
    owner = Column(String(255), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)


class TfsTestRun(Base):
    __tablename__ = "tfs_test_runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, nullable=False, unique=True)
    plan_id = Column(Integer, nullable=True)
    name = Column(String(512), nullable=True)
    project = Column(String(255), nullable=False)
    environment = Column(String(255), nullable=True)
    state = Column(String(100), default="NotStarted")
    total_tests = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    blocked_count = Column(Integer, default=0)
    not_run_count = Column(Integer, default=0)
    test_point_ids = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class TfsTestResult(Base):
    __tablename__ = "tfs_test_results"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, nullable=False)
    test_point_id = Column(Integer, nullable=True)
    test_case_id = Column(Integer, nullable=True)
    outcome = Column(String(100), nullable=True)
    comment = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    state = Column(String(100), default="Active")
