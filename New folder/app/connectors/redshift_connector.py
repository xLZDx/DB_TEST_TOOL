"""Amazon Redshift connector using psycopg2 or redshift-connector (SSO)."""
from typing import Any, Dict, List, Optional
from app.connectors.base import BaseConnector, ConnectionResult, ColumnInfo, TableInfo
import logging
import os

logger = logging.getLogger(__name__)


class RedshiftConnector(BaseConnector):

    def __init__(self, host: str, port: int, database: str,
                 username: str, password: str, extra_params: Optional[Dict] = None):
        super().__init__(host, port or 5439, database, username, password, extra_params)
        mode = str((self.extra_params or {}).get("auth_mode", "password")).lower().strip()
        self._use_sso = mode in {"sso", "iam", "browser_saml"}

    def _build_password_kwargs(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.username,
            "password": self.password,
        }

    def _build_sso_kwargs(self) -> Dict[str, Any]:
        extras = self.extra_params or {}

        kwargs: Dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "iam": True,
            "ssl": bool(extras.get("ssl", True)),
            "credentials_provider": extras.get(
                "credentials_provider",
                "BrowserSamlCredentialsProvider",
            ),
        }

        passthrough_keys = [
            "login_url",
            "idp_host",
            "idp_port",
            "preferred_role",
            "region",
            "cluster_identifier",
            "db_user",
            "profile",
            "is_serverless",
            "serverless_acct_id",
            "serverless_work_group",
            "app_id",
            "app_name",
            "idp_response_timeout",
            "listen_port",
            "ssl_insecure",
        ]
        for key in passthrough_keys:
            value = extras.get(key)
            if value not in (None, ""):
                kwargs[key] = value

        if self.username and "user" not in kwargs:
            kwargs["user"] = self.username
        if self.password and "password" not in kwargs:
            kwargs["password"] = self.password

        return kwargs

    def _connect_with_password(self, timeout_seconds: int):
        import psycopg2
        kwargs = self._build_password_kwargs()
        kwargs["connect_timeout"] = timeout_seconds
        return psycopg2.connect(**kwargs)

    def _connect_with_sso(self, timeout_seconds: int):
        try:
            import redshift_connector
        except Exception as e:
            raise RuntimeError(
                "Redshift SSO requires redshift-connector. Install it in the application environment."
            ) from e

        kwargs = self._build_sso_kwargs()
        kwargs["timeout"] = timeout_seconds

        extras = self.extra_params or {}
        ca_bundle = extras.get("ca_bundle") or extras.get("ssl_root_cert")
        if ca_bundle:
            try:
                with open(str(ca_bundle), "r", encoding="utf-8", errors="ignore") as f:
                    head = f.read(512)
                head_l = head.lower()
                if "<html" in head_l or "<!doctype html" in head_l:
                    raise RuntimeError(
                        "Configured CA bundle is not a PEM certificate file (received HTML/login page). "
                        "Download the raw rjcert.pem file and set that path in TLS CA Bundle Path."
                    )
                if "-----begin certificate-----" not in head_l:
                    raise RuntimeError(
                        "Configured CA bundle does not contain PEM certificate blocks. "
                        "Ensure the file includes '-----BEGIN CERTIFICATE-----'."
                    )
            except FileNotFoundError:
                raise RuntimeError(f"CA bundle file not found: {ca_bundle}")
        old_aws_ca = os.environ.get("AWS_CA_BUNDLE")
        old_req_ca = os.environ.get("REQUESTS_CA_BUNDLE")
        try:
            if ca_bundle:
                os.environ["AWS_CA_BUNDLE"] = str(ca_bundle)
                os.environ["REQUESTS_CA_BUNDLE"] = str(ca_bundle)
            return redshift_connector.connect(**kwargs)
        finally:
            if ca_bundle:
                if old_aws_ca is None:
                    os.environ.pop("AWS_CA_BUNDLE", None)
                else:
                    os.environ["AWS_CA_BUNDLE"] = old_aws_ca
                if old_req_ca is None:
                    os.environ.pop("REQUESTS_CA_BUNDLE", None)
                else:
                    os.environ["REQUESTS_CA_BUNDLE"] = old_req_ca

    def test_connection(self) -> ConnectionResult:
        try:
            conn = self._connect_with_sso(20) if self._use_sso else self._connect_with_password(10)
            cur = conn.cursor()
            cur.execute("SELECT version()")
            ver = cur.fetchone()[0]
            cur.close()
            conn.close()
            return ConnectionResult(True, "Connected", ver)
        except Exception as e:
            msg = str(e)
            lower = msg.lower()
            if "certificate_verify_failed" in lower or "self-signed certificate" in lower:
                msg = (
                    f"{msg} | TLS certificate validation failed for SSO/IAM. "
                    "Provide corporate CA bundle path in Redshift SSO dialog (TLS CA Bundle Path) "
                    "or enable 'Skip TLS verification (temporary)'."
                )
            return ConnectionResult(False, msg)

    def connect(self):
        self._connection = self._connect_with_sso(30) if self._use_sso else self._connect_with_password(15)
        if hasattr(self._connection, "autocommit"):
            self._connection.autocommit = True

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
            WHERE schema_name NOT IN ('information_schema','pg_catalog','pg_internal')
            ORDER BY schema_name
        """
        return [r["schema_name"] for r in self.execute_query(sql)]

    def get_tables(self, schema: str) -> List[TableInfo]:
        sql = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %(schema)s
            ORDER BY table_name
        """
        rows = self.execute_query(sql, {"schema": schema})
        results = []
        for r in rows:
            ttype = "TABLE" if r["table_type"] == "BASE TABLE" else "VIEW"
            results.append(TableInfo(r["table_schema"], r["table_name"], ttype))
        return results

    def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        sql = """
            SELECT c.column_name, c.data_type, c.is_nullable, c.ordinal_position,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %(schema)s AND tc.table_name = %(table)s
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_schema = %(schema)s AND c.table_name = %(table)s
            ORDER BY c.ordinal_position
        """
        rows = self.execute_query(sql, {"schema": schema, "table": table})
        return [
            ColumnInfo(
                column_name=r["column_name"],
                data_type=r["data_type"],
                nullable=r["is_nullable"] == "YES",
                is_pk=bool(r["is_pk"]),
                ordinal_position=r["ordinal_position"],
            ) for r in rows
        ]

    def execute_query(self, sql: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if not self._connection:
            self.connect()
        cur = self._connection.cursor()
        try:
            cur.execute(sql, params or {})
            if cur.description:
                rows = cur.fetchall()
                if not rows:
                    return []
                first = rows[0]
                if isinstance(first, dict):
                    return [dict(row) for row in rows]
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in rows]
            affected = cur.rowcount if isinstance(cur.rowcount, int) and cur.rowcount > -1 else 0
            return [{"ROWS_AFFECTED": affected}]
        finally:
            cur.close()

    def get_row_count(self, schema: str, table: str) -> int:
        rows = self.execute_query(
            f'SELECT COUNT(*) AS cnt FROM "{schema}"."{table}"'
        )
        return rows[0]["cnt"] if rows else 0
