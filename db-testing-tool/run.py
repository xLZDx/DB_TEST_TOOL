#!/usr/bin/env python3
"""
DB Testing Tool - Local Launcher
Run this file to start the application: python run.py
"""
import uvicorn
import os
import sys

def main():
    os.environ.setdefault("DB_TESTING_TOOL_ENV", "local")

    port = int(os.environ.get("DBTOOL_PORT", 8550))
    is_portable = os.environ.get("DB_TESTING_TOOL_ENV") == "portable"

    # In portable mode, disable reload (no dev dependencies needed)
    use_reload = not is_portable

    mode_label = "Portable" if is_portable else "Development"
    print("=" * 60)
    print(f"  DB Testing Tool - {mode_label}")
    print(f"  Open http://localhost:{port} in your browser")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        reload=use_reload,
        log_level="info",
    )

if __name__ == "__main__":
    main()
