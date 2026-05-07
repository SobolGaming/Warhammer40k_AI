from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


def records_from_document(document: Any, *, source_path: Path | None = None) -> Iterator[dict[str, Any]]:
    if isinstance(document, list):
        for item in document:
            if not isinstance(item, dict):
                raise ValueError(f"Expected decision record object at {source_path or '<memory>'}.")
            yield dict(item)
        return
    if isinstance(document, dict) and isinstance(document.get("records"), list):
        for item in list(document.get("records", []) or []):
            if not isinstance(item, dict):
                raise ValueError(f"Expected decision record object at {source_path or '<memory>'}.")
            yield dict(item)
        return
    if isinstance(document, dict):
        yield dict(document)
        return
    raise ValueError(f"Expected decision records JSON at {source_path or '<memory>'}.")


def iter_records_from_json(path: str | Path, *, chunk_size: int = 1024 * 1024) -> Iterator[dict[str, Any]]:
    resolved_path = Path(path)
    decoder = json.JSONDecoder()
    with resolved_path.open("r", encoding="utf-8") as handle:
        buffer = ""
        eof = False

        def _read_more() -> None:
            nonlocal buffer, eof
            chunk = handle.read(max(1, int(chunk_size)))
            if chunk:
                buffer += chunk
            else:
                eof = True

        while not buffer.strip() and not eof:
            _read_more()
        buffer = buffer.lstrip()
        if not buffer:
            return
        opener = buffer[0]
        buffer = buffer[1:]
        if opener != "[":
            document = json.loads(opener + buffer + handle.read())
            for item in records_from_document(document, source_path=resolved_path):
                yield item
            return

        while True:
            buffer = buffer.lstrip()
            while not buffer and not eof:
                _read_more()
                buffer = buffer.lstrip()
            if not buffer:
                if eof:
                    raise ValueError(f"Unexpected end of JSON array at {resolved_path}.")
                continue
            if buffer[0] == "]":
                return
            if buffer[0] == ",":
                buffer = buffer[1:]
                continue
            while True:
                try:
                    item, consumed = decoder.raw_decode(buffer)
                    break
                except json.JSONDecodeError:
                    if eof:
                        raise
                    _read_more()
            if not isinstance(item, dict):
                raise ValueError(f"Expected decision record object in JSON array at {resolved_path}.")
            yield dict(item)
            buffer = buffer[consumed:]


__all__ = [
    "iter_records_from_json",
    "records_from_document",
]
