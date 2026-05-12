# DB Testing Tool – Copilot Instructions

## Project Overview
FastAPI web application (Python 3.11+) for Oracle/Redshift database testing, DRD-to-SQL mapping generation, and AI-driven training. Runs on `localhost:8550`.

## Architecture
```
app/
├── main.py              # FastAPI entry point
├── database.py          # SQLAlchemy async engine (SQLite app.db)
├── routers/
│   ├── tests.py         # Test case CRUD, control table, training pipeline
│   ├── datasources.py   # Datasource management
│   ├── ai.py            # AI provider integration (GHC, local agents)
│   ├── table_inspector.py
│   └── mappings.py      # Mapping file management
├── services/
│   ├── control_table_service.py   # DRD→INSERT SQL generation logic
│   ├── drd_import_service.py      # Excel/CSV DRD parsing
│   ├── sql_generation_service.py  # AI-based SQL generation
│   ├── schema_service.py          # PDM/schema management
│   └── ai_service.py              # AI provider abstraction
├── models/                         # SQLAlchemy ORM models
├── templates/                      # Jinja2 HTML (mappings.html, training_studio.html)
└── static/js/app.js               # Client-side API wrapper
```

## Key Conventions
- **Oracle SQL**: All generated SQL targets Oracle dialect (NVL, DECODE, CASE WHEN, MERGE)
- **Source alias**: DRD files reference staging tables by alias (e.g., `OPN_TAX_LOTS_NONBKR_TGT.COLUMN`)
- **Schemas**: `SCHEMA_OWNER.TABLE_NAME` format (e.g., `TAXLOT_OWNER.OPN_TAX_LOTS_NON_BKR_FACT`)
- **PDM files**: Saved in `data/local_kb/schema_kb_ds_{id}.json`
- **Training rules**: `ControlTableCorrectionRule` model with upsert on (target_table, target_column)
- **API pattern**: All endpoints under `/api/tests/`, `/api/datasources/`, `/api/ai/`

## Datasources
- **CDS** (id=2): Oracle `gl_odiCCALqa_main` – 7 schemas including CCAL_BAL_OWNER, CCAL_OWNER, TAXLOT_OWNER
- **LH** (id=3): Oracle `gl_cdss001qa_main` – Lighthouse
- **Redshift** (id=1): Lighthouse QA via SSO

## Common Tasks
- **Parse DRD**: Upload .xlsx → `drd_import_service.parse_drd_file()` → column mapping
- **Generate INSERT**: `control_table_service.build_control_insert_sql()` → Oracle INSERT with JOINs
- **Train**: Upload DRD + expected SQL → training pipeline iterates, saves wins to KB
- **Validate SQL**: `control_table_service.validate_insert_sql()` → check against live DB

## Testing
```bash
cd C:\GIT_Repo\db-testing-tool
python -m pytest tests/ -v
```
Start server: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8550 --reload`
