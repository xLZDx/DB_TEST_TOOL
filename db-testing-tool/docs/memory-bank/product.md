# DB Testing Tool – Product Context

## Purpose
Automated Oracle/Redshift database testing tool with AI-driven DRD-to-SQL mapping generation. Designed for capital markets data quality validation.

## Target Users
- Database developers and testers working with Oracle ETL mappings
- Data engineers validating DRD (Data Requirements Document) implementations
- QA teams running regression tests against Oracle/Redshift databases

## Core Workflows
1. **DRD Import → SQL Generation**: Upload DRD Excel → parse columns → generate INSERT/MERGE SQL
2. **Comparison & Validation**: Compare generated SQL against manual/ODI reference SQL per-column
3. **Training & Learning**: Iterative AI training to improve SQL generation accuracy
4. **Test Execution**: Generate and run test suites against live databases

## Key Business Rules
- All SQL targets Oracle dialect (NVL, DECODE, CASE WHEN, MERGE statements)
- DRD files use `SCHEMA_OWNER.TABLE_NAME` convention
- Training rules persist across sessions and auto-apply on future generations
- Source tables are referenced by alias in DRD expressions (e.g., `OPN_TAX_LOTS_NONBKR_TGT.COLUMN`)
- Target tables live in fact/dimension schemas (e.g., `TAXLOT_OWNER`, `CCAL_BAL_OWNER`)
