"""Regression Lab catalog models."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class RegressionCatalogItem(Base):
    """Indexed TFS test case metadata for regression discovery and validation."""

    __tablename__ = "regression_catalog_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project = Column(String(200), nullable=False)
    plan_id = Column(Integer, nullable=True)
    plan_name = Column(String(500), nullable=True)
    suite_id = Column(Integer, nullable=True)
    suite_name = Column(String(500), nullable=True)
    suite_path = Column(Text, nullable=True)
    parent_suite_id = Column(Integer, nullable=True)
    test_point_id = Column(Integer, nullable=True)
    test_case_id = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    work_item_type = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    priority = Column(Integer, nullable=True)
    owner = Column(String(200), nullable=True)
    automation_status = Column(String(100), nullable=True)
    area_path = Column(String(500), nullable=True)
    iteration_path = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)
    description_text = Column(Text, nullable=True)
    steps_text = Column(Text, nullable=True)
    expected_results_text = Column(Text, nullable=True)
    attachment_names_json = Column(Text, nullable=True)
    attachment_text = Column(Text, nullable=True)
    hyperlink_urls_json = Column(Text, nullable=True)
    linked_requirement_ids_json = Column(Text, nullable=True)
    linked_requirement_titles_json = Column(Text, nullable=True)
    sql_candidates_json = Column(Text, nullable=True)
    test_case_web_url = Column(Text, nullable=True)
    test_plan_web_url = Column(Text, nullable=True)
    test_suite_web_url = Column(Text, nullable=True)
    created_date = Column(DateTime, nullable=True)
    changed_date = Column(DateTime, nullable=True)
    domain_group = Column(String(100), nullable=True)
    domain_context = Column(String(200), nullable=True)
    validation_status = Column(String(50), nullable=True)
    validation_score = Column(Integer, nullable=True)
    validation_summary = Column(Text, nullable=True)
    validation_details_json = Column(Text, nullable=True)
    promoted_local_test_count = Column(Integer, default=0)
    indexed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RegressionLabConfig(Base):
    """Per-project Regression Lab settings (defaults, exclusions, and time window)."""

    __tablename__ = "regression_lab_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project = Column(String(200), nullable=False, unique=True)
    default_area_paths_json = Column(Text, nullable=True)
    default_iteration_paths_json = Column(Text, nullable=True)
    exclusion_keywords_json = Column(Text, nullable=True)
    excluded_item_ids_json = Column(Text, nullable=True)
    excluded_plan_ids_json = Column(Text, nullable=True)
    excluded_suite_ids_json = Column(Text, nullable=True)
    min_changed_date = Column(DateTime, nullable=True)
    include_archived = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
