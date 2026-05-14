"""Per-attribute test generator service.

Generates one test case per target column (e.g. 367 tests for 367 matched attributes).
Each test includes the full CTE/JOIN source query that validates a single attribute
from source to target using the resolved mapping.

Supports CT, DRD, and Chat flow test generation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def generate_attribute_tests(
    analysis_rows: List[Dict[str, Any]],
    target_schema: str,
    target_table: str,
    source_schema: str = "",
    primary_source_table: str = "",
    generated_sql: str = "",
    join_sql: str = "",
    source_datasource_id: int = 0,
    target_datasource_id: int = 0,
    pbi_id: str = "",
    suite_prefix: str = "CT",
    grain_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate one test per attribute from comparison results.

    Args:
        analysis_rows: DRD rows with column, source_attribute, generated_expression, etc.
        target_schema: e.g. SSDS_TRANSACTIONS_OWNER
        target_table: e.g. AVY_FACT
        source_schema: e.g. CCAL_REPL_OWNER
        primary_source_table: e.g. TXN (main source alias B)
        generated_sql: full generated CTE/INSERT SQL
        join_sql: extracted JOIN block from generated SQL
        source_datasource_id: DS ID for source
        target_datasource_id: DS ID for target
        pbi_id: PBI reference (e.g. PBI2674782)
        suite_prefix: CT, DRD, or CHAT
        grain_columns: columns forming the business key (for join condition)

    Returns:
        List of test case dicts ready for POST /api/tests
    """
    target_schema_u = (target_schema or "").strip().upper()
    target_table_u = (target_table or "").strip().upper()
    source_schema_u = (source_schema or "").strip().upper()
    primary_src = (primary_source_table or "").strip().upper()
    grain_cols = [g.upper() for g in (grain_columns or ["TXN_ID"])]

    # Extract FROM + JOIN block from generated SQL
    from_join_block = _extract_from_join_block(generated_sql or join_sql)

    tests = []
    for i, row in enumerate(analysis_rows, start=1):
        col = (row.get("column") or row.get("physical_name") or "").strip().upper()
        if not col:
            continue

        source_attr = (row.get("source_attribute") or "").strip().upper()
        gen_expr = (row.get("generated_expression") or "").strip()
        source_table = (row.get("source_table") or primary_src).strip().upper()
        source_sch = (row.get("source_schema") or source_schema_u).strip().upper()
        transformation = (row.get("transformation") or "").strip()

        # Build validation query for this single attribute
        source_query = _build_attribute_validation_query(
            target_column=col,
            source_expression=gen_expr or f"S.{source_attr}" if source_attr else f"S.{col}",
            from_join_block=from_join_block,
            grain_columns=grain_cols,
            target_schema=target_schema_u,
            target_table=target_table_u,
            source_schema=source_sch,
            source_table=source_table,
        )

        # Description includes mapping lineage
        desc_parts = [f"{pbi_id}: " if pbi_id else ""]
        desc_parts.append(f"{suite_prefix} attribute validation [{i}] {col}")
        if source_attr and source_attr != col:
            desc_parts.append(f" | Source: {source_sch}.{source_table}.{source_attr}" if source_sch else f" | Source: {source_table}.{source_attr}")
        if transformation:
            desc_parts.append(f" | Transform: {transformation[:100]}")

        test = {
            "name": f"{suite_prefix}_{target_table_u}_{col}",
            "test_type": "value_match",
            "source_datasource_id": source_datasource_id or None,
            "target_datasource_id": target_datasource_id or None,
            "severity": "high" if col in grain_cols else "medium",
            "description": "".join(desc_parts),
            "source_query": source_query,
            "target_query": f"-- Target column: {target_schema_u}.{target_table_u}.{col}\nSELECT {col} FROM {target_schema_u}.{target_table_u} WHERE ROWNUM <= 100",
            "expected_result": "0",
        }
        tests.append(test)

    return tests


def generate_ct_suite(
    analysis_rows: List[Dict[str, Any]],
    generated_sql: str,
    target_schema: str,
    target_table: str,
    source_datasource_id: int = 0,
    target_datasource_id: int = 0,
    pbi_id: str = "",
    grain_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate CT_TEST suite — per-attribute with full CTE/INSERT validation."""
    # Extract primary source from generated SQL
    source_schema, primary_table = _extract_primary_source(generated_sql)

    return generate_attribute_tests(
        analysis_rows=analysis_rows,
        target_schema=target_schema,
        target_table=target_table,
        source_schema=source_schema,
        primary_source_table=primary_table,
        generated_sql=generated_sql,
        source_datasource_id=source_datasource_id,
        target_datasource_id=target_datasource_id,
        pbi_id=pbi_id,
        suite_prefix="CT",
        grain_columns=grain_columns,
    )


def generate_drd_suite(
    analysis_rows: List[Dict[str, Any]],
    generated_sql: str,
    target_schema: str,
    target_table: str,
    source_datasource_id: int = 0,
    target_datasource_id: int = 0,
    pbi_id: str = "",
    grain_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate DRD_TEST suite — per-attribute with full join query."""
    source_schema, primary_table = _extract_primary_source(generated_sql)

    return generate_attribute_tests(
        analysis_rows=analysis_rows,
        target_schema=target_schema,
        target_table=target_table,
        source_schema=source_schema,
        primary_source_table=primary_table,
        generated_sql=generated_sql,
        source_datasource_id=source_datasource_id,
        target_datasource_id=target_datasource_id,
        pbi_id=pbi_id,
        suite_prefix="DRD",
        grain_columns=grain_columns,
    )


def generate_chat_suite(
    analysis_rows: List[Dict[str, Any]],
    generated_sql: str,
    target_schema: str,
    target_table: str,
    source_datasource_id: int = 0,
    target_datasource_id: int = 0,
    pbi_id: str = "",
    grain_columns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate CHAT_TEST suite — per-attribute with source validation."""
    source_schema, primary_table = _extract_primary_source(generated_sql)

    return generate_attribute_tests(
        analysis_rows=analysis_rows,
        target_schema=target_schema,
        target_table=target_table,
        source_schema=source_schema,
        primary_source_table=primary_table,
        generated_sql=generated_sql,
        source_datasource_id=source_datasource_id,
        target_datasource_id=target_datasource_id,
        pbi_id=pbi_id,
        suite_prefix="CHAT",
        grain_columns=grain_columns,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_attribute_validation_query(
    target_column: str,
    source_expression: str,
    from_join_block: str,
    grain_columns: List[str],
    target_schema: str,
    target_table: str,
    source_schema: str = "",
    source_table: str = "",
) -> str:
    """Build a validation query that compares source expression vs target column.

    Uses NVL comparison pattern:
    SELECT COUNT(*) FROM source_joins
    LEFT JOIN target ON grain
    WHERE NVL(source_expr, '-999') <> NVL(target.col, '-999')
    """
    # Grain join condition
    grain_join = " AND ".join(
        f"S.{g} = T.{g}" for g in grain_columns
    )

    # Source expression — ensure it has an alias qualifier
    src_expr = source_expression
    if not any(src_expr.startswith(f"{q}.") for q in ["S", "B", "T"]) and "." not in src_expr and "(" not in src_expr:
        src_expr = f"S.{src_expr}"

    lines = [
        f"-- Attribute validation: {target_column}",
        f"-- Source expression: {source_expression}",
        f"SELECT /*+ PARALLEL(8) */",
        f"COUNT(*) AS cnt",
    ]

    if from_join_block:
        lines.append(from_join_block)
    else:
        src_full = f"{source_schema}.{source_table}" if source_schema else source_table
        lines.append(f"FROM {src_full} S")

    lines.extend([
        f"LEFT JOIN {target_schema}.{target_table} T",
        f"ON {grain_join}",
        f"WHERE NVL(TO_CHAR({src_expr}), '-999') <> NVL(TO_CHAR(T.{target_column}), '-999')",
    ])

    return "\n".join(lines)


def _extract_from_join_block(sql: str) -> str:
    """Extract the FROM + JOIN section from a SQL statement."""
    if not sql:
        return ""

    # Find FROM keyword at level 0
    upper = sql.upper()
    # Look for FROM that starts the main query body
    from_match = re.search(
        r"\bFROM\b\s+([\w.$\"]+(?:\s+\w+)?(?:\s*\n?\s*(?:LEFT|RIGHT|INNER|OUTER|CROSS|FULL)?\s*(?:OUTER\s+)?JOIN\s+[\s\S]*?)?)"
        r"(?=\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|$)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if from_match:
        block = from_match.group(0).strip()
        # Limit to reasonable size
        if len(block) > 10000:
            block = block[:10000]
        return block

    return ""


def _extract_primary_source(sql: str) -> tuple:
    """Extract primary source schema.table from SQL (first FROM table)."""
    if not sql:
        return ("", "")

    m = re.search(
        r"\bFROM\s+([\w$#]+)\.([\w$#]+)",
        sql,
        flags=re.IGNORECASE,
    )
    if m:
        return (m.group(1).upper(), m.group(2).upper())

    m = re.search(r"\bFROM\s+([\w$#]+)", sql, flags=re.IGNORECASE)
    if m:
        return ("", m.group(1).upper())

    return ("", "")
