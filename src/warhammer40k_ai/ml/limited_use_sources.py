from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..engine.limited_use_context import clean_limited_use_text, limited_use_scopes_from_text


LIMITED_USE_SOURCE_FILES = (
    "wahapedia_data/Abilities.json",
    "wahapedia_data/Datasheets_abilities.json",
    "wahapedia_data/Detachment_abilities.json",
    "wahapedia_data/Stratagems.json",
    "wahapedia_data/Enhancements.json",
)

_TEXT_FIELDS = ("name", "description", "legend", "type", "parameter")


@dataclass(frozen=True)
class LimitedUseSourceEntry:
    source_file: str
    source_kind: str
    index: int
    entry_id: str
    name: str
    faction_id: str
    detachment: str
    datasheet_id: str
    scopes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_kind": self.source_kind,
            "index": self.index,
            "entry_id": self.entry_id,
            "name": self.name,
            "faction_id": self.faction_id,
            "detachment": self.detachment,
            "datasheet_id": self.datasheet_id,
            "scopes": list(self.scopes),
        }


def _source_kind(path: str) -> str:
    stem = Path(path).stem.lower()
    if stem == "datasheets_abilities":
        return "datasheet_ability"
    return stem.removesuffix("s")


def _load_json_entries(path: Path) -> list[Mapping[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, Mapping)]
    if isinstance(data, Mapping):
        return [entry for entry in data.values() if isinstance(entry, Mapping)]
    raise ValueError(f"{path} must contain a JSON list or object.")


def _entry_text(entry: Mapping[str, Any]) -> str:
    return " ".join(clean_limited_use_text(entry.get(field)) for field in _TEXT_FIELDS)


def find_limited_use_source_entries(
    *,
    repo_root: str | Path,
    source_files: Iterable[str] = LIMITED_USE_SOURCE_FILES,
) -> tuple[list[LimitedUseSourceEntry], dict[str, int]]:
    root = Path(repo_root)
    limited_entries: list[LimitedUseSourceEntry] = []
    entry_counts: dict[str, int] = {}
    for relative in source_files:
        path = root / relative
        entries = _load_json_entries(path)
        entry_counts[relative] = len(entries)
        kind = _source_kind(relative)
        for index, entry in enumerate(entries):
            scopes = limited_use_scopes_from_text(_entry_text(entry))
            if not scopes:
                continue
            limited_entries.append(
                LimitedUseSourceEntry(
                    source_file=relative,
                    source_kind=kind,
                    index=index,
                    entry_id=clean_limited_use_text(entry.get("id") or entry.get("ability_id")),
                    name=clean_limited_use_text(entry.get("name")),
                    faction_id=clean_limited_use_text(entry.get("faction_id")),
                    detachment=clean_limited_use_text(entry.get("detachment")),
                    datasheet_id=clean_limited_use_text(entry.get("datasheet_id")),
                    scopes=scopes,
                )
            )
    limited_entries.sort(
        key=lambda entry: (
            entry.source_file,
            entry.index,
            entry.entry_id,
            entry.name,
        )
    )
    return limited_entries, entry_counts


def summarize_limited_use_source_entries(
    *,
    repo_root: str | Path,
    source_files: Iterable[str] = LIMITED_USE_SOURCE_FILES,
) -> dict[str, Any]:
    entries, entry_counts = find_limited_use_source_entries(repo_root=repo_root, source_files=source_files)
    by_file: dict[str, dict[str, Any]] = {}
    for relative in source_files:
        file_entries = [entry for entry in entries if entry.source_file == relative]
        scope_counts = Counter(scope for entry in file_entries for scope in entry.scopes)
        by_file[relative] = {
            "entry_count": int(entry_counts.get(relative, 0)),
            "limited_use_entry_count": len(file_entries),
            "scope_counts": dict(sorted(scope_counts.items())),
        }
    total_scope_counts = Counter(scope for entry in entries for scope in entry.scopes)
    return {
        "source_files": list(source_files),
        "entry_count": sum(int(count) for count in entry_counts.values()),
        "limited_use_entry_count": len(entries),
        "scope_counts": dict(sorted(total_scope_counts.items())),
        "by_file": by_file,
        "entries": [entry.to_dict() for entry in entries],
    }


__all__ = [
    "LIMITED_USE_SOURCE_FILES",
    "LimitedUseSourceEntry",
    "find_limited_use_source_entries",
    "summarize_limited_use_source_entries",
]
