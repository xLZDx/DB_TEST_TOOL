"""SQL pattern validation service stub."""
import logging

logger = logging.getLogger(__name__)


def validate_test_definition_sql(sql: str) -> bool:
    """Stub: validate SQL pattern in test definition.
    
    TODO: Implement actual SQL validation.
    """
    logger.debug("SQL pattern validation: stub implementation (always valid)")
    return True
