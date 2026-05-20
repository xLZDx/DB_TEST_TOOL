"""Mappings router — DRD preview, import, AI summary, and Mapping Rule CRUD."""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mapping_rule import MappingRule
from app.services.drd_import_service import (
    extract_drd_metadata,
    generate_drd_tests,
    parse_drd_file,
    preview_file,
    read_excel_all_sheets,
    validate_column_mappings_with_kb,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


# ── DRD Preview ─────────────────────────────────────────────────────────────

@router.post("/drd-preview")
async def drd_preview(
    file: UploadFile = File(...),
    sheet_name: str = Form(""),
):
    """Preview a DRD (Data Requirements Document) file.

    Returns detected sheets, headers, metadata, and sample rows so the UI
    can display the column-selection step before import.
    """
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "File must be CSV or Excel format")

    file_bytes = await file.read()
    filename = file.filename or "file.xlsx"
    result = preview_file(file_bytes, filename, sheet_name=sheet_name.strip() or None)

    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("xlsx", "xls"):
        try:
            all_sheets = read_excel_all_sheets(file_bytes)
            sheet_infos = []
            for sn, rows in all_sheets.items():
                meta = extract_drd_metadata(file_bytes, filename, sheet_name=sn)
                sheet_infos.append({"name": sn, "row_count": len(rows), "metadata": meta})
            result["sheet_details"] = sheet_infos
        except Exception:
            pass

    return result


# ── DRD Import (generate test candidates) ───────────────────────────────────

@router.post("/drd-import")
async def drd_import(
    file: UploadFile = File(...),
    selected_fields: str = "",
    target_schema: str = "",
    target_table: str = "",
    source_table: str = "",
    main_grain: str = "",
    source_datasource_id: int = 1,
    target_datasource_id: int = 1,
    require_ai: bool = True,
    ai_mode: str = "kb_only",
    single_db_testing: bool = True,
    cross_db_optional: bool = True,
    sheet_name: str = "",
):
    """Parse a DRD file and return suggested test case definitions.

    The UI sends the file as multipart/form-data with query params for
    selected_fields, target/source tables, datasource IDs, and AI options.
    """
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "File must be CSV or Excel format")

    file_bytes = await file.read()
    filename = file.filename or "file.xlsx"

    selected = [f.strip() for f in selected_fields.split(",") if f.strip()] if selected_fields else []

    try:
        parsed = parse_drd_file(
            file_bytes=file_bytes,
            filename=filename,
            selected_fields=selected,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=target_datasource_id,
            default_source_table=source_table,
            sheet_name=sheet_name.strip() or None,
        )
    except Exception as exc:
        raise HTTPException(422, f"Failed to parse DRD file: {exc}") from exc

    column_mappings = parsed.get("column_mappings") or []
    errors = parsed.get("errors") or []

    # KB validation (attribute resolution against PDM)
    kb_result: dict = {"validated_count": 0, "unresolved_count": 0, "mismatch_highlights": []}
    try:
        kb_result = validate_column_mappings_with_kb(
            column_mappings=column_mappings,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=target_datasource_id,
        )
        column_mappings = kb_result.get("column_mappings") or column_mappings
    except Exception as kb_exc:
        logger.warning("KB validation failed (non-fatal): %s", kb_exc)
        errors.append(f"KB validation skipped: {kb_exc}")

    # Generate suggested tests from resolved mappings
    suggested_tests: list = []
    baseline_skipped_rows: list = []
    baseline_skipped_count = 0
    baseline_invalid_sql_count = 0
    inferred_main_grain = main_grain

    try:
        gen_result = generate_drd_tests(
            column_mappings=column_mappings,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=target_datasource_id,
            main_grain=main_grain,
            single_db_testing=single_db_testing,
            cross_db_optional=cross_db_optional,
            include_diagnostics=True,
            default_source_table=source_table,
        )
        if isinstance(gen_result, dict):
            suggested_tests = gen_result.get("tests") or []
            baseline_skipped_rows = gen_result.get("skipped_rows") or []
            baseline_skipped_count = gen_result.get("skipped_count") or len(baseline_skipped_rows)
            baseline_invalid_sql_count = gen_result.get("invalid_sql_count") or 0
            inferred_main_grain = gen_result.get("main_grain") or main_grain
        else:
            suggested_tests = gen_result or []
    except Exception as gen_exc:
        logger.exception("Test generation failed")
        errors.append(f"Test generation error: {gen_exc}")

    return {
        "status": "success" if not errors else "partial",
        "message": (
            f"Generated {len(suggested_tests)} test candidate(s) from "
            f"{len(column_mappings)} mapped column(s)."
        ),
        "suggested_tests": suggested_tests,
        "column_mappings_count": len(column_mappings),
        "kb_validation": {
            "validated_count": kb_result.get("validated_count", 0),
            "unresolved_count": kb_result.get("unresolved_count", 0),
        },
        "baseline_skipped_rows": baseline_skipped_rows,
        "baseline_skipped_count": baseline_skipped_count,
        "baseline_invalid_sql_count": baseline_invalid_sql_count,
        "main_grain": inferred_main_grain,
        "errors": errors,
    }


# ── DRD AI Summary ──────────────────────────────────────────────────────────

@router.post("/drd-ai-summary")
async def drd_ai_summary(
    file: UploadFile = File(...),
    selected_fields: str = "",
    target_schema: str = "",
    target_table: str = "",
    source_table: str = "",
    sql_text: str = "",
    main_grain: str = "",
    ai_mode: str = "ghc_kb",
    source_datasource_id: int = 1,
    target_datasource_id: int = 1,
    single_db_testing: bool = True,
    cross_db_optional: bool = True,
    sheet_name: str = "",
):
    """Parse DRD file and return KB-validated mapping analysis with optional AI enrichment.

    Used by the mappings page to show the attribute-level analysis before
    the user decides which columns to import.
    """
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "File must be CSV or Excel format")

    file_bytes = await file.read()
    filename = file.filename or "file.xlsx"

    selected = [f.strip() for f in selected_fields.split(",") if f.strip()] if selected_fields else []

    try:
        parsed = parse_drd_file(
            file_bytes=file_bytes,
            filename=filename,
            selected_fields=selected,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=target_datasource_id,
            default_source_table=source_table,
            sheet_name=sheet_name.strip() or None,
        )
    except Exception as exc:
        raise HTTPException(422, f"Failed to parse DRD file: {exc}") from exc

    column_mappings = parsed.get("column_mappings") or []
    errors = parsed.get("errors") or []
    metadata = parsed.get("metadata") or {}

    kb_result: dict = {"validated_count": 0, "unresolved_count": 0, "mismatch_highlights": [], "confidence_details": []}
    try:
        kb_result = validate_column_mappings_with_kb(
            column_mappings=column_mappings,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=target_datasource_id,
        )
    except Exception as kb_exc:
        logger.warning("KB validation failed (non-fatal): %s", kb_exc)
        errors.append(f"KB validation skipped: {kb_exc}")

    summary_lines: list[str] = []
    validated = kb_result.get("validated_count", 0)
    unresolved = kb_result.get("unresolved_count", 0)
    total = len(column_mappings)
    summary_lines.append(f"Parsed {total} column mapping(s) from DRD.")
    if validated or unresolved:
        summary_lines.append(f"KB validation: {validated} resolved, {unresolved} unresolved.")

    mismatches = kb_result.get("mismatch_highlights") or []
    if mismatches:
        summary_lines.append(f"Top mismatches: {'; '.join(mismatches[:5])}")

    # If sql_text provided, briefly note whether source attributes appear in it
    if sql_text.strip():
        sql_upper = sql_text.upper()
        missing_in_sql: list[str] = []
        for cm in column_mappings[:30]:
            attr = (cm.get("source_attribute") or "").strip().upper()
            if attr and attr not in sql_upper:
                missing_in_sql.append(attr)
        if missing_in_sql:
            summary_lines.append(
                f"{len(missing_in_sql)} DRD attribute(s) not found in provided SQL "
                f"(e.g. {', '.join(missing_in_sql[:5])})."
            )
        else:
            summary_lines.append("All checked DRD attributes appear in the provided SQL.")

    return {
        "status": "success",
        "summary": " ".join(summary_lines),
        "total_mappings": total,
        "validated_count": validated,
        "unresolved_count": unresolved,
        "mismatch_highlights": mismatches[:50],
        "confidence_details": (kb_result.get("confidence_details") or [])[:20],
        "metadata": metadata,
        "errors": errors,
    }


# ── Mapping Rule CRUD ────────────────────────────────────────────────────────

class MappingRuleCreate(BaseModel):
    name: str
    source_datasource_id: int
    source_schema: Optional[str] = None
    source_table: str
    source_columns: Optional[str] = None   # JSON array string
    target_datasource_id: int
    target_schema: Optional[str] = None
    target_table: str
    target_columns: Optional[str] = None   # JSON array string
    transformation_sql: Optional[str] = None
    join_condition: Optional[str] = None
    filter_condition: Optional[str] = None
    rule_type: str = "direct"
    description: Optional[str] = None


def _rule_dict(r: MappingRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "source_datasource_id": r.source_datasource_id,
        "source_schema": r.source_schema,
        "source_table": r.source_table,
        "source_columns": r.source_columns,
        "target_datasource_id": r.target_datasource_id,
        "target_schema": r.target_schema,
        "target_table": r.target_table,
        "target_columns": r.target_columns,
        "transformation_sql": r.transformation_sql,
        "join_condition": r.join_condition,
        "filter_condition": r.filter_condition,
        "rule_type": r.rule_type,
        "description": r.description,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("")
async def list_mappings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MappingRule).order_by(MappingRule.name))
    items = result.scalars().all()
    return {"mappings": [_rule_dict(r) for r in items], "total": len(items)}


@router.post("")
async def create_mapping(body: MappingRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = MappingRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id, "name": rule.name, "status": "created"}


@router.get("/{mapping_id}")
async def get_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(MappingRule, mapping_id)
    if not rule:
        raise HTTPException(404, "Mapping rule not found")
    return _rule_dict(rule)


@router.put("/{mapping_id}")
async def update_mapping(mapping_id: int, body: MappingRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(MappingRule, mapping_id)
    if not rule:
        raise HTTPException(404, "Mapping rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return _rule_dict(rule)


@router.delete("/{mapping_id}")
async def delete_mapping(mapping_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(MappingRule, mapping_id)
    if not rule:
        raise HTTPException(404, "Mapping rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True}


class BulkDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/bulk-delete")
async def bulk_delete_mappings(body: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    deleted = 0
    for rule_id in body.ids:
        rule = await db.get(MappingRule, rule_id)
        if rule:
            await db.delete(rule)
            deleted += 1
    await db.commit()
    return {"deleted": deleted}

