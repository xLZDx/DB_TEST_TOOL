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
    print("=" * 60)
    print("  DB Testing Tool - Starting...")
    print("  Open http://localhost:8550 in your browser")
    print("=" * 60)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8550,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()
