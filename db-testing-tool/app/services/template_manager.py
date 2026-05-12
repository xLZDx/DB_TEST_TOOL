"""Mapping template management service for different Excel import formats."""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class TemplateType(Enum):
    """Available mapping template types."""
    BASIC = "basic"
    ENTERPRISE = "enterprise" 
    DATA_WAREHOUSE = "data_warehouse"
    ETL_PIPELINE = "etl_pipeline"


@dataclass
class TemplateColumn:
    """Definition of a template column."""
    name: str
    field: str
    required: bool = False
    data_type: str = "string"
    description: str = ""
    sample_value: str = ""
    aliases: List[str] = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


@dataclass 
class MappingTemplate:
    """Complete mapping template definition."""
    name: str
    type: TemplateType
    description: str
    columns: List[TemplateColumn]
    example_data: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.example_data is None:
            self.example_data = []


class TemplateManager:
    """Manages different mapping template types."""
    
    def __init__(self):
        self._templates = {
            TemplateType.BASIC: self._create_basic_template(),
            TemplateType.ENTERPRISE: self._create_enterprise_template(),
            TemplateType.DATA_WAREHOUSE: self._create_data_warehouse_template(),
            TemplateType.ETL_PIPELINE: self._create_etl_pipeline_template()
        }
    
    def get_template(self, template_type: TemplateType) -> MappingTemplate:
        """Get template by type."""
        return self._templates[template_type]
    
    def get_all_templates(self) -> Dict[TemplateType, MappingTemplate]:
        """Get all available templates."""
        return self._templates.copy()
    
    def detect_template_type(self, headers: List[str]) -> Optional[TemplateType]:
        """Auto-detect template type from Excel headers."""
        headers_lower = [h.lower().strip() for h in headers if h]
        
        # Score each template based on header matches
        scores = {}
        for template_type, template in self._templates.items():
            score = 0
            total_required = 0
            required_matches = 0
            
            for col in template.columns:
                if col.required:
                    total_required += 1
                
                # Check if column name or aliases match
                col_matches = [col.name.lower()]
                col_matches.extend([alias.lower() for alias in col.aliases])
                
                if any(match in headers_lower for match in col_matches):
                    if col.required:
                        required_matches += 1
                        score += 3  # Higher weight for required columns
                    else:
                        score += 1  # Lower weight for optional columns
            
            # Apply penalty only if required columns are missing
            # Use softer penalty: reduce score based on missing required columns
            if total_required > 0:
                missing_required = total_required - required_matches
                # Subtract 2 points for each missing required column (softer than ratio multiplication)
                final_score = score - (missing_required * 2)
                scores[template_type] = max(0, final_score)  # Don't go negative
            else:
                scores[template_type] = score
        
        # Return template with highest score if above threshold
        if scores:
            best_template = max(scores, key=scores.get)
            # Lower threshold to 2 to be more lenient
            if scores[best_template] >= 2:
                return best_template
        
        return None
    
    def _create_basic_template(self) -> MappingTemplate:
        """Create simplified basic mapping template for A->B validation with optional joins."""
        return MappingTemplate(
            name="Basic Mapping Rules",
            type=TemplateType.BASIC,
            description="Simplified mapping template for source-to-target data validation with optional transformation and join logic",
            columns=[
                TemplateColumn("Rule Name", "name", required=True, 
                              description="Name of the mapping rule",
                              sample_value="Customer Name to Warehouse",
                              aliases=["name", "mapping name", "rule"]),
                TemplateColumn("Source Table", "source_table", required=True,
                              description="Source table name (with optional schema prefix)",
                              sample_value="public.customers",
                              aliases=["src table", "source", "from table"]),
                TemplateColumn("Target Table", "target_table", required=True,
                              description="Target table name (with optional schema prefix)",
                              sample_value="warehouse.dim_customers",
                              aliases=["tgt table", "target", "to table"]),
                TemplateColumn("Transformation SQL Query", "transformation_sql",
                              description="Complete SQL showing the transformation logic (SELECT statement with joins, filters, transformations)",
                              sample_value="SELECT UPPER(TRIM(c.customer_name)) as cust_name, c.customer_id, l.location_name FROM customers c LEFT JOIN locations l ON c.location_id = l.id WHERE c.status = 'ACTIVE'",
                              aliases=["transformation", "transform", "sql query", "query", "transformation logic"]),
                TemplateColumn("Filter Condition", "filter_condition",
                              description="Optional WHERE clause filter conditions",
                              sample_value="status = 'ACTIVE' AND customer_name IS NOT NULL",
                              aliases=["filter", "filter condition", "where", "where clause"]),
                TemplateColumn("Join Condition", "join_condition",
                              description="Optional JOIN conditions for multi-table validation",
                              sample_value="src.location_id = lookup.id",
                              aliases=["join", "join condition", "joins"]),
                TemplateColumn("Description", "description",
                              description="Description of the mapping rule and business logic",
                              sample_value="Validates customer name transformation from source to data warehouse with location lookup and active status filter",
                              aliases=["desc", "notes", "comments"])
            ]
        )
    
    def _create_enterprise_template(self) -> MappingTemplate:
        """Create enterprise template based on the DRD CSV structure."""
        return MappingTemplate(
            name="Enterprise Data Mapping",
            type=TemplateType.ENTERPRISE,
            description="Comprehensive enterprise-level mapping template based on Lighthouse data warehouse structure",
            columns=[
                # Rule identification
                TemplateColumn("Rule Name", "name", required=True,
                              description="Name of the mapping rule",
                              sample_value="SHADOW Transaction Type Code Mapping"),
                TemplateColumn("Rule Type", "rule_type", 
                              description="Type of mapping rule",
                              sample_value="lookup"),
                
                # Target (Lighthouse) attributes
                TemplateColumn("Logical Name", "logical_name", required=True,
                              description="Logical name of attribute (without underscores)",
                              sample_value="SHADOW Transaction Type Code",
                              aliases=["logical name of attribute"]),
                TemplateColumn("Physical Name", "physical_name", required=True,
                              description="Physical name of attribute (actual column name)",
                              sample_value="SHDW_TXN_TP_CD", 
                              aliases=["physical name of attribute"]),
                TemplateColumn("Target Data Type Oracle", "target_datatype_oracle",
                              description="Data type in Oracle target",
                              sample_value="VARCHAR2(50)",
                              aliases=["data type in oracle"]),
                TemplateColumn("Target Nullable Oracle", "target_nullable_oracle",
                              description="Nullable in Oracle (Yes/No)",
                              sample_value="Yes",
                              aliases=["nullable in table and in oracle view"]),
                TemplateColumn("Target Data Type Redshift", "target_datatype_redshift", 
                              description="Data type in Redshift target",
                              sample_value="character varying(50)",
                              aliases=["data type in redshift"]),
                TemplateColumn("Target Nullable Redshift", "target_nullable_redshift",
                              description="Nullable in Redshift (Yes/No)", 
                              sample_value="Yes",
                              aliases=["nullable in redshift table"]),
                TemplateColumn("Business Definition", "business_definition",
                              description="Business definition and purpose",
                              sample_value="Possible values: ORG, OLD, NEW, REV, REP"),
                TemplateColumn("Sample Data Values", "sample_data_values",
                              description="Sample data values",
                              sample_value="OLD, ORG, REP, REV, NEW",
                              aliases=["sample data values"]),
                
                # Source attributes  
                TemplateColumn("Source Datasource ID", "source_datasource_id", required=True,
                              data_type="integer", description="ID of source datasource",
                              sample_value="1",
                              aliases=["source ds id", "src datasource id"]),
                TemplateColumn("Source Schema", "source_schema",
                              description="Source schema name",
                              sample_value="CCAL_REPL_OWNER"),
                TemplateColumn("Source Table", "source_table", required=True,
                              description="Source table name", 
                              sample_value="TXN"),
                TemplateColumn("Source Attribute Name", "source_columns",
                              description="Source attribute/column name",
                              sample_value="SRC_TXN_TP",
                              aliases=["source attribute name"]),
                TemplateColumn("Source Data Type", "source_datatype",
                              description="Source data type",
                              sample_value="VARCHAR2(10)",
                              aliases=["data type"]),
                TemplateColumn("Source Nullable", "source_nullable",
                              description="Source nullable (Yes/No)",
                              sample_value="Yes",
                              aliases=["nullable"]),
                
                # Target system info
                TemplateColumn("Target Datasource ID", "target_datasource_id", required=True,
                              data_type="integer", description="ID of target datasource",
                              sample_value="2",
                              aliases=["target ds id", "tgt datasource id"]),
                TemplateColumn("Target Schema", "target_schema",
                              description="Target schema name",
                              sample_value="SSDS_DAL_OWNER"),  
                TemplateColumn("Target Table", "target_table", required=True,
                              description="Target table name",
                              sample_value="ACTIVITY_FACT_V"),
                TemplateColumn("Target Columns", "target_columns",
                              description="Target column name(s)",
                              sample_value="SHDW_TXN_TP_CD",
                              aliases=["target column"]),
                
                # Transformation and business logic
                TemplateColumn("Transformation Rules", "transformation_sql",
                              description="Transformation/Business Rules/Join Conditions",
                              sample_value="Look up using TXN.SRC_TXN_TP=SHDW_TXN_TP.SRC_TXN_TP",
                              aliases=["transformation", "business rules", "join conditions"]),
                TemplateColumn("Notes Comments", "notes_comments", 
                              description="Notes and comments",
                              sample_value="Note to Dev team: Additional validation required",
                              aliases=["notes", "comments", "notes / comments"]),
                
                # Additional metadata
                TemplateColumn("Action", "action",
                              description="Action on attribute (Add/Update/Remove)", 
                              sample_value="Add",
                              aliases=["action on attribute"]),
                TemplateColumn("Include in View", "include_in_view",
                              description="Include in view (Yes/No/N)",
                              sample_value="Yes",
                              aliases=["include in view"]),
                TemplateColumn("PBI Number", "pbi_number",
                              description="Product Backlog Item number",
                              sample_value="1912566",
                              aliases=["pbi number", "table pbi number"]),
                TemplateColumn("Description", "description",
                              description="Additional description",
                              sample_value="Enterprise mapping rule for transaction type codes")
            ],
            example_data=[
                {
                    "Rule Name": "SHADOW Transaction Type Code Mapping",
                    "Logical Name": "SHADOW Transaction Type Code", 
                    "Physical Name": "SHDW_TXN_TP_CD",
                    "Target Data Type Oracle": "VARCHAR2(50)",
                    "Source Schema": "CCAL_REPL_OWNER",
                    "Source Table": "TXN", 
                    "Source Attribute Name": "SRC_TXN_TP",
                    "Transformation Rules": "Direct mapping with validation"
                }
            ]
        )
    
    def _create_data_warehouse_template(self) -> MappingTemplate:
        """Create data warehouse specific template."""
        return MappingTemplate(
            name="Data Warehouse Mapping", 
            type=TemplateType.DATA_WAREHOUSE,
            description="Template for data warehouse ETL and dimensional modeling scenarios",
            columns=[
                TemplateColumn("Rule Name", "name", required=True,
                              description="Name of the mapping rule",
                              sample_value="Customer Dimension Load"),
                TemplateColumn("Layer", "layer", 
                              description="Data warehouse layer (staging/ods/dwh/mart)",
                              sample_value="dwh"),
                TemplateColumn("Dimension Type", "dimension_type",
                              description="Type of dimension (scd1/scd2/fact/bridge)",
                              sample_value="scd2"),
                TemplateColumn("Source System", "source_system", required=True,
                              description="Source system name",
                              sample_value="CRM_PROD"),
                TemplateColumn("Source Schema", "source_schema",
                              description="Source schema",
                              sample_value="dbo"),
                TemplateColumn("Source Table", "source_table", required=True,
                              description="Source table name",
                              sample_value="customers"),
                TemplateColumn("Source Columns", "source_columns",
                              description="Source column names (JSON array)",
                              sample_value='["customer_id","customer_name","email"]'),
                TemplateColumn("Target Schema", "target_schema", required=True,
                              description="Target schema name",
                              sample_value="warehouse"),
                TemplateColumn("Target Table", "target_table", required=True,
                              description="Target table name", 
                              sample_value="dim_customer"),
                TemplateColumn("Target Columns", "target_columns",
                              description="Target column names (JSON array)",
                              sample_value='["customer_key","customer_name","email_address"]'),
                TemplateColumn("Business Key", "business_key",
                              description="Business key columns",
                              sample_value="customer_id"),
                TemplateColumn("SCD Attributes", "scd_attributes", 
                              description="Slowly changing dimension attributes",
                              sample_value='["customer_name","email"]'),
                TemplateColumn("Transformation SQL", "transformation_sql",
                              description="ETL transformation logic",
                              sample_value="SELECT customer_id, UPPER(customer_name), email FROM source"),
                TemplateColumn("Load Strategy", "load_strategy",
                              description="Load strategy (full/incremental/merge)",
                              sample_value="incremental"),
                TemplateColumn("Description", "description",
                              description="Mapping description",
                              sample_value="Loads customer dimension with SCD Type 2")
            ]
        )
    
    def _create_etl_pipeline_template(self) -> MappingTemplate:
        """Create ETL pipeline specific template."""
        return MappingTemplate(
            name="ETL Pipeline Mapping",
            type=TemplateType.ETL_PIPELINE, 
            description="Template for ETL pipeline and data integration scenarios",
            columns=[
                TemplateColumn("Pipeline Name", "name", required=True,
                              description="Name of ETL pipeline",
                              sample_value="Daily Customer Extract"),
                TemplateColumn("Step Order", "step_order", 
                              description="Step order in pipeline",
                              sample_value="1",
                              data_type="integer"),
                TemplateColumn("Source Connection", "source_connection", required=True,
                              description="Source connection name",
                              sample_value="PROD_DB"),
                TemplateColumn("Source Type", "source_type",
                              description="Source type (table/view/query/api)",
                              sample_value="table"),
                TemplateColumn("Source Schema", "source_schema",
                              description="Source schema", 
                              sample_value="public"),
                TemplateColumn("Source Object", "source_table", required=True,
                              description="Source object (table/view name)",
                              sample_value="customers"),
                TemplateColumn("Source Query", "source_query",
                              description="Custom source query (if applicable)",
                              sample_value="SELECT * FROM customers WHERE updated_date >= ?"),
                TemplateColumn("Target Connection", "target_connection", required=True,
                              description="Target connection name", 
                              sample_value="DWH_DB"),
                TemplateColumn("Target Schema", "target_schema", required=True,
                              description="Target schema",
                              sample_value="staging"),
                TemplateColumn("Target Table", "target_table", required=True,
                              description="Target table name",
                              sample_value="stg_customers"),
                TemplateColumn("Column Mappings", "column_mappings",
                              description="Column mappings (JSON format)",
                              sample_value='{"id":"customer_id","name":"customer_name"}'),
                TemplateColumn("Transformations", "transformation_sql",
                              description="Data transformations",
                              sample_value="TRIM(UPPER(customer_name)) as customer_name"),
                TemplateColumn("Data Quality Rules", "data_quality_rules",
                              description="Data quality validation rules",
                              sample_value="customer_name IS NOT NULL AND email LIKE '%@%'"),
                TemplateColumn("Schedule", "schedule",
                              description="ETL schedule (cron/frequency)",
                              sample_value="0 6 * * *"),
                TemplateColumn("Dependencies", "dependencies", 
                              description="Pipeline dependencies",
                              sample_value="extract_products,validate_references"),
                TemplateColumn("Error Handling", "error_handling",
                              description="Error handling strategy",
                              sample_value="skip_invalid_records"),
                TemplateColumn("Description", "description",
                              description="Pipeline step description", 
                              sample_value="Extracts and stages customer data from production")
            ]
        )


# Global template manager instance
template_manager = TemplateManager()