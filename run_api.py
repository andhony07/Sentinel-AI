#!/usr/bin/env python3
"""Dedicated launcher script for the FastAPI REST Backend."""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is available on sys.path regardless of execution directory
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from app.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"Starting FastAPI server on http://{settings.api_host}:{settings.api_port}")
    print(f"Interactive Swagger Documentation: http://localhost:{settings.api_port}/docs")
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
