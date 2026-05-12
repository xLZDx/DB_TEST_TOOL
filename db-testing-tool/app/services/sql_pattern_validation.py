"""SQL pattern validation service."""
from __future__ import annotations
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def validate_test_definition_sql(sql: str) -> bool:
    """Stub: validate SQL pattern in test definition. Always returns True (no-op)."""
    logger.debug("SQL pattern validation: stub implementation (always valid)")
    return True


def validate_sql_pattern(sql: str) -> list:
    """Validate a SQL fragment and return a list of error strings.

    Returns an empty list when the SQL is acceptable (stub: always valid).
    """
    logger.debug("validate_sql_pattern: stub (always valid)")
    return []


def split_valid_invalid_test_defs(
    test_defs: List[dict],
) -> Tuple[List[dict], List[dict]]:
    """Split test definitions into valid and invalid based on pattern_errors field.

    A definition is invalid if it contains a non-empty ``pattern_errors`` dict
    with at least one non-empty list under the 'source' or 'target' key.
    All others are considered valid.
    """
    valid: List[dict] = []
    invalid: List[dict] = []
    for td in test_defs:
        errors = td.get("pattern_errors") or {}
        if isinstance(errors, dict):
            src_errs = errors.get("source") or []
            tgt_errs = errors.get("target") or []
            if src_errs or tgt_errs:
                invalid.append(td)
                continue
        valid.append(td)
    return valid, invalid
