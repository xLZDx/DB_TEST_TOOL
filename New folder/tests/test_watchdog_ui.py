"""
Test Watchdog UI integration - verify dashboard displays watchdog status correctly.
"""
import pytest
from app.routers.system_watchdog import router
from app.services.session_watchdog import get_session_watchdog_status, run_watchdog_sweep_now


def test_watchdog_status_has_required_fields():
    """Verify watchdog status dict has all fields needed by dashboard UI."""
    status = get_session_watchdog_status()
    
    required_fields = {
        'enabled': bool,
        'running': bool,
        'interval_seconds': int,
        'last_sweep_at': (str, type(None)),
        'last_result': (dict, type(None)),
        'last_error': str,
    }
    
    for field, expected_type in required_fields.items():
        assert field in status, f"Missing field: {field}"
        if isinstance(expected_type, tuple):
            assert isinstance(status[field], expected_type), \
                f"Field {field} type {type(status[field])} not in {expected_type}"
        else:
            assert isinstance(status[field], expected_type), \
                f"Field {field} expected {expected_type}, got {type(status[field])}"


def test_watchdog_sweep_returns_required_stats():
    """Verify manual sweep returns operation and odi stats for dashboard display."""
    result = run_watchdog_sweep_now()
    
    # Must have operation stats
    assert 'operation' in result
    assert 'stale_stopped' in result['operation']
    assert 'pruned' in result['operation']
    assert 'active' in result['operation']
    
    # Must have odi stats
    assert 'odi' in result
    assert 'killed_stale' in result['odi']
    assert 'killed_zombie_processes' in result['odi']
    assert 'pruned' in result['odi']
    assert 'active_sessions' in result['odi']


def test_watchdog_router_status_endpoint():
    """Verify /api/system/watchdog/status endpoint is properly registered."""
    # Find the status endpoint
    status_endpoint = None
    for route in router.routes:
        if '/api/system/watchdog/status' in route.path:
            status_endpoint = route
            break
    
    assert status_endpoint is not None, "Status endpoint not found in router"
    assert 'GET' in status_endpoint.methods, "Status endpoint should support GET"


def test_watchdog_router_sweep_endpoint():
    """Verify /api/system/watchdog/sweep endpoint is properly registered."""
    # Find the sweep endpoint
    sweep_endpoint = None
    for route in router.routes:
        if '/api/system/watchdog/sweep' in route.path:
            sweep_endpoint = route
            break
    
    assert sweep_endpoint is not None, "Sweep endpoint not found in router"
    assert 'POST' in sweep_endpoint.methods, "Sweep endpoint should support POST"


def test_dashboard_has_watchdog_card_html():
    """Verify dashboard.html includes the watchdog card markup."""
    with open('app/templates/dashboard.html', 'r') as f:
        html = f.read()
    
    required_elements = [
        'Watchdog Status',  # Card heading
        'watchdog-status-badge',
        'watchdog-interval',
        'watchdog-last-sweep',
        'watchdog-killed-count',
        'watchdog-sweep-btn',
    ]
    
    for element in required_elements:
        assert element in html, f"Dashboard missing: {element}"


def test_app_js_has_watchdog_api_methods():
    """Verify app.js API object includes watchdog methods."""
    with open('app/static/js/app.js', 'r') as f:
        js = f.read()
    
    required_methods = [
        'getWatchdogStatus: () => api(\'GET\', \'/api/system/watchdog/status\')',
        'runWatchdogSweep: () => api(\'POST\', \'/api/system/watchdog/sweep\', {})',
    ]
    
    for method in required_methods:
        assert method in js, f"App.js missing: {method}"


def test_dashboard_has_watchdog_js_functions():
    """Verify dashboard.html includes required JavaScript functions for watchdog UI."""
    with open('app/templates/dashboard.html', 'r') as f:
        html = f.read()
    
    required_functions = [
        'async function loadWatchdogStatus()',
        'async function triggerWatchdogSweep()',
        'setInterval(loadWatchdogStatus, 5000)',  # Auto-refresh every 5 seconds
    ]
    
    for func in required_functions:
        assert func in html, f"Dashboard missing: {func}"


def test_watchdog_card_displays_status_badge_colors():
    """Verify dashboard UI renders appropriate colors for watchdog status."""
    with open('app/templates/dashboard.html', 'r') as f:
        html = f.read()
    
    # Check that the status badge changes color based on state
    assert 'var(--success)' in html, "Should use success color for active status"
    assert 'var(--warning)' in html, "Should use warning color for inactive status"
    assert 'var(--danger)' in html, "Should use danger color for killed counts"
    assert 'var(--muted)' in html, "Should use muted color for disabled status"


def test_watchdog_UI_layout_is_grid():
    """Verify watchdog card uses responsive grid layout."""
    with open('app/templates/dashboard.html', 'r') as f:
        html = f.read()
    
    # Check for grid layout structure
    assert 'grid-template-columns:1fr 1fr' in html, "Watchdog status fields should be in 2-column grid"
    assert 'gap:12px' in html, "Status fields should have proper spacing"


def test_sweep_button_is_enabled_by_default():
    """Verify manual sweep button is enabled and functional."""
    with open('app/templates/dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Check button properties
    assert 'btn-success' in html, "Sweep button should use success style"
    assert 'Manual Sweep' in html, "Sweep button should have Manual Sweep text"
    assert 'onclick="triggerWatchdogSweep()"' in html, "Button should call triggerWatchdogSweep"
    assert 'width:100%' in html, "Sweep button should be full width"
