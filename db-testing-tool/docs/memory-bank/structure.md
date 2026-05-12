# Project Structure Guide

## Directory Layout
```
db-testing-tool/
├── .github/copilot-instructions.md   # Copilot agent instructions
├── app/                               # Main application
│   ├── main.py                        # FastAPI app, CORS, static files, routers
│   ├── database.py                    # SQLAlchemy async engine + get_db dependency
│   ├── routers/                       # API endpoint handlers
│   │   ├── tests.py                   # ~2000 lines: test CRUD, control table, training
│   │   ├── datasources.py            # Datasource management + schema queries
│   │   ├── ai.py                     # AI provider routing (GHC, local agents)
│   │   ├── table_inspector.py        # Table data browsing + inline edit
│   │   └── mappings.py               # Mapping file import/export
│   ├── services/                      # Business logic
│   │   ├── control_table_service.py   # DRD→INSERT generation, comparison, validation
│   │   ├── drd_import_service.py      # File parsing (Excel, CSV, JSON)
│   │   ├── sql_generation_service.py  # AI-assisted SQL generation
│   │   ├── schema_service.py          # PDM management, live DB schema
│   │   └── ai_service.py            # AI abstraction layer
│   ├── models/                        # SQLAlchemy ORM models
│   ├── templates/                     # Jinja2 HTML templates
│   └── static/                        # JS, CSS, images
├── data/local_kb/                     # Persistent knowledge base (PDM JSON files)
├── training_packs/                    # Training snapshots
├── docs/                              # Documentation (this folder)
│   ├── architecture.md                # Full API + service reference
│   ├── agents.md                      # Agent definitions
│   ├── mcp-servers.md                 # MCP server configuration
│   ├── training-instructions.md       # Training workflow guide
│   └── memory-bank/                   # Memory bank for agent context
│       ├── product.md                 # Product context
│       ├── tech.md                    # Tech stack & conventions
│       └── structure.md               # This file
├── tests/                             # Pytest test files
├── tools/                             # Utility scripts
└── scripts/                           # Deployment/setup scripts
```

## Key Entry Points
- **Start server**: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8550 --reload`
- **Run tests**: `python -m pytest tests/ -v`
- **Main pages**: `/mappings` (control table), `/training-studio`, `/table-inspector`, `/settings`

## Data Flow
```
DRD File (.xlsx) → drd_import_service.parse_drd_file()
    → control_table_service.analyze_control_table()
    → control_table_service.build_control_insert_sql()
    → validate_insert_sql() → comparison grid → training pipeline → KB rules
```
