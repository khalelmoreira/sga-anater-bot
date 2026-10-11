"""
Where the app keeps its files.

From source (dev) everything stays relative to the working directory, as it
always was (`logs/`, `data/acoes_potenciais/`). In the packaged Windows app
the install folder may be read-only, so files go under
`%APPDATA%\\SGA-ANATER-Bot`. `SGA_BOT_HOME` overrides both.
"""

import os
import sys
from pathlib import Path

APP_NAME = "SGA-ANATER-Bot"


def frozen():
    return bool(getattr(sys, "frozen", False))


def app_home():
    override = os.environ.get("SGA_BOT_HOME")
    if override:
        return Path(override)
    if frozen():
        base = os.environ.get("APPDATA") or str(Path.home() / ".local" / "share")
        return Path(base) / APP_NAME
    return Path(".")


def logs_dir():
    """Action logs + screenshots (real data in the screenshots: never sanitized)."""
    return app_home() / "logs"


def templates_dir():
    """WhatsApp 'Ações Potenciais' templates, one .txt per PA + município."""
    return app_home() / "data" / "acoes_potenciais"
