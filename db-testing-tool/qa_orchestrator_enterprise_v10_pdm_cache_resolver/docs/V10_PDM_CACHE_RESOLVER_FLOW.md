# v10 PDM Cache Resolver Flow

## Objective

Generation must work even when XML is not available. XML is only a quality gate.
The source of truth for generation is:

```text
DRD + cached DB PDM metadata
```

## Assumption

The application has full DB definitions cached locally, with files like:

```text
data/local_kb/hint_index_ds_2.json
data/local_kb/hint_index_ds_3.json
data/local_kb/schema_kb_ds_2.json
data/local_kb/schema_kb_ds_3.json
data/local_kb/operation_history.jsonl
```

## Resolver decision model

```text
1. Validate exact DRD source_schema.source_table.source_attribute against PDM.
2. If exact object exists, status = VALIDATED_EXACT.
3. If missing, score candidates from PDM using:
   - schema similarity
   - table similarity
   - attribute similarity
   - target column similarity
   - logical name similarity
   - transformation text hints
   - common DRD abbreviations
4. If confidence >= auto_accept_threshold, status = PREDICTED_AUTO_ACCEPT.
5. If confidence >= review_threshold, status = PREDICTED_REVIEW_REQUIRED.
6. If confidence is too low or object missing, trigger backfill request.
```

## Why this matters

A DRD may say:

```text
source table: TXN
source attribute: SRC_ACTN_CODE
```

But the PDM cache may contain a more precise physical object, datatype, nullable flag, or alternate attribute name. The resolver enriches the DRD row before SQL generation.

## Outputs

The enriched generator emits:

```text
source_select.sql
insert_select.sql     recommended for DRD generator
cte.sql               recommended for control table
merge.sql
pdm_resolution_report.csv
pdm_cache_summary.json
backfill requests in operation_history.jsonl
```
