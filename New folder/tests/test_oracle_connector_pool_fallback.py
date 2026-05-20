import unittest
from unittest.mock import Mock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.oracle_connector import OracleConnector


class _FakeCursor:
    def __init__(self, rows=None, description=None, execute_error=None):
        self._rows = rows or []
        self.description = description
        self._execute_error = execute_error
        self.rowcount = len(self._rows)
        self.executed = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self._execute_error:
            raise self._execute_error

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class _FakeConnection:
    def __init__(self, cursor_factory):
        self._cursor_factory = cursor_factory
        self.closed = False
        self.committed = False

    def cursor(self):
        return self._cursor_factory()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class OracleConnectorPoolFallbackTests(unittest.TestCase):
    def setUp(self):
        self.connector = OracleConnector(
            host="dummy",
            port=1521,
            database="db",
            username="u",
            password="p",
        )

    def test_execute_query_falls_back_to_direct_connection_when_pool_acquire_fails(self):
        fake_cursor = _FakeCursor(rows=[(1,)], description=[("VALUE",)])
        fake_conn = _FakeConnection(lambda: fake_cursor)
        fake_pool = Mock()
        fake_pool.acquire.side_effect = RuntimeError("pool timeout")

        self.connector._pool = fake_pool
        self.connector._direct_connect = Mock(return_value=fake_conn)

        rows = self.connector.execute_query("SELECT 1 AS VALUE FROM dual")

        self.assertEqual(rows, [{"VALUE": 1}])
        self.connector._direct_connect.assert_called_once()
        self.assertTrue(fake_conn.closed)
        self.assertEqual(fake_cursor.executed[0][0], "SELECT 1 AS VALUE FROM dual")

    def test_validate_sql_batch_returns_clear_error_when_no_connection_is_available(self):
        fake_pool = Mock()
        fake_pool.acquire.side_effect = RuntimeError("pool timeout")

        self.connector._pool = fake_pool
        self.connector._direct_connect = Mock(side_effect=RuntimeError("direct timeout"))

        result = self.connector.validate_sql_batch(["SELECT 1 FROM dual", "SELECT 2 FROM dual"])

        self.assertEqual(
            result,
            [
                "Cannot acquire Oracle connection for SQL validation.",
                "Cannot acquire Oracle connection for SQL validation.",
            ],
        )

    def test_execute_query_does_not_attempt_direct_fallback_on_dpy_6005(self):
        fake_pool = Mock()
        fake_pool.acquire.side_effect = RuntimeError("DPY-6005: cannot connect to database timed out")

        self.connector._pool = fake_pool
        self.connector._direct_connect = Mock(side_effect=RuntimeError("should not be called"))

        with self.assertRaises(RuntimeError) as ctx:
            self.connector.execute_query("SELECT 1 FROM dual")

        self.connector._direct_connect.assert_not_called()
        self.assertIn("Failed to acquire Oracle connection from pool", str(ctx.exception))
        self.assertNotIn("direct connect fallback failed", str(ctx.exception))

    def test_execute_query_does_not_attempt_direct_fallback_on_dpy_4005(self):
        fake_pool = Mock()
        fake_pool.acquire.side_effect = RuntimeError("DPY-4005: timed out waiting for the connection pool to return a connection")

        self.connector._pool = fake_pool
        self.connector.connect = Mock()
        self.connector._direct_connect = Mock(side_effect=RuntimeError("should not be called"))

        with self.assertRaises(RuntimeError) as ctx:
            self.connector.execute_query("SELECT 1 FROM dual")

        self.connector._direct_connect.assert_not_called()
        self.assertIn("Failed to acquire Oracle connection from pool", str(ctx.exception))
        self.assertNotIn("direct connect fallback failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
