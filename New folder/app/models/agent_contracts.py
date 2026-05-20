from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class TfsContext(BaseModel):
    """Output of the Context Builder Agent. Represents the cleaned, consolidated requirement."""
    work_item_id: str = Field(..., description="The TFS Work Item ID")
    title: str = Field(..., description="Title of the work item")
    description: str = Field(..., description="Cleaned description of the ETL requirement")
    comments: List[str] = Field(default_factory=list, description="Relevant comments from TFS")
    artifact_contents: List[str] = Field(default_factory=list, description="Extracted text from attached Excel/CSV mappings")
    schema_ddl: str = Field(..., description="DDL and schema information for ONLY the tables mentioned in the requirement")

class MappingRule(BaseModel):
    """Represents a single field-level transformation."""
    source_column: str = Field(..., description="Source column name")
    target_column: str = Field(..., description="Target column name")
    transformation: str = Field(default="Direct", description="Transformation logic (e.g., Direct, NVL(col, 0), UPPER(col))")
    rule_type: str = Field(default="direct", description="Categorization: direct, complex, lookup")

class EtlMappingSpec(BaseModel):
    """Output of the Analysis Agent. Represents the parsed ETL logic ready for coding."""
    source_tables: List[str] = Field(..., description="List of fully qualified source tables")
    target_tables: List[str] = Field(..., description="List of fully qualified target tables")
    business_keys: List[str] = Field(default_factory=list, description="Columns used to join source and target")
    join_conditions: str = Field(..., description="Explicit SQL JOIN conditions for lookups and staging")
    mappings: List[MappingRule] = Field(default_factory=list, description="Field level mappings")
    filters: str = Field(default="", description="WHERE clause filters (e.g., Active Flag = 'Y')")

class AgentPhaseReport(BaseModel):
    """Transparent audit log from one agent phase. Returned to the user in semi-manual mode."""
    phase: str = Field(..., description="Phase name: context_builder | analysis | design | validation")
    documents_reviewed: List[str] = Field(default_factory=list, description="Document names / URLs actually read")
    tables_identified: List[str] = Field(default_factory=list, description="Source and target tables identified from artifacts")
    decisions: List[str] = Field(default_factory=list, description="Key decisions the agent made (e.g., which tables to use, which rules to apply)")
    warnings: List[str] = Field(default_factory=list, description="Issues: hallucinated tables, missing docs, low-confidence decisions")
    result_summary: str = Field(default="", description="1-2 sentence summary of what this phase produced")
    result_payload: Optional[Dict[str, Any]] = Field(default=None, description="Serialized result object for display")


class TestCaseDesign(BaseModel):
    """Output of the Design Agent. Represents an executable test case."""
    name: str = Field(..., description="Descriptive name of the test case")
    test_type: str = Field(..., description="Type of test: value_match, row_count, null_check, referential_integrity")
    severity: str = Field(default="medium", description="Severity: high, medium, low")
    description: str = Field(..., description="Business explanation of what this test validates")
    db_dialect: str = Field(..., description="The SQL dialect used for the queries (e.g., Oracle, MSSQL)")
    source_query: str = Field(..., description="SQL query against the source database")
    target_query: str = Field(..., description="SQL query against the target database")
    expected_result: str = Field(default="0", description="Expected numeric result, usually 0 representing no mismatches")