from typing import  Callable
import inspect

def describe_callable(cb: Callable) -> str:
    try:
        file = inspect.getsourcefile(cb) or inspect.getfile(cb)
        line = inspect.getsourcelines(cb)[1]
    except (OSError, IOError):  # builtins / C-extensions
        file = inspect.getfile(cb)
        line = None

    return (
        f"callback={cb.__name__!r}, "
        f"file={file}, "
        f"line={line}"
    )

def describe_self_stack() -> str:
    return "\n".join(f"  {i}: {frame}" for i, frame in enumerate(inspect.stack()))
