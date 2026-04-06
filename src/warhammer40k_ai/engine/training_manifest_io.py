from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_training_records_document(path: str | Path) -> Any:
    file_path = Path(path).resolve()
    return json.loads(file_path.read_text(encoding="utf-8"))


def extract_training_records(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(item or {}) for item in document]
    if isinstance(document, dict):
        if isinstance(document.get("records"), list):
            return [dict(item or {}) for item in list(document.get("records", []) or [])]
        return [dict(document)]
    raise ValueError("Input must be a decision record object, list, or object with a records list.")


def load_training_records(path: str | Path) -> list[dict[str, Any]]:
    return extract_training_records(load_training_records_document(path))


def save_training_manifest(manifest: dict[str, Any] | Any, path: str | Path) -> Path:
    file_path = Path(path).resolve()
    payload = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest or {})
    file_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    return file_path


__all__ = [
    "extract_training_records",
    "load_training_records",
    "load_training_records_document",
    "save_training_manifest",
]
