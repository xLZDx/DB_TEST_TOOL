# DB Testing Tool

A local web application for automated database testing with AI assistance, supporting **Oracle**, **Redshift**, and optional **SQL Server** connections.

## Features

| Module | Description |
|---|---|
| **Data Sources** | Connect to Oracle, Redshift, SQL Server. Test connections live. |
| **Schema Browser** | Introspect tables, views, columns, PKs. Compare schemas across DBs. |
| **Mapping Rules** | Define source→target mapping rules with transformations, joins, filters. |
| **Test Generation** | Auto-generate row count, null check, uniqueness, value match, freshness tests. |
| **Test Execution** | Run individual or batch tests. Track pass/fail with evidence. |
| **AI Assistant** | Analyze SQL, extract mapping rules, suggest tests, triage failures. |
| **TFS Integration** | Create/sync TFS bugs from failures. Auto-bug creation per batch. |
| **Dashboard** | Stats, pass rate, recent runs, quick actions. |

## Quick Start

### 1. Install Python 3.10+

Ensure Python 3.10 or later is installed and available on your PATH.

### 2. Clone & Install Dependencies

```bash
cd db-testing-tool
pip install -r requirements.txt
```

> **Note:** Oracle connector (`oracledb`) works in thin mode by default — no Oracle client needed.  
> For Redshift, `psycopg2-binary` is included.  
> SQL Server requires ODBC Driver 17+ to be installed separately if you use it.

### 3. Configure (Optional)

Copy the env template and fill in your values:

```bash
copy .env.example .env
```

Edit `.env`:
- **AI_PROVIDER** – `openai` (default), `azure`, `compatible`, or `githubcopilot`
- **OPENAI_API_KEY** – for OpenAI provider (optional, app works without AI)
- **TFS_BASE_URL**, **TFS_PAT**, **TFS_PROJECT** – for TFS/Azure DevOps integration (optional)

### AI Provider Examples

**OpenAI (default)**

```dotenv
AI_PROVIDER=openai
AI_MODEL=gpt-4o
OPENAI_API_KEY=...
```

**Azure OpenAI**

```dotenv
AI_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
```

**Internal OpenAI-compatible endpoint**

```dotenv
AI_PROVIDER=compatible
AI_BASE_URL=https://<internal-endpoint>/v1
AI_API_KEY=...
AI_MODEL=<model-or-deployment-name>
```

**GitHub Copilot-compatible endpoint (enterprise/internal gateway)**

```dotenv
AI_PROVIDER=githubcopilot
GITHUBCOPILOT_BASE_URL=https://<your-copilot-gateway>/v1
GITHUBCOPILOT_API_KEY=...
GITHUBCOPILOT_MODEL=<model-name>
```

Note: this app expects an OpenAI-compatible chat completions endpoint. If your Copilot setup uses a different API shape, place a compatible gateway in front of it.

If your corporate TLS uses custom CAs:

```dotenv
OPENAI_VERIFY_SSL=true
OPENAI_CA_BUNDLE=C:/path/to/corporate-root-ca.pem
```

### 4. Run

```bash
python run.py
```

Open **http://localhost:8550** in your browser.

## Workflow

1. **Add Data Sources** – Oracle and/or Redshift connection details
2. **Test Connections** – Verify connectivity
3. **Analyze Schemas** – Introspect tables/columns from remote databases
4. **Define Mapping Rules** – Source→target table relationships and transformations
5. **Generate Tests** – Auto-create test cases from mapping rules
6. **Run Tests** – Execute against live databases, review results
7. **AI Assist** – Paste SQL to extract rules, get test suggestions, triage failures
8. **TFS Tracking** – Push failures as bugs to TFS/Azure DevOps

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/datasources` | GET/POST | List/create data sources |
| `/api/datasources/{id}/test` | POST | Test connection |
| `/api/schemas/analyze` | POST | Introspect remote database |
| `/api/schemas/tree/{id}` | GET | Get schema tree |
| `/api/schemas/compare` | POST | Compare two tables' schemas |
| `/api/mappings` | GET/POST | List/create mapping rules |
| `/api/tests` | GET/POST | List/create test cases |
| `/api/tests/generate/{rule_id}` | POST | Generate tests for rule |
| `/api/tests/run/{id}` | POST | Run single test |
| `/api/tests/run-batch` | POST | Run batch of tests |
| `/api/tests/runs` | GET | List test run results |
| `/api/tests/dashboard-stats` | GET | Dashboard statistics |
| `/api/ai/analyze-sql` | POST | AI SQL analysis |
| `/api/ai/extract-rules` | POST | AI rule extraction |
| `/api/ai/suggest-tests` | POST | AI test suggestions |
| `/api/ai/triage` | POST | AI failure triage |
| `/api/tfs/workitems` | GET/POST | List/create TFS work items |
| `/api/tfs/auto-bugs` | POST | Auto-create bugs from batch |

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy (async), SQLite
- **Frontend:** Jinja2 templates, vanilla JS, custom CSS
- **Connectors:** oracledb (Oracle), psycopg2 (Redshift), pyodbc (SQL Server)
- **AI:** OpenAI GPT-4o via API
- **Tracking:** TFS / Azure DevOps REST API

## Project Structure

```
db-testing-tool/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py             # Settings & env loading
│   ├── database.py           # SQLAlchemy engine/session
│   ├── connectors/           # Oracle, Redshift, SQL Server connectors
│   ├── models/               # SQLAlchemy models
│   ├── routers/              # API endpoints
│   ├── services/             # Business logic (schema, tests, AI, TFS)
│   ├── templates/            # HTML pages
│   └── static/               # CSS & JS
├── data/                     # SQLite database (auto-created)
├── .env                      # Configuration (create from .env.example)
├── requirements.txt
├── run.py                    # Entry point
└── README.md
```
