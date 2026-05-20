from typing import Dict

class DbDialect:
    def __init__(self, name: str, null_handler: str, current_date: str, row_limit: str, extra_rules: str = ""):
        self.name = name
        self.null_handler = null_handler
        self.current_date = current_date
        self.row_limit = row_limit
        self.extra_rules = extra_rules

    def get_system_prompt_injection(self) -> str:
        return (
            f"You must generate strictly {self.name} compliant SQL.\n"
            f"- Use `{self.null_handler}` for null coalescence/handling.\n"
            f"- Use `{self.current_date}` for the current system date.\n"
            f"- To limit rows, use `{self.row_limit}`.\n"
            f"{self.extra_rules}"
        )

DIALECTS: Dict[str, DbDialect] = {
    "oracle": DbDialect(
        name="Oracle",
        null_handler="NVL",
        current_date="SYSDATE",
        row_limit="FETCH FIRST n ROWS ONLY",
        extra_rules="- Do NOT use ISNULL, GETDATE(), or LIMIT.\n- Use TO_CHAR and TO_DATE for type casting and formatting."
    ),
    "redshift": DbDialect(
        name="Redshift",
        null_handler="NVL", # Redshift supports NVL and COALESCE
        current_date="SYSDATE",
        row_limit="LIMIT n",
        extra_rules="- Use Postgres/Redshift compatible syntax.\n- Be mindful of schema prefixes."
    ),
    "mssql": DbDialect(
        name="MS SQL Server",
        null_handler="ISNULL",
        current_date="GETDATE()",
        row_limit="TOP (n)",
        extra_rules="- Do NOT use NVL or SYSDATE.\n- Use brackets [ ] for schema and table names if necessary."
    ),
    "mysql": DbDialect(
        name="MySQL",
        null_handler="IFNULL",
        current_date="NOW()",
        row_limit="LIMIT n",
        extra_rules="- Use backticks ` for schema and table names if necessary."
    ),
    "postgresql": DbDialect(
        name="PostgreSQL",
        null_handler="COALESCE",
        current_date="CURRENT_DATE",
        row_limit="LIMIT n",
        extra_rules="- Use double quotes \" for schema and table names if necessary."
    )
}

def get_dialect_prompt(dialect_name: str) -> str:
    """Retrieve the strict prompt injection for the target DB dialect."""
    # Default to Oracle if unknown
    dialect = DIALECTS.get(dialect_name.lower(), DIALECTS["oracle"])
    return dialect.get_system_prompt_injection()