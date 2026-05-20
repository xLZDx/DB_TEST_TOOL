"""Cross-tool contract tests for major app functionality coverage.

This suite validates that core modules, routes, templates, and watchdog controls
remain wired across the whole DB Testing Tool.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "app" / "main.py"
CONFIG_PY = ROOT / "app" / "config.py"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_core_routers_are_included_in_main():
    main = _read(MAIN_PY)
    expected = [
        "datasources.router",
        "schemas.router",
        "mappings.router",
        "tests.router",
        "ai.router",
        "tfs.router",
        "agents.router",
        "credentials.router",
        "external_tools.router",
        "odi.router",
        "chat_assistant.router",
        "regression_lab.router",
        "system_watchdog.router",
    ]
    for token in expected:
        assert token in main


def test_all_primary_page_routes_exist():
    main = _read(MAIN_PY)
    routes = [
        '"/"',
        '"/datasources"',
        '"/schema-browser"',
        '"/mappings"',
        '"/tests"',
        '"/runs"',
        '"/ai-assistant"',
        '"/chat-assistant"',
        '"/training-studio"',
        '"/tfs"',
        '"/settings"',
        '"/agents"',
        '"/external-tools"',
        '"/odi"',
        '"/regression-lab"',
    ]
    for route in routes:
        assert route in main


def test_watchdog_is_started_and_stopped_with_app_lifecycle():
    main = _read(MAIN_PY)
    assert "from app.services.session_watchdog import start_session_watchdog, stop_session_watchdog" in main
    assert "await start_session_watchdog()" in main
    assert "@app.on_event(\"shutdown\")" in main
    assert "await stop_session_watchdog()" in main


def test_watchdog_config_keys_exist():
    config = _read(CONFIG_PY)
    keys = [
        "WATCHDOG_ENABLED",
        "WATCHDOG_INTERVAL_SECONDS",
        "WATCHDOG_OPERATION_STALE_MINUTES",
        "WATCHDOG_OPERATION_QUEUE_STALE_MINUTES",
        "WATCHDOG_OPERATION_RETAIN_MINUTES",
        "WATCHDOG_ODI_STALE_SECONDS",
        "WATCHDOG_ODI_MAX_RUNTIME_SECONDS",
        "WATCHDOG_ODI_RETAIN_SECONDS",
    ]
    for key in keys:
        assert key in config


def test_watchdog_endpoints_exist():
    router = _read(ROOT / "app" / "routers" / "system_watchdog.py")
    assert "prefix=\"/api/system/watchdog\"" in router
    assert "@router.get(\"/status\")" in router
    assert "@router.post(\"/sweep\")" in router


def test_watchdog_service_implements_loop_and_sweep():
    service = _read(ROOT / "app" / "services" / "session_watchdog.py")
    assert "async def _watchdog_loop()" in service
    assert "def run_watchdog_sweep_now()" in service
    assert "sweep_stale_operations" in service
    assert "sweep_odi_sessions" in service


def test_operation_control_supports_stale_sweep():
    content = _read(ROOT / "app" / "services" / "operation_control.py")
    assert "def sweep_stale_operations(" in content
    assert "Watchdog terminated stale session" in content


def test_odi_router_supports_session_sweeping():
    content = _read(ROOT / "app" / "routers" / "odi.py")
    assert "def sweep_odi_sessions(" in content
    assert "killed_stale" in content
    assert "killed_zombie_processes" in content


def test_regression_lab_has_filter_discovery_and_expand_controls():
    html = _read(ROOT / "app" / "templates" / "regression_lab.html")
    assert "Filter Discovery (Iterations / Areas / Plans / Suites)" in html
    assert "Collapse All" in html
    assert "Expand All" in html


def test_js_api_contains_regression_filter_endpoint():
    js = _read(APP_JS)
    assert "getRegressionFilters" in js
    assert "/api/regression-lab/filters/" in js


def test_all_critical_templates_exist():
    templates = ROOT / "app" / "templates"
    expected = [
        "dashboard.html",
        "datasources.html",
        "schema_browser.html",
        "mappings.html",
        "tests.html",
        "ai.html",
        "chat_assistant.html",
        "training_studio.html",
        "tfs.html",
        "agents.html",
        "settings.html",
        "external_tools.html",
        "odi.html",
        "regression_lab.html",
    ]
    for name in expected:
        assert (templates / name).exists(), f"Missing template: {name}"


def test_all_critical_router_modules_exist():
    routers = ROOT / "app" / "routers"
    expected = [
        "datasources.py",
        "schemas.py",
        "mappings.py",
        "tests.py",
        "ai.py",
        "tfs.py",
        "agents.py",
        "credentials.py",
        "external_tools.py",
        "odi.py",
        "chat_assistant.py",
        "regression_lab.py",
        "system_watchdog.py",
    ]
    for name in expected:
        assert (routers / name).exists(), f"Missing router: {name}"
