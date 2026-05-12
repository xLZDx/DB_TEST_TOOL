"""SQL Server connector using pyodbc (optional Tier-2)."""
from typing import Any, Dict, List, Optional
from app.connectors.base import BaseConnector, ConnectionResult, ColumnInfo, TableInfo
import logging

logger = logging.getLogger(__name__)


class SqlServerConnector(BaseConnector):

    def __init__(self, host: str, port: int, database: str,
                 username: str, password: str, extra_params: Optional[Dict] = None):
        super().__init__(host, port or 1433, database, username, password, extra_params)
        self.driver = (extra_params or {}).get("driver", "ODBC Driver 17 for SQL Server")

    def _conn_str(self) -> str:
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )

    def test_connection(self) -> ConnectionResult:
        try:
            import pyodbc
            conn = pyodbc.connect(self._conn_str(), timeout=10)
            cur = conn.cursor()
            cur.execute("SELECT @@VERSION")
            ver = cur.fetchone()[0]
            cur.close()
            conn.close()
            return ConnectionResult(True, "Connected", ver[:80])
        except Exception as e:
            return ConnectionResult(False, str(e))

    def connect(self):
        import pyodbc
        self._connection = pyodbc.connect(self._conn_str(), timeout=15)

    def disconnect(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def get_schemas(self) -> List[str]:
        sql = """
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('guest','INFORMATION_SCHEMA','sys')
            ORDER BY schema_name
        """
        return [r["schema_name"] for r in self.execute_query(sql)]

    def get_tables(self, schema: str) -> List[TableInfo]:
        sql = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = ?
            ORDER BY table_name
        """
        rows = self.execute_query(sql, {"schema": schema})
        return [
            TableInfo(r["table_schema"], r["table_name"],
                      "TABLE" if r["table_type"] == "BASE TABLE" else "VIEW")
            for r in rows
        ]

    def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        sql = """
            SELECT c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE, c.ORDINAL_POSITION,
                   CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_pk
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                  AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
            ) pk ON c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """
        rows = self.execute_query(sql, {"p1": schema, "p2": table, "p3": schema, "p4": table})
        return [
            ColumnInfo(
                column_name=r.get("COLUMN_NAME", ""),
                data_type=r.get("DATA_TYPE", ""),
                nullable=r.get("IS_NULLABLE") == "YES",
                is_pk=bool(r.get("is_pk")),
                ordinal_position=r.get("ORDINAL_POSITION", 0),
            ) for r in rows
        ]

    def execute_query(self, sql: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if not self._connection:
            self.connect()
        cur = self._connection.cursor()
        try:
            if params:
                cur.execute(sql, list(params.values()))
            else:
                cur.execute(sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            affected = cur.rowcount if isinstance(cur.rowcount, int) and cur.rowcount > -1 else 0
            return [{"ROWS_AFFECTED": affected}]
        finally:
            cur.close()

    def get_row_count(self, schema: str, table: str) -> int:
        rows = self.execute_query(
            f"SELECT COUNT(*) AS cnt FROM [{schema}].[{table}]"
        )
        return rows[0]["cnt"] if rows else 0
