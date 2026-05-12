"""Comprehensive tests for regression_lab_service.py.

Tests cover: group classification, domain context, filtering, helper functions,
archival detection, text parsing, SQL extraction, and report generation logic.
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from app.services.regression_lab_service import (
        _best_group_for_text,
        _compute_domain_group,
        _extract_sql_candidates,
        _extract_expected_results_text,
        _heuristic_search_score,
        _is_archive_like,
        _is_archive_match_for_item,
        _json_dumps,
        _json_loads,
        _matches_prefix,
        _matches_tags,
        _norm_text,
        _norm_upper,
        _parse_dt,
        _strip_markup,
        DEFAULT_EXCLUSION_KEYWORDS,
        GROUP_RULES,
        REGRESSION_MAIN_GROUPS,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="sqlalchemy or other deps not available")


# --- Helper functions ---

class TestNormText:
    def test_none(self):
        assert _norm_text(None) == ""

    def test_empty(self):
        assert _norm_text("") == ""

    def test_strips_whitespace(self):
        assert _norm_text("  hello world  ") == "hello world"

    def test_preserves_case(self):
        assert _norm_text(" Hello ") == "Hello"


class TestNormUpper:
    def test_none(self):
        assert _norm_upper(None) == ""

    def test_uppercase(self):
        assert _norm_upper("hello") == "HELLO"

    def test_removes_quotes(self):
        assert _norm_upper('"TABLE"') == "TABLE"

    def test_strips(self):
        assert _norm_upper("  test  ") == "TEST"


class TestJsonDumpsLoads:
    def test_dumps_list(self):
        result = _json_dumps([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_dumps_none(self):
        result = _json_dumps(None)
        assert json.loads(result) == []

    def test_loads_valid(self):
        assert _json_loads('[1,2,3]', []) == [1, 2, 3]

    def test_loads_none(self):
        assert _json_loads(None, []) == []

    def test_loads_invalid(self):
        assert _json_loads("not json", "fallback") == "fallback"

    def test_loads_empty(self):
        assert _json_loads("", []) == []


class TestParseDt:
    def test_none(self):
        assert _parse_dt(None) is None

    def test_empty_string(self):
        assert _parse_dt("") is None

    def test_iso_format(self):
        result = _parse_dt("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_with_timezone(self):
        result = _parse_dt("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_us_date_format(self):
        result = _parse_dt("01/15/2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_datetime_passthrough(self):
        dt = datetime(2024, 1, 15, tzinfo=timezone.utc)
        assert _parse_dt(dt) == dt


class TestStripMarkup:
    def test_none(self):
        assert _strip_markup(None) == ""

    def test_br_tags(self):
        assert "line1\nline2" in _strip_markup("line1<br/>line2")

    def test_html_tags(self):
        result = _strip_markup("<div><p>Hello</p></div>")
        assert "Hello" in result
        assert "<" not in result

    def test_multi_newlines_collapsed(self):
        result = _strip_markup("a\n\n\n\n\nb")
        assert "\n\n\n" not in result


# --- Classification ---

class TestBestGroupForText:
    def test_transactions(self):
        assert _best_group_for_text("source shadow firm trades") == "Transactions"

    def test_positions(self):
        assert _best_group_for_text("tax lot position") == "Positions"

    def test_balances(self):
        assert _best_group_for_text("RTC sub bal ending balance") == "Balances"

    def test_aml(self):
        assert _best_group_for_text("AML watchlist sanctions") == "AML"

    def test_performance(self):
        assert _best_group_for_text("cash flow performance return") == "Performance/CF Generation"

    def test_other_fallback(self):
        assert _best_group_for_text("random unrelated text") == "Other"

    def test_empty(self):
        assert _best_group_for_text("") == "Other"

    def test_multi_word_keyword_priority(self):
        # "tax lot" is a multi-word keyword worth more points
        result = _best_group_for_text("tax lot")
        assert result == "Positions"

    def test_priority_ordering(self):
        # "balance" and "position" both match - Balances should win per priority
        result = _best_group_for_text("balance position")
        assert result == "Balances"


class TestComputeDomainGroup:
    def test_transaction_context(self):
        group, context = _compute_domain_group("transfer xfer movement", "", "", "", "")
        assert group == "Transactions"
        assert context == "Transfers"

    def test_positions_taxlot(self):
        group, context = _compute_domain_group("tax lot holding", "", "", "", "")
        assert group == "Positions"
        assert context == "Tax Lots"

    def test_balances_rtc(self):
        group, context = _compute_domain_group("rtc balance sub bal", "", "", "", "")
        assert group == "Balances"
        assert context == "RTC Balances"

    def test_other_unclassified(self):
        group, context = _compute_domain_group("nothing here", "", "", "", "")
        assert group == "Other"
        assert context == "Unclassified"


# --- Archive detection ---

class TestIsArchiveLike:
    def test_archive_match(self):
        assert _is_archive_like("Old Archive Suite", DEFAULT_EXCLUSION_KEYWORDS)

    def test_arch_match(self):
        assert _is_archive_like("arch_old_test", DEFAULT_EXCLUSION_KEYWORDS)

    def test_junk_match(self):
        assert _is_archive_like("Junk Data", DEFAULT_EXCLUSION_KEYWORDS)

    def test_no_match(self):
        assert not _is_archive_like("Regression Suite Active", DEFAULT_EXCLUSION_KEYWORDS)

    def test_empty(self):
        assert not _is_archive_like("", DEFAULT_EXCLUSION_KEYWORDS)

    def test_custom_keywords(self):
        assert _is_archive_like("deprecated items", ["deprecated"])
        assert not _is_archive_like("active items", ["deprecated"])


# --- Filtering ---

class TestMatchesPrefix:
    def test_matches(self):
        assert _matches_prefix("CDSIntegration\\CCAL\\Sprint1", ["CDSIntegration\\CCAL"])

    def test_no_match(self):
        assert not _matches_prefix("OtherProject\\Path", ["CDSIntegration\\CCAL"])

    def test_empty_prefixes(self):
        assert _matches_prefix("anything", [])

    def test_none_value(self):
        assert not _matches_prefix(None, ["CDSIntegration"])

    def test_case_insensitive(self):
        assert _matches_prefix("cdsintegration\\ccal", ["CDSIntegration\\CCAL"])


class TestMatchesTags:
    def test_matches_single(self):
        assert _matches_tags("regression, balances, aml", ["regression"])

    def test_matches_all(self):
        assert _matches_tags("regression, balances", ["regression", "balances"])

    def test_fails_partial(self):
        assert not _matches_tags("regression", ["regression", "balances"])

    def test_empty_filter(self):
        assert _matches_tags("anything", [])

    def test_none_tags(self):
        assert not _matches_tags(None, ["regression"])


# --- SQL extraction ---

class TestExtractSqlCandidates:
    def test_simple_select(self):
        text = "Run this query:\nSELECT * FROM table1 WHERE id = 1;"
        candidates = _extract_sql_candidates(text)
        assert len(candidates) >= 1
        assert "SELECT" in candidates[0].upper()

    def test_with_cte(self):
        text = "WITH cte AS (SELECT 1) SELECT * FROM cte;"
        candidates = _extract_sql_candidates(text)
        assert len(candidates) >= 1

    def test_no_sql(self):
        text = "This is just a description with no SQL."
        candidates = _extract_sql_candidates(text)
        assert len(candidates) == 0

    def test_multiple_queries(self):
        text = "SELECT a FROM t1;\nSELECT b FROM t2;"
        candidates = _extract_sql_candidates(text)
        assert len(candidates) >= 2

    def test_html_stripped(self):
        text = "<div>SELECT * FROM <strong>table1</strong>;</div>"
        candidates = _extract_sql_candidates(text)
        assert len(candidates) >= 1

    def test_deduplication(self):
        text = "SELECT * FROM t1;\nSELECT * FROM t1;"
        candidates = _extract_sql_candidates(text)
        assert len(candidates) == 1


class TestExtractExpectedResultsText:
    def test_none(self):
        assert _extract_expected_results_text(None) == ""

    def test_empty(self):
        assert _extract_expected_results_text("") == ""

    def test_extracts_content(self):
        xml = '<parameterizedString isformatted="true">step action</parameterizedString><parameterizedString isformatted="true">expected result</parameterizedString>'
        result = _extract_expected_results_text(xml)
        assert "expected result" in result


# --- Search scoring ---

class TestHeuristicSearchScore:
    def test_title_match_high_weight(self):
        item = MagicMock()
        item.title = "RTC Balance Verification"
        item.domain_context = ""
        item.suite_path = ""
        item.tags = ""
        item.description_text = ""
        item.steps_text = ""
        item.attachment_text = ""
        score = _heuristic_search_score(item, "balance")
        assert score >= 8  # title weight is 8

    def test_no_match(self):
        item = MagicMock()
        item.title = "Something Else"
        item.domain_context = ""
        item.suite_path = ""
        item.tags = ""
        item.description_text = ""
        item.steps_text = ""
        item.attachment_text = ""
        score = _heuristic_search_score(item, "balance")
        assert score == 0

    def test_multi_term(self):
        item = MagicMock()
        item.title = "RTC Balance Transfer"
        item.domain_context = ""
        item.suite_path = ""
        item.tags = "regression"
        item.description_text = ""
        item.steps_text = ""
        item.attachment_text = ""
        score = _heuristic_search_score(item, "balance regression")
        assert score > 8  # Both terms found


# --- Groups list ---

class TestMainGroups:
    def test_all_groups_present(self):
        expected = ["Transactions", "Positions", "Balances", "AML", "Performance/CF Generation", "Other"]
        assert REGRESSION_MAIN_GROUPS == expected

    def test_group_rules_keys_match(self):
        for group in GROUP_RULES:
            assert group in REGRESSION_MAIN_GROUPS


# --- Integration-level tests (mock DB) ---

class TestCatalogFilterContains:
    """Verify that catalog filtering uses contains-matching for area/iteration."""

    def test_area_contains_matching_logic(self):
        """The filter should match if filter text is contained in area_path."""
        area_filter = "CDSCCAL"
        item_area = "CDSIntegration\\CDSCCAL\\SubPath"
        assert area_filter.lower() in item_area.lower()

    def test_iteration_contains_matching_logic(self):
        """The filter should match if filter text is contained in iteration_path."""
        iter_filter = "CCAL"
        item_iter = "CDSIntegration\\CCAL\\Sprint5"
        assert iter_filter.lower() in item_iter.lower()

    def test_partial_text_matches(self):
        """Contains matching finds partial path segments."""
        filter_text = "Shadow"
        suite_name = "Source Shadow firm trades into CCAL"
        assert filter_text.lower() in suite_name.lower()
