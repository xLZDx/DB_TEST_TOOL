"""IntelliTest FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.config import settings
from app.database import init_db

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Static files and templates
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Import and register routers
from app.routers import chat, jira, tfs, testrail, tests, artifacts, datasources, auth

app.include_router(chat.router)
app.include_router(jira.router)
app.include_router(tfs.router)
app.include_router(testrail.router)
app.include_router(tests.router)
app.include_router(artifacts.router)
app.include_router(datasources.router)
app.include_router(auth.router)


@app.on_event("startup")
async def startup():
    """Create required data directories and initialize database on startup."""
    data_dir = settings.get_data_dir()
    for sub in ("chat_history", "chat_artifacts", "schema_kb"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    # Initialize SQLite database tables
    await init_db()


# ── Page routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "dashboard"})


@app.get("/chat", response_class=HTMLResponse)
async def page_chat(request: Request):
    return templates.TemplateResponse("chat_assistant.html", {"request": request, "page": "chat"})


@app.get("/jira", response_class=HTMLResponse)
async def page_jira(request: Request):
    return templates.TemplateResponse("jira_browser.html", {"request": request, "page": "jira"})


@app.get("/tfs-browser", response_class=HTMLResponse)
async def page_tfs(request: Request):
    return templates.TemplateResponse("tfs_browser.html", {"request": request, "page": "tfs"})


@app.get("/test-management", response_class=HTMLResponse)
async def page_tests(request: Request):
    return templates.TemplateResponse("test_management.html", {"request": request, "page": "tests"})


@app.get("/testrail-sync", response_class=HTMLResponse)
async def page_testrail(request: Request):
    return templates.TemplateResponse("testrail_sync.html", {"request": request, "page": "testrail"})


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "page": "settings"})
