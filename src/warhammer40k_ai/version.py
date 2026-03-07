from __future__ import annotations

APP_VERSION = "0.1.866"
__version__ = APP_VERSION


def get_app_version() -> str:
    return APP_VERSION


def get_version_payload() -> dict:
    return {"app_version": APP_VERSION}
