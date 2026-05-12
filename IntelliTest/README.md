# IntelliTest — Intelligent Test Generation Platform

> **Combined AIRA + DB Testing Tool** — a unified, AI-powered test generation platform
> that supports both Jira and TFS work item systems, generates SQL validation tests from DRD/mapping
> documents, executes tests against live databases, and exports results to TestRail.

---

## What IntelliTest is

IntelliTest merges the best capabilities from two tools:

| Feature | From | Enhanced |
|---------|------|---------|
| Jira integration (browse, read PBIs, download attachments) | AIRA | ✅ Python port, full REST API |
| TestRail test export | AIRA | ✅ Python port with bulk import |
| TFS/Azure DevOps integration | DB Testing Tool | ✅ Work item context + attachments |
| SQL test generation from DRD/mapping docs | DB Testing Tool | ✅ Multi-layer + aggregation flows |
| Database test execution | DB Testing Tool | ✅ Oracle, Redshift, SQL Server |
| AI Chat Assistant | DB Testing Tool | ✅ Multi-artifact, history |
| Schema KB (table/column knowledge base) | DB Testing Tool | ✅ Auto-indexed |
| Control Table testing | DB Testing Tool | ✅ DDL + INSERT + validation |

---

## Key capabilities

### 1. Dual Work Item Support (Jira + TFS)
- Browse Jira projects, epics, stories, bugs
- Browse TFS/Azure DevOps PBIs and bugs
- Download and analyze attachments from both systems
- Use work item context (title, description, acceptance criteria, attachments) to guide AI test generation

### 2. AI-Powered Test Generation
- Upload DRD/mapping documents (CSV, Excel)
- Attach multiple context files: mapping docs, SQL, architecture notes, wiki exports
- Describe in **plain language** what tests you need
- AI generates complete, executable SQL validation tests
- Multi-layer validation: staging → intermediate aggregation → final target

### 3. Test Management & Execution
- Create test suites from generated tests
- Execute tests against Oracle, Redshift, or SQL Server
- Track pass/fail results with mismatch details
- Export results to TFS bugs or TestRail test cases

### 4. TestRail Integration
- Export generated test cases to TestRail
- Sync test results back from execution
- Maintain coverage mapping: Jira story ↔ TestRail test case

### 5. Schema Knowledge Base
- Introspect connected databases
- Build a local KB of tables, columns, PKs, FKs
- AI uses KB to build accurate JOIN predicates and NULL-safe comparisons

---

## Architecture

```
IntelliTest/
├── app/
│   ├── main.py                  FastAPI application entry
│   ├── config.py                Settings (Jira, TFS, TestRail, DB, AI)
│   ├── routers/
│   │   ├── jira.py             Jira REST API endpoints
│   │   ├── testrail.py         TestRail API endpoints
│   │   ├── tfs.py              TFS/Azure DevOps endpoints
│   │   ├── chat.py             AI Chat Assistant endpoints
│   │   ├── tests.py            Test management and execution
│   │   ├── datasources.py      DB connection management
│   │   └── artifacts.py        File upload and artifact store
│   ├── services/
│   │   ├── jira_service.py     Jira REST client
│   │   ├── testrail_service.py TestRail client  
│   │   ├── tfs_service.py      TFS REST client
│   │   ├── ai_service.py       GHC/OpenAI integration
│   │   ├── test_generator.py   SQL test generation from DRD + AI
│   │   ├── artifact_memory.py  Conversation + artifact history
│   │   └── schema_service.py   DB introspection
│   ├── models/
│   │   ├── conversation.py     Conversation + message models
│   │   ├── test_case.py        Test case + run models
│   │   └── artifact.py         Uploaded artifact models
│   └── templates/
│       ├── base.html           Shared layout
│       ├── dashboard.html      Overview page
│       ├── chat_assistant.html AI chatbot interface
│       ├── jira_browser.html   Jira item browser
│       ├── tfs_browser.html    TFS item browser
│       ├── test_management.html Test suite management
│       └── testrail_sync.html  TestRail export/sync
└── docs/
    ├── ARCHITECTURE.md
    └── INTEGRATION_GUIDE.md
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- GitHub Copilot access (for AI test generation)
- Optional: Jira API token, TestRail credentials, TFS PAT, database JDBC/ODBC drivers

### Setup

```bash
# 1. Clone and navigate
cd c:\GIT_Repo\IntelliTest

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env with your credentials

# 4. Start the server
python run.py
# App available at http://127.0.0.1:8560
```

### Environment variables

```env
# AI Provider
AI_PROVIDER=githubcopilot
GITHUBCOPILOT_TOKEN=<your-token>

# Jira
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your@email.com
JIRA_API_TOKEN=your-jira-token

# TFS / Azure DevOps
TFS_BASE_URL=https://dev.azure.com
TFS_PAT=your-tfs-pat
TFS_PROJECT=YourProject
TFS_COLLECTION=YourOrg

# TestRail
TESTRAIL_URL=https://yourcompany.testrail.io
TESTRAIL_EMAIL=your@email.com
TESTRAIL_API_KEY=your-testrail-key

# Databases (comma-separated JSON array)
DATASOURCES_JSON=[{"name":"DEV","type":"oracle","host":"dev-db","port":1521,"service":"CDSDEV","username":"user","password":"pass"}]
```

---

## Key Differences from Individual Tools

### vs. AIRA (PowerShell/VS Code extension)
- **IntelliTest is a standalone web application** — no VS Code required
- TFS/Azure DevOps support added (AIRA only supports Jira)
- SQL test generation and database execution (AIRA only generates TestRail cases)
- Runs against live databases to validate data quality

### vs. DB Testing Tool
- **Jira integration added** (DB Testing Tool only supports TFS)
- TestRail export (DB Testing Tool exports to TFS only)
- Richer AI chat with cross-system context (Jira + TFS + DRD all at once)
- Multi-layer test generation: covers ETL pipeline stages, not just final target

---

## Status: Active Development Prototype

This is a functional prototype. Core modules implemented:
- ✅ Jira service (read work items + attachments + linked issues)
- ✅ TFS service (read work items + attachments + hyperlinks)
- ✅ AI chat assistant (multi-artifact, GHC backend, persistent history)
- ✅ Artifact memory service (upload DRD/SQL/docs, store for AI context)
- ✅ Test generator (DRD → SQL tests with AI enrichment)
- ✅ FastAPI endpoints for all above
- 🔄 TestRail integration (in progress)
- 🔄 Database connection management (in progress)
- 🔄 Test execution engine (in progress)
- 🔄 Full UI (templates in progress)
