"""UI package entry points.

Avoid importing GUI backends at module import time. Use lazy imports so
headless tooling and tests can import UI submodules without crashing.
"""

__all__ = ["WahapediaUI"]


def __getattr__(name: str):
    if name == "WahapediaUI":
        from .wahapedia_ui import WahapediaUI

        return WahapediaUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
