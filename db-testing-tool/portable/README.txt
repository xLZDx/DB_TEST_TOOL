══════════════════════════════════════════════════════════════
  DB Testing Tool - Portable Edition
══════════════════════════════════════════════════════════════

QUICK START
───────────
  1. Double-click  Start.bat
  2. Wait for the browser to open (about 10-15 seconds)
  3. That's it — no installation, no admin rights, no Python needed.


STOPPING THE SERVER
───────────────────
  Double-click  Stop.bat
    or
  Close the minimised "DB Testing Tool" command window.


CONFIGURATION (.env)
────────────────────
  Edit the .env file in this folder to configure:

  • AI Provider (GitHub Copilot, OpenAI, Azure OpenAI)
  • Database connections (via DATASOURCES_JSON or through the UI)
  • TFS / Azure DevOps integration
  • Redshift session timeout

  See .env for all available settings with comments.


DATA & PORTABILITY
──────────────────
  All data is stored inside this folder:

    data/           SQLite database, templates, knowledge base
    logs/           Server logs (stdout + stderr)
    reports/        Generated test reports

  You can:
  • Copy this entire folder to a USB drive or network share
  • Zip it and share with colleagues
  • Move it to another machine — everything is self-contained
  • Keep multiple copies with different configurations


FILE STRUCTURE
──────────────
  DB-Testing-Tool-Portable/
  ├── python/          Embedded Python runtime (~120 MB)
  ├── app/             Application code
  ├── data/            Your data (SQLite DB, templates)
  ├── logs/            Runtime logs
  ├── reports/         Test report output
  ├── .env             Configuration (edit this)
  ├── run.py           Python entry point
  ├── Start.bat        ← Launch the application
  ├── Start.ps1        PowerShell launcher (advanced)
  ├── Stop.bat         ← Stop the server
  ├── Stop.ps1         PowerShell stop script
  ├── BUILD_INFO.txt   Build metadata
  └── README.txt       This file


REQUIREMENTS
────────────
  • Windows 10 or later (64-bit)
  • No admin rights needed
  • No Python installation needed
  • Port 8550 must be available (firewall may prompt on first run)


ADVANCED USAGE
──────────────
  PowerShell launcher with custom port:
    .\Start.ps1 -Port 9000 -NoBrowser

  Environment variables:
    DBTOOL_PORT=9000           Override the default port
    DB_TESTING_TOOL_DATA_DIR   Override data directory path


TROUBLESHOOTING
───────────────
  Server won't start:
    • Check logs\db-testing-tool.err.log for error details
    • Make sure port 8550 is not used by another application
    • Try running:  python\python.exe run.py   in a terminal

  Antivirus warning:
    • Some antivirus software may flag the embedded Python.
      This is a false positive. The Python binary is the official
      embeddable package from python.org.
    • Add this folder to your antivirus exclusions if needed.

  "Access denied" errors:
    • Make sure the folder is not on a read-only drive
    • Move it to a local folder (e.g., C:\Tools\)

══════════════════════════════════════════════════════════════
