"""Regression contracts for modal fullscreen and test-creation UX behavior.

These tests verify source contracts in frontend templates/scripts so
critical UX regressions are caught in CI even without browser automation.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
APP_CSS = ROOT / "app" / "static" / "css" / "app.css"
MAIN_PY = ROOT / "app" / "main.py"
MAPPINGS_HTML = ROOT / "app" / "templates" / "mappings.html"
BASE_HTML = ROOT / "app" / "templates" / "base.html"
TFS_HTML = ROOT / "app" / "templates" / "tfs.html"
SCHEMA_BROWSER_HTML = ROOT / "app" / "templates" / "schema_browser.html"
TRAINING_STUDIO_HTML = ROOT / "app" / "templates" / "training_studio.html"
ODI_HTML = ROOT / "app" / "templates" / "odi.html"
TESTS_ROUTER = ROOT / "app" / "routers" / "tests.py"
REGRESSION_LAB_HTML = ROOT / "app" / "templates" / "regression_lab.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_fullscreen_uses_overlay_class_toggle_contract():
    js = _read(APP_JS)
    assert "modal-overlay-fullscreen" in js
    assert "overlay.classList.add('modal-overlay-fullscreen')" in js
    assert "overlay.classList.remove('modal-overlay-fullscreen')" in js
    assert "overlay.classList.remove('modal-overlay-fullscreen')" in js


def test_fullscreen_size_telemetry_contract_present():
    js = _read(APP_JS)
    assert "function _snapshotModalSize(modal)" in js
    assert "function _recordModalFullscreenMeasurement(modal, before, after, isFullscreen)" in js
    assert "window.getModalFullscreenRegression" in js


def test_fullscreen_css_matches_control_table_approach():
    css = _read(APP_CSS)
    assert ".modal-overlay.modal-overlay-fullscreen" in css
    assert "width: 100vw !important;" in css
    assert "height: 100vh !important;" in css
    assert "border-radius: 0;" in css
    assert ".modal.app-modal-window:not(.fullscreen)::after" in css


def test_invalid_sql_is_not_excluded_on_create_contract():
    html = _read(MAPPINGS_HTML)
    # The old exclusion text must not exist anymore.
    assert "will be excluded" not in html
    # New create-all behavior prompt should be present.
    assert "create all selected tests as-is" in html.lower()


def test_data_type_fallback_uses_saved_pdm_contract():
    html = _read(MAPPINGS_HTML)
    assert "API.getSavedPdm" in html
    assert "_getPdmTableColumns" in html
    assert "PDM-backed common columns" in html


def test_drd_detected_table_fallback_and_lookup_sanitization_contract():
    html = _read(MAPPINGS_HTML)
    assert "function _isLikelyTableReference(value)" in html
    assert "function _sanitizeDetectedTableRefs(values)" in html
    assert "function _drdPreviewTargetFallback()" in html
    assert "res.complex_count || 0" in html
    assert "_drdHasComplexMappings() ? lookupTables : []" in html


def test_control_table_modal_sync_and_reset_contract():
    html = _read(MAPPINGS_HTML)
    assert 'id="ct-lookup-tables"' in html
    assert 'function resetControlTableModalState()' in html
    assert 'document.getElementById(\'ct-source-table\')' in html
    assert 'document.getElementById(\'ct-target\')' in html
    assert 'closeControlTableModal()' in html


def test_training_studio_route_and_nav_contract():
    main_py = _read(MAIN_PY)
    base_html = _read(BASE_HTML)
    assert '@app.get("/training-studio", response_class=HTMLResponse)' in main_py
    assert 'TemplateResponse("training_studio.html"' in main_py
    assert 'page": "training-studio"' in main_py
    assert 'href="/training-studio"' in base_html
    assert 'Training Studio' in base_html


def test_odi_route_and_nav_contract():
    main_py = _read(MAIN_PY)
    base_html = _read(BASE_HTML)
    odi_html = _read(ODI_HTML)
    assert '@app.get("/odi", response_class=HTMLResponse)' in main_py
    assert 'TemplateResponse("odi.html"' in main_py
    assert 'href="/odi"' in base_html
    assert 'ODI' in base_html
    assert 'ODI Studio Lite' in odi_html
    assert 'Execution Monitor' in odi_html


def test_training_studio_page_and_mappings_link_contract():
    training_html = _read(TRAINING_STUDIO_HTML)
    mappings_html = _read(MAPPINGS_HTML)
    assert 'Automation Loop' in training_html
    assert 'Start Automation' in training_html
    assert 'Run Once' in training_html
    assert 'Stop Automation' in training_html
    assert 'id="ts-auto-status"' in training_html
    assert 'API.startTrainingAutomation' in training_html
    assert 'API.runTrainingAutomationOnce' in training_html
    assert 'Training Studio Moved' not in mappings_html
    assert 'Open Training Studio' not in mappings_html


def test_training_automation_api_contract_present():
    router_py = _read(TESTS_ROUTER)
    assert '@router.get("/training-automation/status")' in router_py
    assert '@router.post("/training-automation/start")' in router_py
    assert '@router.post("/training-automation/stop")' in router_py
    assert '@router.post("/training-automation/run-once")' in router_py
    assert 'class TrainingAutomationRequest(BaseModel):' in router_py


def test_tfs_path_memory_shared_js_contract_present():
    js = _read(APP_JS)
    assert "const TFS_PATH_MEMORY_KEY = 'dbTestingTool.tfsPathMemory.v1';" in js
    assert 'function getRememberedTfsPaths(project, context)' in js
    assert 'function rememberTfsPaths(project, context, values)' in js
    assert 'window.getRememberedTfsPaths = getRememberedTfsPaths;' in js
    assert 'window.rememberTfsPaths = rememberTfsPaths;' in js


def test_tfs_page_restores_and_saves_last_area_iteration_paths():
    html = _read(TFS_HTML)
    assert "function restoreRememberedTfsPathInputs(project, context, areaInputId, iterationInputId)" in html
    assert "function rememberCurrentTfsPathInputs(project, context, areaInputId, iterationInputId)" in html
    assert "function handleTfsPathProjectChange(context, project, areaInputId, iterationInputId)" in html
    assert "handleTfsPathProjectChange('bug-create', this.value, 'bug-area', 'bug-iteration')" in html
    assert "handleTfsPathProjectChange('test-plan', this.value, 'tp-area', 'tp-iteration')" in html
    assert "rememberCurrentTfsPathInputs(" in html
    assert "'bug-create'" in html
    assert "'test-plan'" in html


def test_schema_browser_blank_default_contract_present():
    html = _read(SCHEMA_BROWSER_HTML)
    assert "dsSelect.value = '';" in html
    assert 'Select a data source to load schemas' in html
    assert 'Select a data source and click Analyze or Refresh' in html
    assert 'Data source is blank by default. Select one when you want to browse schemas.' in html


def test_regression_lab_search_results_and_reset_contract_present():
    html = _read(REGRESSION_LAB_HTML)
    assert 'id="rl-search-fullscreen-btn"' in html
    assert 'function resetRegressionDashboard()' in html
    assert 'function renderRegressionSearchResults' in html
    assert 'Showing first ${visibleMatches.length} of ${total} matched test case(s).' in html
    assert 'Execution data is not loaded automatically.' in html
    assert 'Top Plans' in html
    assert 'Top Suites' in html
    assert 'Filter Discovery' in html
    assert 'Linked PBIs / Requirements' not in html
