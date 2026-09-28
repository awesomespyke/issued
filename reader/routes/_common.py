"""Shared templates instance and helper functions for all reader routes."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from server.config import get_config
from ..repo.folders import get_folder


# Support PyInstaller bundle (sys._MEIPASS) and normal execution
if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS) / "reader"
else:
    _base = Path(__file__).resolve().parent.parent  # reader/routes/ â†’ reader/

TEMPLATES_DIR = _base / "templates"
STATIC_DIR = _base / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def url_path(request: Request, route_name: str, **path_params) -> str:
    """Build an application route without coupling it to the request host."""
    return request.url_for(route_name, **path_params).path


templates.env.globals["url_path"] = url_path


def _library_title() -> str:
    try:
        return get_config().library.name
    except FileNotFoundError:
        return "Comic Library"


def _reader_auth_enabled() -> bool:
    try:
        return get_config().reader_auth.enabled
    except FileNotFoundError:
        return False
