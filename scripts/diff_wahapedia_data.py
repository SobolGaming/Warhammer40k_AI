"""
Diff Wahapedia JSON dumps between two folders.

Usage:
  python scripts/diff_wahapedia_data.py --old path/to/old --new path/to/new --out diff.txt
"""

from __future__ import annotations

import argparse
import fnmatch
import html
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import logging
logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[1]

KEY_FIELDS: Dict[str, Tuple[str, ...]] = {
    "Abilities.json": ("id", "faction_id"),
    "Datasheets.json": ("id",),
    "Datasheets_abilities.json": ("datasheet_id", "line"),
    "Datasheets_detachment_abilities.json": ("datasheet_id", "detachment_ability_id"),
    "Datasheets_enhancements.json": ("datasheet_id", "enhancement_id"),
    "Datasheets_keywords.json": ("datasheet_id", "keyword", "model", "is_faction_keyword"),
    "Datasheets_leader.json": ("leader_id", "attached_id"),
    "Datasheets_models.json": ("datasheet_id", "line"),
    "Datasheets_models_cost.json": ("datasheet_id", "line"),
    "Datasheets_options.json": ("datasheet_id", "line"),
    "Datasheets_stratagems.json": ("datasheet_id", "stratagem_id"),
    "Datasheets_unit_composition.json": ("datasheet_id", "line"),
    "Datasheets_wargear.json": ("datasheet_id", "line", "line_in_wargear"),
    "Detachments.json": ("id",),
    "Detachment_abilities.json": ("id",),
    "Enhancements.json": ("id",),
    "Factions.json": ("id",),
    "Last_update.json": ("last_update",),
    "Source.json": ("id",),
    "Stratagems.json": ("id",),
}

PUNCT_TRANSLATION = {
    0x00A0: " ",
    0x2010: "-",
    0x2011: "-",
    0x2013: "-",
    0x2014: "-",
    0x2018: "'",
    0x2019: "'",
    0x201C: '"',
    0x201D: '"',
    0x2026: "...",
    0x2212: "-",
}


@dataclass(frozen=True)
class RowKey:
    base: Tuple[Any, ...]
    sig: Optional[str] = None
    sig_index: Optional[int] = None


@dataclass(frozen=True)
class DiffOptions:
    strip_html: bool
    normalize_punct: bool
    normalize_ws: bool
    max_text: int
    ignore_fields: Tuple[str, ...]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _strip_tags(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text)


def _normalize_text(text: str, opts: DiffOptions) -> str:
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    if opts.strip_html:
        text = _strip_tags(text)
    text = html.unescape(text)
    if opts.normalize_punct:
        text = text.translate(PUNCT_TRANSLATION)
    if opts.normalize_ws:
        text = re.sub(r"\s+", " ", text).strip()
    return text


def _values_equal(old: Any, new: Any, opts: DiffOptions) -> bool:
    if isinstance(old, str) or isinstance(new, str):
        return _normalize_text("" if old is None else old, opts) == _normalize_text("" if new is None else new, opts)
    return old == new


def _canonical_row_signature(row: Any, opts: DiffOptions) -> str:
    if isinstance(row, dict):
        filtered = {}
        for k in sorted(row.keys()):
            if k in opts.ignore_fields:
                continue
            v = row.get(k)
            if isinstance(v, str) or v is None:
                filtered[k] = _normalize_text("" if v is None else v, opts)
            else:
                filtered[k] = v
        return json.dumps(filtered, sort_keys=True, ensure_ascii=True)
    if isinstance(row, str) or row is None:
        return json.dumps(_normalize_text("" if row is None else row, opts), sort_keys=True, ensure_ascii=True)
    return json.dumps(row, sort_keys=True, ensure_ascii=True)


def _infer_key_fields(rows: Sequence[dict]) -> Optional[Tuple[str, ...]]:
    if not rows:
        return None
    sample = rows[0]
    if not isinstance(sample, dict):
        return None
    if "id" in sample:
        return ("id",)
    if "datasheet_id" in sample and "line" in sample:
        return ("datasheet_id", "line")
    if "datasheet_id" in sample and "ability_id" in sample:
        return ("datasheet_id", "ability_id")
    if "datasheet_id" in sample and "stratagem_id" in sample:
        return ("datasheet_id", "stratagem_id")
    if "datasheet_id" in sample and "enhancement_id" in sample:
        return ("datasheet_id", "enhancement_id")
    if "datasheet_id" in sample and "name" in sample:
        return ("datasheet_id", "name")
    if "faction_id" in sample and "name" in sample:
        return ("faction_id", "name")
    if "name" in sample:
        return ("name",)
    return None


def _list_json_files(folder: Path) -> List[str]:
    return sorted([p.name for p in folder.glob("*.json")])


def _filter_files(files: Iterable[str], include: Sequence[str], exclude: Sequence[str]) -> List[str]:
    out: List[str] = []
    for name in files:
        if include and not any(fnmatch.fnmatch(name, pat) for pat in include):
            continue
        if exclude and any(fnmatch.fnmatch(name, pat) for pat in exclude):
            continue
        out.append(name)
    return out


def _build_row_map(
    rows: Sequence[dict],
    key_fields: Tuple[str, ...],
    opts: DiffOptions,
) -> Tuple[Dict[RowKey, dict], int]:
    grouped: Dict[Tuple[Any, ...], List[dict]] = {}
    for row in rows:
        key = tuple(row.get(f) for f in key_fields)
        grouped.setdefault(key, []).append(row)

    row_map: Dict[RowKey, dict] = {}
    ambiguous = 0
    for key, items in grouped.items():
        if len(items) == 1:
            row_map[RowKey(base=key)] = items[0]
            continue
        ambiguous += len(items)
        sig_counts: Dict[str, int] = {}
        for row in items:
            sig = _canonical_row_signature(row, opts)
            sig_counts[sig] = sig_counts.get(sig, 0) + 1
            row_map[RowKey(base=key, sig=sig, sig_index=sig_counts[sig])] = row
    return row_map, ambiguous


def _format_row_label(
    row: dict,
    key_fields: Tuple[str, ...],
    key: RowKey,
    max_text: int,
) -> str:
    parts = []
    for field, value in zip(key_fields, key.base):
        parts.append(f"{field}={_truncate(value, max_text)}")
    if "name" in row and "name" not in key_fields:
        parts.append(f"name={_truncate(row.get('name', ''), max_text)}")
    if key.sig is not None:
        parts.append(f"dup={key.sig_index or 1}")
    return ", ".join(parts) if parts else "row"


def _truncate(value: Any, max_len: int) -> str:
    text = "" if value is None else str(value)
    if max_len <= 0 or len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_value(value: Any, opts: DiffOptions) -> str:
    if isinstance(value, str) or value is None:
        return _truncate(_normalize_text("" if value is None else value, opts), opts.max_text)
    return _truncate(json.dumps(value, ensure_ascii=True, sort_keys=True), opts.max_text)


def _diff_dict(old: dict, new: dict, opts: DiffOptions) -> Dict[str, Tuple[Any, Any]]:
    changed: Dict[str, Tuple[Any, Any]] = {}
    keys = set(old.keys()) | set(new.keys())
    for key in sorted(keys):
        if key in opts.ignore_fields:
            continue
        old_v = old.get(key)
        new_v = new.get(key)
        if not _values_equal(old_v, new_v, opts):
            changed[key] = (old_v, new_v)
    return changed


def _diff_list_of_dicts(
    file_name: str,
    old_rows: List[dict],
    new_rows: List[dict],
    opts: DiffOptions,
) -> Dict[str, Any]:
    key_fields = KEY_FIELDS.get(file_name) or _infer_key_fields(old_rows or new_rows) or ()
    if not key_fields:
        return _diff_list_as_multiset(old_rows, new_rows, opts, note="No key fields; using full-row multiset.")

    old_map, old_ambiguous = _build_row_map(old_rows, key_fields, opts)
    new_map, new_ambiguous = _build_row_map(new_rows, key_fields, opts)

    added_keys = [k for k in new_map.keys() if k not in old_map]
    removed_keys = [k for k in old_map.keys() if k not in new_map]
    common_keys = [k for k in new_map.keys() if k in old_map]

    changed_items = []
    for key in common_keys:
        old_row = old_map[key]
        new_row = new_map[key]
        changes = _diff_dict(old_row, new_row, opts)
        if changes:
            changed_items.append((key, changes))

    note_parts = []
    if file_name not in KEY_FIELDS:
        note_parts.append(f"Inferred key fields: {', '.join(key_fields)}")
    if old_ambiguous or new_ambiguous:
        note_parts.append("Duplicate keys detected; duplicates are disambiguated by full-row signature.")

    return {
        "key_fields": key_fields,
        "added": added_keys,
        "removed": removed_keys,
        "changed": changed_items,
        "note": " ".join(note_parts).strip(),
        "old_count": len(old_rows),
        "new_count": len(new_rows),
    }


def _diff_list_as_multiset(
    old_rows: List[Any],
    new_rows: List[Any],
    opts: DiffOptions,
    note: str,
) -> Dict[str, Any]:
    old_counts = Counter(_canonical_row_signature(r, opts) for r in old_rows)
    new_counts = Counter(_canonical_row_signature(r, opts) for r in new_rows)
    added = []
    removed = []
    for sig, count in (new_counts - old_counts).items():
        added.append((sig, count))
    for sig, count in (old_counts - new_counts).items():
        removed.append((sig, count))
    return {
        "key_fields": (),
        "added": added,
        "removed": removed,
        "changed": [],
        "note": note,
        "old_count": len(old_rows),
        "new_count": len(new_rows),
    }


def _render_text_report(
    results: List[Dict[str, Any]],
    old_dir: Path,
    new_dir: Path,
    opts: DiffOptions,
    summary_only: bool,
    old_only: Sequence[str],
    new_only: Sequence[str],
) -> str:
    lines = []
    lines.append("Wahapedia diff report")
    lines.append(f"Old: {old_dir}")
    lines.append(f"New: {new_dir}")
    lines.append(
        f"Options: strip_html={opts.strip_html}, normalize_punct={opts.normalize_punct}, normalize_ws={opts.normalize_ws}"
    )
    if old_only:
        lines.append(f"Only in old: {', '.join(old_only)}")
    if new_only:
        lines.append(f"Only in new: {', '.join(new_only)}")
    lines.append("")

    for result in results:
        lines.append(f"File: {result['file']}")
        lines.append(
            f"Counts: old={result['old_count']}, new={result['new_count']}, added={len(result['added'])}, "
            f"removed={len(result['removed'])}, changed={len(result['changed'])}"
        )
        if result.get("note"):
            lines.append(f"Note: {result['note']}")

        if summary_only:
            lines.append("")
            continue

        if result["added"]:
            lines.append("Added:")
            for item in result["added"]:
                if isinstance(item, RowKey):
                    row = result["new_map"][item]
                    label = _format_row_label(row, result["key_fields"], item, opts.max_text)
                    lines.append(f"  + {label}")
                else:
                    lines.append(f"  + {item}")

        if result["removed"]:
            lines.append("Removed:")
            for item in result["removed"]:
                if isinstance(item, RowKey):
                    row = result["old_map"][item]
                    label = _format_row_label(row, result["key_fields"], item, opts.max_text)
                    lines.append(f"  - {label}")
                else:
                    lines.append(f"  - {item}")

        if result["changed"]:
            lines.append("Changed:")
            for key, changes in result["changed"]:
                row = result["new_map"].get(key) or result["old_map"].get(key) or {}
                label = _format_row_label(row, result["key_fields"], key, opts.max_text)
                lines.append(f"  * {label}")
                for field, (old_v, new_v) in changes.items():
                    old_text = _format_value(old_v, opts)
                    new_text = _format_value(new_v, opts)
                    lines.append(f"      {field}: {old_text} -> {new_text}")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_json_report(results: List[Dict[str, Any]]) -> str:
    serializable = []
    for result in results:
        entry = dict(result)
        entry["added"] = _serialize_row_keys(entry["added"])
        entry["removed"] = _serialize_row_keys(entry["removed"])
        entry["changed"] = [
            {"key": _serialize_row_key(key), "changes": changes} for key, changes in entry["changed"]
        ]
        entry.pop("old_map", None)
        entry.pop("new_map", None)
        serializable.append(entry)
    return json.dumps(serializable, ensure_ascii=True, indent=2, sort_keys=True)


def _serialize_row_key(key: Any) -> Any:
    if isinstance(key, RowKey):
        return {"base": list(key.base), "sig": key.sig, "sig_index": key.sig_index}
    return key


def _serialize_row_keys(keys: List[Any]) -> List[Any]:
    return [_serialize_row_key(k) for k in keys]


def _diff_file(
    file_name: str,
    old_path: Path,
    new_path: Path,
    opts: DiffOptions,
) -> Dict[str, Any]:
    old_data = _read_json(old_path)
    new_data = _read_json(new_path)

    result: Dict[str, Any] = {"file": file_name}

    if isinstance(old_data, dict) and isinstance(new_data, dict):
        changes = _diff_dict(old_data, new_data, opts)
        result.update(
            {
                "key_fields": (),
                "added": [],
                "removed": [],
                "changed": [(RowKey(base=(file_name,)), changes)] if changes else [],
                "note": "",
                "old_count": len(old_data),
                "new_count": len(new_data),
                "old_map": {},
                "new_map": {},
            }
        )
        return result

    if isinstance(old_data, list) and isinstance(new_data, list) and all(
        isinstance(r, dict) for r in old_data + new_data
    ):
        list_result = _diff_list_of_dicts(file_name, old_data, new_data, opts)
        key_fields = list_result["key_fields"]
        old_map, _ = _build_row_map(old_data, key_fields, opts) if key_fields else ({}, 0)
        new_map, _ = _build_row_map(new_data, key_fields, opts) if key_fields else ({}, 0)
        result.update(list_result)
        result["old_map"] = old_map
        result["new_map"] = new_map
        return result

    if isinstance(old_data, list) and isinstance(new_data, list):
        list_result = _diff_list_as_multiset(old_data, new_data, opts, note="List diff via multiset.")
        result.update(list_result)
        result["old_map"] = {}
        result["new_map"] = {}
        return result

    result.update(
        {
            "key_fields": (),
            "added": [],
            "removed": [],
            "changed": [(RowKey(base=(file_name,)), {"type": (type(old_data), type(new_data))})],
            "note": "Type mismatch between old and new.",
            "old_count": 0,
            "new_count": 0,
            "old_map": {},
            "new_map": {},
        }
    )
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff Wahapedia JSON dumps between two folders.")
    parser.add_argument("--old", required=True, help="Path to old JSON dump folder.")
    parser.add_argument("--new", required=True, help="Path to new JSON dump folder.")
    parser.add_argument("--out", default="", help="Write report to this file instead of stdout.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument("--include", action="append", default=[], help="Include only matching filenames (glob).")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude matching filenames (glob).")
    parser.add_argument("--keep-html", action="store_true", help="Do not strip HTML tags before comparing strings.")
    parser.add_argument("--no-normalize-punct", action="store_true", help="Disable punctuation normalization.")
    parser.add_argument("--no-normalize-ws", action="store_true", help="Disable whitespace normalization.")
    parser.add_argument("--max-text", type=int, default=240, help="Max length of printed values (0 = no limit).")
    parser.add_argument("--ignore-field", action="append", default=[], help="Field name to ignore (repeatable).")
    parser.add_argument("--summary-only", action="store_true", help="Only print per-file counts.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    old_dir = Path(args.old).resolve()
    new_dir = Path(args.new).resolve()
    if not old_dir.exists() or not new_dir.exists():
        raise SystemExit("Both --old and --new must exist.")

    opts = DiffOptions(
        strip_html=not args.keep_html,
        normalize_punct=not args.no_normalize_punct,
        normalize_ws=not args.no_normalize_ws,
        max_text=args.max_text,
        ignore_fields=tuple(args.ignore_field),
    )

    old_files = set(_list_json_files(old_dir))
    new_files = set(_list_json_files(new_dir))
    old_only = sorted(old_files - new_files)
    new_only = sorted(new_files - old_files)
    all_files = sorted(old_files & new_files)
    all_files = _filter_files(all_files, args.include, args.exclude)

    results: List[Dict[str, Any]] = []
    for file_name in all_files:
        result = _diff_file(file_name, old_dir / file_name, new_dir / file_name, opts)
        results.append(result)

    if args.format == "json":
        report = _render_json_report(results)
    else:
        report = _render_text_report(results, old_dir, new_dir, opts, args.summary_only, old_only, new_only)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
    else:
        logger.info(report)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
