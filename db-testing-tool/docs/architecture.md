# DB Testing Tool – Architecture & API Reference

## Table of Contents
1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [API Endpoints](#api-endpoints)
4. [Services](#services)
5. [Models](#models)
6. [Templates & Frontend](#templates--frontend)
7. [Training System](#training-system)
8. [Configuration](#configuration)

---

## Overview
A FastAPI web application for automated Oracle/Redshift database testing, DRD (Data Requirements Document) parsing, SQL generation, and AI-driven training. The tool generates INSERT/MERGE SQL from DRD mappings and iteratively improves output quality through a training pipeline.

**Stack**: Python 3.11+, FastAPI, SQLAlchemy (async), SQLite, Jinja2, cx_Oracle, JavaScript (vanilla)

**Port**: 8550 (default)

---

## Project Structure
```
db-testing-tool/
├── app/
│   ├── main.py                    # FastAPI app factory, middleware, startup
│   ├── database.py                # Async SQLAlchemy engine, session factory
│   ├── routers/
│   │   ├── tests.py               # Test CRUD, control table, training pipeline (largest router)
│   │   ├── datasources.py         # Datasource CRUD, schema/table/PDM endpoints
│   │   ├── ai.py                  # AI chat, training reproduction, agent management
│   │   ├── table_inspector.py     # Table data inspection, inline editing
│   │   └── mappings.py            # Mapping file import/export
│   ├── services/
│   │   ├── control_table_service.py  # Core: DRD→SQL, comparison, alias handling
│   │   ├── drd_import_service.py     # Excel/CSV/JSON parsing, sheet detection
│   │   ├── sql_generation_service.py # AI-assisted SQL generation
│   │   ├── schema_service.py         # PDM management, live DB schema queries
│   │   └── ai_service.py            # AI provider abstraction (GHC, local)
│   ├── models/
│   │   ├── test_case.py              # TestCase, TestSuite, TestRun
│   │   ├── datasource.py            # Datasource configuration
│   │   ├── control_table_training.py # ControlTableCorrectionRule, ControlTableFileState
│   │   └── ...
│   ├── templates/
│   │   ├── base.html                 # Base template (nav, rule editor modal, toast)
│   │   ├── mappings.html             # Control table modal (6000+ lines)
│   │   ├── training_studio.html      # Training page with comparison grid, coaching
│   │   ├── dashboard.html            # Dashboard
│   │   └── settings.html             # Settings page
│   └── static/
│       ├── js/app.js                 # API wrapper, utility functions
│       └── css/styles.css            # Application styles
├── data/
│   └── local_kb/                     # Saved PDM files (schema_kb_ds_{id}.json)
├── training_packs/                   # Saved training packs (DRD + SQL snapshots)
├── docs/                             # Documentation
├── tests/                            # Pytest test suite
├── tools/                            # Utility scripts
└── requirements.txt
```

---

## API Endpoints

### Test Cases (`/api/tests/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tests/suites` | List all test suites |
| POST | `/api/tests/suites` | Create test suite |
| GET | `/api/tests/suites/{id}` | Get suite details |
| DELETE | `/api/tests/suites/{id}` | Delete suite |
| POST | `/api/tests/suites/{id}/run` | Execute test suite |

### Control Table (`/api/tests/control-table/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze-from-drd` | Parse DRD + generate INSERT SQL |
| POST | `/preview-drd` | Preview DRD file (sheets, metadata, headers) |
| POST | `/compare` | Compare generated vs manual SQL per-column |
| POST | `/check-sql` | Validate SQL against live DB |
| POST | `/generate-suite` | Generate test suite from comparison results |

### Training Rules (`/api/tests/control-table/training/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/rules?target_table=X` | List rules for table |
| POST | `/rules` | Create/upsert rule (deduplicates on table+column) |
| PUT | `/rules/{id}` | Update rule |
| DELETE | `/rules/{id}` | Delete single rule |
| DELETE | `/rules?target_table=X` | Clear all rules for table |
| POST | `/feedback` | Save training feedback (legacy) |

### Training Pipeline (`/api/tests/training-pipeline/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/run` | Run iterative training pipeline |
| GET | `/rules?target_table=X` | List all training rules |

### Training Automation (`/api/tests/training-automation/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Get automation loop status |
| POST | `/start` | Start background training loop |
| POST | `/stop` | Stop automation |
| POST | `/run-once` | Execute single automation cycle |

### Datasources (`/api/datasources/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all datasources |
| POST | `/` | Create datasource |
| GET | `/{id}/schemas` | List schemas |
| GET | `/{id}/tables` | List tables in schema |
| GET | `/{id}/columns` | Get column metadata |
| POST | `/{id}/execute` | Execute SQL query |
| POST | `/{id}/pdm/refresh` | Refresh PDM cache |

### AI (`/api/ai/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send chat message to AI provider |
| POST | `/training-reproduce-async` | Start async AI job |
| GET | `/training-reproduce-async/{job_id}` | Poll job status |
| GET | `/agents` | List AI agents |

---

## Services

### `control_table_service.py`
**Core service for DRD→SQL generation.**

Key functions:
- `analyze_control_table(file_bytes, filename, ...)` → Parse DRD, lookup target table, generate INSERT
- `build_control_insert_sql(analysis, target_def, ...)` → Build Oracle INSERT with proper aliases & JOINs
- `load_target_table_definition(schema, table, ds_id)` → Search ALL saved PDMs, then try live DB
- `compare_insert_sql(analysis_rows, gen_sql, manual_sql, ...)` → Column-by-column comparison
- `validate_insert_sql(ds_id, sql, execute)` → Validate against live Oracle

### `drd_import_service.py`
**DRD file parsing with multi-format support.**

Key functions:
- `parse_drd_file(file_bytes, filename, sheet_name)` → Full parse with metadata
- `preview_file(file_bytes, filename, sheet_name)` → Quick preview with sheet list
- `extract_drd_metadata(file_bytes, filename, sheet_name)` → Parse metadata preamble
- `_pick_best_drd_sheet(wb)` → Auto-detect best DRD sheet in multi-tab Excel
- `read_excel_all_sheets(file_bytes)` → Read all sheets from Excel

---

## Models

### `ControlTableCorrectionRule`
```python
id: int (PK)
target_table: str        # e.g. "TAXLOT_OWNER.OPN_TAX_LOTS_NON_BKR_FACT"
target_column: str       # e.g. "ADJ_COST"
issue_type: str          # expression_mismatch, training_win, manual_edit, etc.
source_attribute: str    # Original DRD attribute name
recommended_source: str  # rule, manual, drd, generated
replacement_expression: str  # The correct SQL expression
notes: str
created_at, updated_at: datetime
```
**Deduplication**: POST `/rules` upserts on (target_table, target_column) – keeps latest only.

### `ControlTableFileState`
Persists generated INSERT SQL per file fingerprint for state recovery.

---

## Templates & Frontend

### `mappings.html` (Control Table Modal)
- **Step 1**: DRD file upload with sheet selector
- **Step 2**: Column mapping review, metadata display
- **Step 3**: Comparison grid (generated vs manual), Insert SQL editor with line numbers
- **Step 4**: Training rules (editable table), in-tool coaching, replay

### `training_studio.html`
- **Training Input**: Target/source tables, DRD upload, ODI/Expected SQL
- **Rules Table**: Editable KB rules with styled modal editor
- **Comparison Grid**: Full controls (filter, select all, apply fixes, win/lose, retrain)
- **In-Tool Coaching**: Chat with AI agent, conversation history, apply suggestions
- **Automation Loop**: Background training with interval control
- **Output & Log**: Generated SQL, activity timeline

### `base.html`
- Universal rule editor modal (shared by all pages)
- Toast notifications, sidebar navigation

---

## Training System

### Training Pipeline Flow
1. User uploads DRD + provides expected SQL
2. Pipeline parses expected SQL into column→expression map
3. Generates INSERT SQL from DRD
4. Compares column-by-column (normalized)
5. Feeds mismatches back to AI for refinement
6. Repeats up to N iterations
7. Saves winning expressions as rules in KB

### Rule Application
Rules are auto-applied during `build_control_insert_sql()`:
- For each column, check if a `ControlTableCorrectionRule` exists
- If mode is "aggressive", apply rule expression directly
- If mode is "conservative", show rule as suggestion in comparison grid

### In-Tool Coaching
- Chat interface with conversation history
- Context includes: target table, current mismatches, saved rules
- Agent responds with explanations and SQL suggestions
- "Apply Suggested Logic" extracts SQL blocks from response

---

## Configuration

### Environment Variables (`.env`)
```
DB_PATH=<path-to-sqlite-app.db>
COPILOT_AUTH_MODE=automatic
STATIC_VERSION=<cache-bust-version>
```

### Datasource Connection
Oracle: `oracle+cx_oracle://user:pass@host:port/service_name`
Redshift: `redshift+redshift_connector://user@host:port/db` (SSO)

### Saved PDMs
Location: `data/local_kb/schema_kb_ds_{datasource_id}.json`
Format: `{ "schemas": { "SCHEMA": { "tables": { "TABLE": { "columns": [...] } } } } }`
