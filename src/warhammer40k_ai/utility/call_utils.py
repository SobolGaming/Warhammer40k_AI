from __future__ import annotations

import inspect
from typing import Any


def call_with_supported_kwargs(func: object, /, *args: Any, **kwargs: Any) -> Any:
    if not callable(func):
        raise TypeError(f"{func!r} is not callable")
    if not kwargs:
        return func(*args)
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return func(*args, **kwargs)
    parameters = signature.parameters
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return func(*args, **kwargs)
    filtered = {
        str(key): value
        for key, value in dict(kwargs or {}).items()
        if str(key) in parameters
    }
    return func(*args, **filtered)
