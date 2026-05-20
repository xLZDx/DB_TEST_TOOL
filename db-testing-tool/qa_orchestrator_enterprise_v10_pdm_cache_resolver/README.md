# v10 — PDM Cache Resolver + DRD-Only Generation + Optional XML Quality Gate

This package updates the v9 semantic-alias gate with a PDM-aware resolver.

## Main idea

XML is **only a quality gate** when available. The generator must work from DRD + cached PDM metadata even when XML is missing.

The new flow is:

```text
DRD row
  ↓
Validate source schema/table/attribute against local PDM cache
  ↓
If exact match exists → keep DRD mapping
  ↓
If schema/table/attribute is missing or suspicious → predict best PDM table/attribute
  ↓
If confidence is high → enrich DRD mapping and generate SQL
  ↓
If confidence is low or object is absent → trigger automatic backfill request
  ↓
Generate statement modes:
  - source_select
  - insert_select   recommended for DRD generator
  - cte             recommended for control table
  - merge
  ↓
If XML exists → run XML quality gate
If XML is missing → return DRD_ONLY_GENERATED
```

## New services

```text
app/services/pdm_cache_resolver_service.py
app/services/pdm_backfill_service.py
app/services/drd_pdm_enrichment_service.py
app/services/statement_mode_generation_service.py
app/services/semantic_alias_quality_gate_service.py
app/routers/orchestrator.py
```

## Assumed local cache path

Default:

```text
data/local_kb
```

Typical files, based on your screenshot:

```text
hint_index_ds_2.json
hint_index_ds_3.json
schema_kb_ds_2.json
schema_kb_ds_3.json
operation_history.jsonl
```

The resolver loads all matching `schema_kb_*.json` and `hint_index_*.json` files.

## Output modes

```json
{
  "sql_generation": {
    "statement_modes": ["source_select", "insert_select", "cte", "merge"],
    "preferred_for_drd_generator": "insert_select",
    "preferred_for_control_table": "cte"
  }
}
```
