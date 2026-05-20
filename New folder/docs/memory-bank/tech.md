# Tech Stack & Conventions

## Stack
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (async), uvicorn
- **Database**: SQLite (app.db for local state), Oracle (cx_Oracle), Redshift (redshift_connector)
- **Frontend**: Vanilla JavaScript, Jinja2 templates, CSS custom properties (dark theme)
- **AI**: GitHub Copilot (GHC) as primary provider, local agent support
- **Parsing**: openpyxl (Excel), csv module, json module

## Coding Conventions
- **Python**: PEP 8, async/await for all DB operations, type hints on public functions
- **SQL**: Oracle SQL dialect, uppercase keywords, table aliases in FROM/JOIN
- **JavaScript**: ES6+, `async/await`, `escapeHtml()` for all user data in HTML
- **HTML**: Inline styles (no separate component CSS), `data-*` attributes for state
- **API**: RESTful, JSON responses, FastAPI Form/File for multipart uploads
- **Error handling**: HTTPException with detail strings, frontend toast notifications

## File Naming
- Routers: `app/routers/{domain}.py`
- Services: `app/services/{domain}_service.py`
- Models: `app/models/{domain}.py`
- Templates: `app/templates/{page}.html`
- PDMs: `data/local_kb/schema_kb_ds_{id}.json`
- Training packs: `training_packs/{pack_id}/`

## Key Patterns
- **Upsert rules**: POST to `/rules` auto-deduplicates on (target_table, target_column)
- **Sheet detection**: `_pick_best_drd_sheet()` scores sheets by DRD header indicators
- **Alias detection**: Frequency analysis of `ALIAS.COLUMN` patterns in DRD expressions
- **Cross-DS PDM lookup**: Search ALL saved PDMs, not just the requested datasource
- **State persistence**: localStorage for Training Studio, SQLite for rules/test cases
