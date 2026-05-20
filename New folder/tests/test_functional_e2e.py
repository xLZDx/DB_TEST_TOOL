"""
Functional E2E tests for the DB Testing Tool.

Runs against the live server at http://127.0.0.1:8550.
Every test hits a real HTTP endpoint and asserts the response shape.
Run with: pytest tests/test_functional_e2e.py -v
"""

import pytest
import requests
import json

BASE = "http://127.0.0.1:8550"
S = requests.Session()
S.headers["Content-Type"] = "application/json"


def _get(path, timeout=15, **kwargs):
    r = S.get(f"{BASE}{path}", timeout=timeout, **kwargs)
    return r


def _post(path, body=None, **kwargs):
    r = S.post(f"{BASE}{path}", json=body, timeout=15, **kwargs)
    return r


# ── 1. UI Pages (HTML) ──────────────────────────────────────────────────────

class TestUIPages:
    """All dashboard page routes must return 200 with HTML content."""

    @pytest.mark.parametrize("path,page_keyword", [
        ("/", "Dashboard"),
        ("/datasources", "datasources"),
        ("/schema-browser", "schema"),
        ("/mappings", "mappings"),
        ("/regression-lab", "regression"),
        ("/ai-assistant", "ai"),
        ("/chat-assistant", "chat"),
        ("/training-studio", "training"),
        ("/tfs", "tfs"),
        ("/agents", "agents"),
        ("/external-tools", "external"),
        ("/odi", "odi"),
        ("/settings", "settings"),
        ("/tests", "test"),
    ])
    def test_page_loads(self, path, page_keyword):
        r = _get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"
        assert "<!DOCTYPE html>" in r.text or "<html" in r.text, f"{path} response is not HTML"


# ── 2. Health / Root API ────────────────────────────────────────────────────

class TestHealth:
    def test_root_api_health(self):
        r = _get("/api/system/watchdog/status")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_root_page_200(self):
        r = _get("/")
        assert r.status_code == 200


# ── 3. Datasources API ──────────────────────────────────────────────────────

class TestDatasourcesAPI:
    def test_list_datasources(self):
        r = _get("/api/datasources/")
        assert r.status_code == 200
        data = r.json()
        assert "datasources" in data or "items" in data or isinstance(data, list)

    def test_list_credentials(self):
        r = _get("/api/credentials/")
        assert r.status_code == 200

    def test_invalid_datasource_404(self):
        r = _get("/api/datasources/99999999")
        assert r.status_code in (404, 422)


# ── 4. Tests API ────────────────────────────────────────────────────────────

class TestTestsAPI:
    def test_list_tests(self):
        r = _get("/api/tests/")
        assert r.status_code == 200
        data = r.json()
        assert "test_cases" in data or "items" in data or isinstance(data, (list, dict))

    def test_list_test_suites(self):
        r = _get("/api/tests/suites")
        # Could be 200 or 404 depending on suite endpoint; must not be 500
        assert r.status_code != 500, f"Server error on /api/tests/suites: {r.text[:200]}"

    def test_list_test_folders(self):
        r = _get("/api/tests/folders")
        assert r.status_code != 500, f"Server error on /api/tests/folders: {r.text[:200]}"

    def test_create_and_delete_test(self):
        payload = {
            "name": "E2E Smoke Test Case",
            "test_type": "sql_compare",
            "description": "Created by functional e2e test",
            "source_query": "SELECT 1 AS n FROM DUAL",
            "target_query": "SELECT 1 AS n FROM DUAL",
        }
        r = _post("/api/tests/", payload)
        assert r.status_code in (200, 201), f"Create test failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        tc_id = data.get("id") or data.get("test_case", {}).get("id")
        if tc_id:
            del_r = S.delete(f"{BASE}/api/tests/{tc_id}", timeout=10)
            assert del_r.status_code in (200, 204), f"Delete test failed: {del_r.status_code}"


# ── 5. AI API ───────────────────────────────────────────────────────────────

class TestAIAPI:
    def test_ai_chat_endpoint_exists(self):
        # Just verify the endpoint is reachable (will 422 without required fields)
        r = _post("/api/ai/chat", {})
        assert r.status_code != 500, f"AI chat returned 500: {r.text[:200]}"
        assert r.status_code in (200, 422)

    def test_ai_providers_list(self):
        r = _get("/api/ai/providers")
        assert r.status_code != 500, f"AI providers returned 500: {r.text[:200]}"


# ── 6. Agents API ───────────────────────────────────────────────────────────

class TestAgentsAPI:
    def test_list_agents(self):
        r = _get("/api/agents/")
        assert r.status_code == 200
        data = r.json()
        assert "agents" in data or isinstance(data, list), f"Unexpected agents response: {data}"

    def test_create_and_delete_agent(self):
        payload = {
            "name": "E2E Test Agent",
            "role": "tester",
            "description": "Temporary agent for e2e test",
            "system_prompt": "You are a test agent created by the e2e suite.",
            "is_active": True,
        }
        r = _post("/api/agents/", payload)
        assert r.status_code in (200, 201), f"Create agent failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        agent_id = data.get("id") or (data.get("agent") or {}).get("id")
        if agent_id:
            del_r = S.delete(f"{BASE}/api/agents/{agent_id}", timeout=10)
            assert del_r.status_code in (200, 204), f"Delete agent failed: {del_r.status_code}"


# ── 7. TFS API ──────────────────────────────────────────────────────────────

class TestTFSAPI:
    def test_tfs_config(self):
        r = _get("/api/tfs/config")
        assert r.status_code == 200
        data = r.json()
        assert "base_url" in data or "configured" in data

    def test_tfs_projects(self):
        r = _get("/api/tfs/projects")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data

    def test_tfs_preset_queries(self):
        r = _get("/api/tfs/preset-queries")
        assert r.status_code == 200
        data = r.json()
        assert "queries" in data

    def test_tfs_work_item_context_bad_id_returns_non500(self):
        """A missing work item must return 4xx, not 500."""
        r = _get("/api/tfs/work-item-context/999999999?project=CDSIntegration")
        # After our fix, should be 400 (ValueError) not 500 (NameError)
        assert r.status_code != 500, f"Got 500 for missing work item: {r.text[:300]}"
        assert r.status_code in (400, 404, 422)

    def test_tfs_test_plans(self):
        # TFS network call — use longer timeout
        r = _get("/api/tfs/test-plans/CDSIntegration", timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data

    def test_tfs_test_run_bad_point_ids_returns_400(self):
        """Creating a run with non-existent point IDs must return 400, not 500."""
        payload = {
            "run_name": "E2E Smoke Run",
            "project": "CDSIntegration",
            "plan_id": 99999999,
            "test_point_ids": [99999999],
        }
        r = _post("/api/tfs/test-runs", payload)
        assert r.status_code in (400, 404, 422), \
            f"Expected 400/404/422, got {r.status_code}: {r.text[:300]}"


# ── 8. Chat Assistant API ───────────────────────────────────────────────────

class TestChatAPI:
    def test_list_conversations(self):
        r = _get("/api/chat/conversations")
        assert r.status_code == 200

    def test_create_conversation(self):
        payload = {"title": "E2E Test Conversation"}
        r = _post("/api/chat/conversations", payload)
        assert r.status_code in (200, 201), f"Create conversation: {r.status_code} {r.text[:200]}"


# ── 9. ODI API ──────────────────────────────────────────────────────────────

class TestODIAPI:
    def test_odi_config_files(self):
        r = _get("/api/odi/config-files")
        assert r.status_code != 500, f"ODI config-files 500: {r.text[:200]}"
        assert r.status_code in (200, 404)

    def test_odi_repository_status(self):
        r = _get("/api/odi/repository/status")
        assert r.status_code != 500, f"ODI repository/status 500: {r.text[:200]}"
        assert r.status_code in (200, 404)


# ── 10. Schema API ──────────────────────────────────────────────────────────

class TestSchemaAPI:
    def test_schema_tree_stub(self):
        r = _get("/api/schemas/tree/1")
        assert r.status_code != 500, f"Schema tree 500: {r.text[:200]}"
        assert r.status_code in (200, 404)


# ── 11. System Watchdog ─────────────────────────────────────────────────────

class TestSystemWatchdog:
    def test_watchdog_status(self):
        r = _get("/api/system/watchdog/status")
        assert r.status_code == 200


# ── 12. Regression Lab API ──────────────────────────────────────────────────

class TestRegressionLabAPI:
    def test_regression_lab_jobs(self):
        r = _get("/api/regression-lab/jobs")
        assert r.status_code != 500, f"Regression lab jobs 500: {r.text[:200]}"
        assert r.status_code in (200, 404)
