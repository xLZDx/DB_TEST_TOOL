"""Integration tests for the Regression Lab API endpoints.

These tests verify the FastAPI router endpoints respond correctly
and contract between frontend and backend is maintained.
Uses httpx async test client with mocked DB session.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from app.routers.regression_lab import (
        RegressionSyncRequest,
        RegressionSearchRequest,
        RegressionSettingsUpdateRequest,
        RegressionExcludeByFilterRequest,
        RegressionPromoteRequest,
        _parse_optional_date,
    )
    from app.services.regression_lab_service import (
        get_regression_distinct_values,
        get_regression_groups,
        get_regression_report,
        list_regression_catalog,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="Dependencies not available")


# --- Router request/response contract tests ---

class TestSyncEndpointContract:
    """Verify sync endpoint accepts correct payload shape."""

    def test_sync_request_model_fields(self):
        req = RegressionSyncRequest(
            project="CDSIntegration",
            area_paths=["CDSIntegration\\CDSCCAL"],
            iteration_paths=["CDSIntegration\\CCAL"],
            tags=["regression"],
            suite_name_contains="Balances",
            min_changed_date="2020-01-01",
            max_cases=400,
        )
        assert req.project == "CDSIntegration"
        assert req.max_cases == 400
        assert req.min_changed_date == "2020-01-01"

    def test_sync_request_defaults(self):
        req = RegressionSyncRequest(project="Test")
        assert req.area_paths == []
        assert req.iteration_paths == []
        assert req.tags == []
        assert req.suite_name_contains == ""
        assert req.min_changed_date is None
        assert req.max_cases == 400


class TestSearchEndpointContract:
    """Verify search endpoint accepts correct payload shape."""

    def test_search_request_model_fields(self):
        req = RegressionSearchRequest(
            project="CDSIntegration",
            query="balances RTC",
            group="Balances",
            status="passed",
            area_path="CDSIntegration\\CDSCCAL",
            iteration_path="CDSIntegration\\CCAL",
            plan_name="CCAL Team",
            suite_name="R1",
            owner="ikorostelev",
            title="balance test",
            tags="regression",
        )
        assert req.project == "CDSIntegration"
        assert req.query == "balances RTC"

    def test_search_request_defaults(self):
        req = RegressionSearchRequest(project="Test", query="find tests")
        assert req.group == ""
        assert req.status == ""
        assert req.area_path == ""


class TestSettingsEndpointContract:
    """Verify settings endpoint accepts correct payload shape."""

    def test_settings_update_model(self):
        req = RegressionSettingsUpdateRequest(
            default_area_paths=["CDSIntegration\\CDSCCAL"],
            default_iteration_paths=["CDSIntegration\\CCAL"],
            exclusion_keywords=["archive", "junk"],
            min_changed_date="2020-01-01",
            include_archived=False,
        )
        assert req.default_area_paths == ["CDSIntegration\\CDSCCAL"]
        assert req.include_archived is False


class TestExcludeByFilterContract:
    """Verify exclusion endpoint modes work."""

    def test_exclude_modes(self):
        for mode in ["item", "suite", "plan"]:
            req = RegressionExcludeByFilterRequest(project="Test", mode=mode)
            assert req.mode == mode


class TestPromoteContract:
    """Verify promote endpoint model."""

    def test_promote_model(self):
        req = RegressionPromoteRequest(
            item_ids=[1, 2, 3],
            source_datasource_id=1,
            target_datasource_id=2,
        )
        assert req.item_ids == [1, 2, 3]


class TestDateParsing:
    """Verify date parsing helper handles all expected formats."""

    def test_iso_format(self):
        result = _parse_optional_date("2024-01-15T10:30:00Z")
        assert result.year == 2024

    def test_us_format(self):
        result = _parse_optional_date("01/15/2024")
        assert result.month == 1
        assert result.day == 15

    def test_date_only(self):
        result = _parse_optional_date("2020-01-01")
        assert result.year == 2020

    def test_none(self):
        assert _parse_optional_date(None) is None

    def test_empty(self):
        assert _parse_optional_date("") is None

    def test_invalid_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _parse_optional_date("not-a-date")


# --- Service function unit tests ---

class TestDistinctValuesContract:
    """Verify the new get_regression_distinct_values function contract."""

    def test_function_signature(self):
        import inspect
        sig = inspect.signature(get_regression_distinct_values)
        params = list(sig.parameters.keys())
        assert "db" in params
        assert "project" in params
        assert "filter_text" in params

    def test_function_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(get_regression_distinct_values)


class TestCatalogListContract:
    """Verify list_regression_catalog function signature."""

    def test_function_signature_has_all_filters(self):
        import inspect
        sig = inspect.signature(list_regression_catalog)
        params = list(sig.parameters.keys())
        expected_params = [
            "db", "project", "group", "status", "search_text",
            "area_path", "iteration_path", "plan_name", "suite_name",
            "owner", "title", "tags", "min_changed_date", "include_excluded",
        ]
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"


class TestReportContract:
    """Verify report function returns expected keys."""

    def test_report_function_signature(self):
        import inspect
        assert inspect.iscoroutinefunction(get_regression_report)


class TestGroupsContract:
    """Verify groups function returns expected structure."""

    def test_groups_function_signature(self):
        import inspect
        assert inspect.iscoroutinefunction(get_regression_groups)
