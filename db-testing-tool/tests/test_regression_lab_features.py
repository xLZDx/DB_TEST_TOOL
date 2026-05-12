"""Regression Lab UI contract tests for the latest features.

Tests cover: expand/collapse all, filter discovery card, reporting rework,
contains-matching filters, default changed-since date, and distinct values API.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGRESSION_LAB_HTML = ROOT / "app" / "templates" / "regression_lab.html"
REGRESSION_LAB_SERVICE = ROOT / "app" / "services" / "regression_lab_service.py"
REGRESSION_LAB_ROUTER = ROOT / "app" / "routers" / "regression_lab.py"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- Expand/Collapse All ---

class TestExpandCollapseAll:
    def test_collapse_all_button_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'collapseAllCatalogPlans()' in html

    def test_expand_all_button_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'expandAllCatalogPlans()' in html

    def test_collapse_all_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function collapseAllCatalogPlans()' in html

    def test_expand_all_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function expandAllCatalogPlans()' in html

    def test_collapse_sets_all_false(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '_rlPlanExpandState[key] = false' in html
        assert '_rlSuiteExpandState[key] = false' in html

    def test_expand_sets_all_true(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '_rlPlanExpandState[key] = true' in html
        assert '_rlSuiteExpandState[key] = true' in html


# --- Filter Discovery Card ---

class TestFilterDiscoveryCard:
    def test_filter_discovery_section_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'Filter Discovery (Iterations / Areas / Plans / Suites)' in html

    def test_filter_discovery_search_input(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-filter-discovery-search"' in html

    def test_iteration_list_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-fd-iter-list"' in html

    def test_area_list_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-fd-area-list"' in html

    def test_plan_list_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-fd-plan-list"' in html

    def test_suite_list_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-fd-suite-list"' in html

    def test_load_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'async function loadRegressionFilterDiscovery()' in html

    def test_render_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function renderFilterDiscoveryLists()' in html

    def test_local_filter_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function filterDiscoveryList(listId, searchText)' in html

    def test_exclusion_function_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function applyFilterDiscoveryToExclusion()' in html

    def test_filter_list_css_defined(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-filter-list' in html
        assert '.rl-filter-search' in html
        assert '.rl-filter-card' in html


# --- Reporting & Aggregations Rework ---

class TestReportingRework:
    def test_report_list_class_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-report-list' in html

    def test_report_list_item_class_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-report-list-item' in html

    def test_report_uses_new_layout(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'rl-report-grid' in html

    def test_kpi_includes_passed_failed(self):
        html = _read(REGRESSION_LAB_HTML)
        assert "statusCounts.passed" in html
        assert "statusCounts.partial" in html
        assert "statusCounts.failed" in html

    def test_kpi_color_coding(self):
        html = _read(REGRESSION_LAB_HTML)
        assert "color:#22c55e" in html  # green for passed
        assert "color:#ef4444" in html  # red for failed
        assert "color:#f59e0b" in html  # amber for partial


# --- Contains-Matching Filters ---

class TestContainsMatching:
    def test_area_filter_uses_contains(self):
        svc = _read(REGRESSION_LAB_SERVICE)
        assert 'area_filter.lower() not in _norm_text(item.area_path).lower()' in svc

    def test_iteration_filter_uses_contains(self):
        svc = _read(REGRESSION_LAB_SERVICE)
        assert 'iteration_filter.lower() not in _norm_text(item.iteration_path).lower()' in svc


# --- Default Changed Since ---

class TestDefaultChangedSince:
    def test_default_date_2020(self):
        html = _read(REGRESSION_LAB_HTML)
        assert "|| '2020-01-01'" in html


# --- Distinct Values API Endpoint ---

class TestDistinctValuesEndpoint:
    def test_router_has_filters_endpoint(self):
        router = _read(REGRESSION_LAB_ROUTER)
        assert '/filters/{project}' in router
        assert 'get_regression_distinct_values' in router

    def test_service_has_distinct_values_function(self):
        svc = _read(REGRESSION_LAB_SERVICE)
        assert 'async def get_regression_distinct_values(' in svc

    def test_service_imports_in_router(self):
        router = _read(REGRESSION_LAB_ROUTER)
        assert 'get_regression_distinct_values' in router

    def test_js_api_binding_present(self):
        js = _read(APP_JS)
        assert 'getRegressionFilters' in js
        assert '/api/regression-lab/filters/' in js


# --- Fullscreen Buttons ---

class TestFullscreenButtons:
    def test_catalog_fullscreen_button(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-catalog-fullscreen-btn"' in html
        assert 'toggleRegressionCatalogFullscreen()' in html

    def test_search_fullscreen_button(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-search-fullscreen-btn"' in html
        assert 'toggleRegressionSearchFullscreen()' in html

    def test_fullscreen_css_class(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-card-fullscreen' in html

    def test_catalog_card_has_id(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'id="rl-catalog-card"' in html


# --- Dashboard Refresh ---

class TestDashboardRefresh:
    def test_refresh_includes_filter_discovery(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'loadRegressionFilterDiscovery()' in html

    def test_reset_function_present(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function resetRegressionDashboardState()' in html
        assert 'function resetRegressionDashboard()' in html


# --- Tree Table Structure ---

class TestTreeTableStructure:
    def test_plan_row_class(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-plan-row' in html

    def test_suite_row_class(self):
        html = _read(REGRESSION_LAB_HTML)
        assert '.rl-suite-row' in html

    def test_group_items_function(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function _groupRegressionItems(items)' in html

    def test_tree_table_renderer(self):
        html = _read(REGRESSION_LAB_HTML)
        assert 'function _renderRegressionTreeTable(tbodyId, items, options' in html
