"""Schema analysis service.

Provides analyze_datasource, get_schema_tree, and compare_schemas.
The analysis itself is delegated to the connector; the KB is managed by
schema_kb_service.  This module wires the two together and is the
single point of call for the schemas router.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def analyze_datasource(
    db: AsyncSession,
    datasource_id: int,
    schema_filter: Optional[str] = None,
    schema_filters: Optional[List[str]] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze a datasource and return schema statistics.

    Returns a dict with at minimum:
        tables: int, columns: int, schemas: list[str]
    """
    logger.warning(
        "schema_service.analyze_datasource called for ds=%s (stub - no connector yet)",
        datasource_id,
    )
    return {
        "tables": 0,
        "columns": 0,
        "schemas": [],
        "datasource_id": datasource_id,
        "status": "stub",
        "message": (
            "Schema analysis is not yet wired to a connector. "
            "Configure a datasource connection and re-run analysis."
        ),
    }


async def get_schema_tree(
    db: AsyncSession,
    datasource_id: int,
) -> Dict[str, Any]:
    """Return a hierarchical schema tree for a datasource.

    Structure: { datasource_id, schemas: [ { name, tables: [ { name, columns: [...] } ] } ] }
    """
    logger.warning(
        "schema_service.get_schema_tree called for ds=%s (stub)", datasource_id
    )
    return {
        "datasource_id": datasource_id,
        "schemas": [],
        "status": "stub",
    }


async def compare_schemas(
    db: AsyncSession,
    source_datasource_id: int,
    source_schema: Optional[str],
    source_table: Optional[str],
    target_datasource_id: int,
    target_schema: Optional[str],
    target_table: Optional[str],
) -> Dict[str, Any]:
    """Compare two schema objects and return a diff report."""
    logger.warning(
        "schema_service.compare_schemas called src_ds=%s tgt_ds=%s (stub)",
        source_datasource_id,
        target_datasource_id,
    )
    return {
        "source": {"datasource_id": source_datasource_id, "schema": source_schema, "table": source_table},
        "target": {"datasource_id": target_datasource_id, "schema": target_schema, "table": target_table},
        "added_columns": [],
        "removed_columns": [],
        "changed_columns": [],
        "status": "stub",
    }
