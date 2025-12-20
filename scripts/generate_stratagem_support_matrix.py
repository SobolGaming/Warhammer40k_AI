"""
Generate docs/STRATAGEM_SUPPORT_MATRIX.md from Wahapedia JSON.

Grouping:
- Core Stratagems (global faction_id == "")
  - Sub-grouped by leading "mode" derived from stratagem 'type' (e.g. "Core", "Boarding Actions")
- Faction Stratagems
  - One section per faction
  - Within faction: "General" (no detachment) then one subsection per detachment

Support status is inferred from current rules engine implementation:
- Implemented: explicit gameplay logic exists (beyond CP spend + logging)
- Partial: implemented but known mismatch vs official wording/restrictions
- Not implemented: available in data but no effect logic wired in engine
- Not supported: filtered/mode not supported (e.g. Boarding Actions are excluded from standard games)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "STRATAGEM_SUPPORT_MATRIX.md")


@dataclass(frozen=True)
class StratagemRow:
    faction_id: str
    id: str
    name: str
    type: str
    cp_cost: str
    turn: str
    phase: str
    detachment: str
    description: str


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _escape_md(text: str) -> str:
    # Table safety: escape pipes; keep it minimal.
    return (text or "").replace("|", r"\|").strip()


def _mode_from_type(type_text: str) -> str:
    """
    Extract a high-level bucket from stratagem type.
    Examples:
      "Core – Battle Tactic Stratagem" -> "Core"
      "Boarding Actions – Epic Deed Stratagem" -> "Boarding Actions"
      "Crusade – Battle Tactic Stratagem" -> "Crusade"
      "Combat Patrol – Strategic Ploy Stratagem" -> "Combat Patrol"
    """
    t = (type_text or "").strip()
    if not t:
        return "Unknown"
    for sep in ("–", "-"):
        if sep in t:
            left = t.split(sep, 1)[0].strip()
            return left or "Unknown"
    # Fallback: first word-ish
    return t


def _load_stratagems() -> List[StratagemRow]:
    path = os.path.join(WAHA_DIR, "Stratagems.json")
    raw = _read_json(path)
    rows: List[StratagemRow] = []
    for item in raw:
        rows.append(
            StratagemRow(
                faction_id=item.get("faction_id", "") or "",
                id=item.get("id", "") or "",
                name=item.get("name", "") or "",
                type=item.get("type", "") or "",
                cp_cost=item.get("cp_cost", "") or "",
                turn=item.get("turn", "") or "",
                phase=item.get("phase", "") or "",
                detachment=item.get("detachment", "") or "",
                description=item.get("description", "") or "",
            )
        )
    return rows


def _load_factions() -> Dict[str, Dict[str, str]]:
    """
    Returns mapping id -> {name, link}.
    If Factions.json missing, return empty mapping.
    """
    path = os.path.join(WAHA_DIR, "Factions.json")
    if not os.path.exists(path):
        return {}
    raw = _read_json(path)
    out: Dict[str, Dict[str, str]] = {}
    for item in raw:
        fid = item.get("id", "") or ""
        if not fid:
            continue
        out[fid] = {
            "name": item.get("name", "") or fid,
            "link": item.get("link", "") or "",
        }
    return out


def _support_classification(row: StratagemRow) -> Tuple[str, str]:
    """
    Returns (status, notes).
    """
    name_u = (row.name or "").strip().upper()
    type_l = (row.type or "").strip().lower()

    # The engine currently filters out Boarding Actions stratagems for standard games.
    if "boarding actions" in type_l or "boarding action" in type_l:
        return (
            "Not supported",
            "Boarding Actions are filtered out by `StratagemManager._build_available()`.",
        )

    # Implemented/partial set based on current `classes/stratagems.py`.
    implemented = {
        "COMMAND RE-ROLL": "Queued on `roll_made`; executes a reroll callback; once-per-turn guard.",
        "FIRE OVERWATCH": "Queued on enemy movement start/end; resolves shooting with hit-on-6s restriction.",
        "RAPID INGRESS": "Queued at end of opponent Movement phase; places a reserves unit immediately.",
        "NEW ORDERS": "End of your Command phase: discard 1 active Secondary and draw (Leviathan-style).",
    }
    if name_u in implemented:
        return ("Implemented", implemented[name_u])

    # Partial: implemented but mismatched vs official wording/restrictions.
    if name_u == "INSANE BRAVERY":
        return (
            "Partial",
            "Implemented as a post-fail Battle-shock cancel (removes Battle-shock). Once-per-battle restriction not enforced; differs from datasheet timing.",
        )

    return ("Not implemented", "No effect logic currently wired (would just spend CP and log a warning).")


def _sort_key(row: StratagemRow) -> Tuple[str, str, str]:
    return (_escape_md(row.name).lower(), row.id, row.type)


def _write_md(rows: List[StratagemRow], factions: Dict[str, Dict[str, str]]) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    core = [r for r in rows if not (r.faction_id or "").strip()]
    faction_rows = [r for r in rows if (r.faction_id or "").strip()]

    # Core sub-group by mode
    core_by_mode: Dict[str, List[StratagemRow]] = {}
    for r in core:
        core_by_mode.setdefault(_mode_from_type(r.type), []).append(r)

    # Faction grouping
    by_faction: Dict[str, List[StratagemRow]] = {}
    for r in faction_rows:
        by_faction.setdefault(r.faction_id, []).append(r)

    # Human-readable faction ordering
    def faction_display(fid: str) -> str:
        info = factions.get(fid) or {}
        return info.get("name") or fid

    faction_order = sorted(by_faction.keys(), key=lambda fid: faction_display(fid).lower())

    def row_line(r: StratagemRow) -> str:
        status, notes = _support_classification(r)
        return (
            f"| {_escape_md(r.name)} | `{_escape_md(r.id)}` | {_escape_md(r.type)} | {_escape_md(r.cp_cost)} | "
            f"{_escape_md(r.turn)} | {_escape_md(r.phase)} | **{status}** | {_escape_md(notes)} |"
        )

    total = len(rows)
    total_core = len(core)
    total_faction = len(faction_rows)
    total_detachment = sum(1 for r in faction_rows if (r.detachment or "").strip())

    # Write
    lines: List[str] = []
    lines.append("# Stratagem support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/Stratagems.json` (and faction names from `wahapedia_data/Factions.json`).")
    lines.append("")
    lines.append("**Definition of status**")
    lines.append("- **Implemented**: the stratagem has explicit gameplay logic in the engine (beyond CP spend + logging).")
    lines.append("- **Partial**: some gameplay logic exists, but key restrictions/timing/text are not fully matched.")
    lines.append("- **Not implemented**: no gameplay effect logic wired yet.")
    lines.append("- **Not supported**: currently excluded by game-mode filtering (e.g. Boarding Actions).")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total stratagem rows: {total}")
    lines.append(f"- Core (global) stratagem rows (`faction_id == \"\"`): {total_core}")
    lines.append(f"- Faction stratagem rows: {total_faction} (detachment-specific: {total_detachment})")
    lines.append("")
    lines.append("## Core Stratagems")
    lines.append("")
    lines.append("> Note: Boarding Actions (and similar mode-specific) stratagems are present in Wahapedia data, but are not used in standard games by this engine today.")
    lines.append("")

    for mode in sorted(core_by_mode.keys(), key=lambda s: s.lower()):
        bucket = sorted(core_by_mode[mode], key=_sort_key)
        lines.append(f"### {mode}")
        lines.append("")
        lines.append("| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |")
        lines.append("|---|---:|---|---:|---|---|---|---|")
        for r in bucket:
            lines.append(row_line(r))
        lines.append("")

    lines.append("## Faction Stratagems")
    lines.append("")

    for fid in faction_order:
        info = factions.get(fid) or {}
        name = info.get("name") or fid
        link = info.get("link") or ""
        header = f"### {name}"
        if link:
            header = f"### {name} (`{fid}`) — `{_escape_md(link)}`"
        else:
            header = f"### {name} (`{fid}`)"
        lines.append(header)
        lines.append("")

        rows_f = by_faction.get(fid, [])
        general = [r for r in rows_f if not (r.detachment or "").strip()]
        det_rows = [r for r in rows_f if (r.detachment or "").strip()]

        # General (non-detachment)
        if general:
            lines.append("#### General")
            lines.append("")
            lines.append("| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |")
            lines.append("|---|---:|---|---:|---|---|---|---|")
            for r in sorted(general, key=_sort_key):
                lines.append(row_line(r))
            lines.append("")

        # Detachment subsections
        det_by_name: Dict[str, List[StratagemRow]] = {}
        for r in det_rows:
            det_by_name.setdefault((r.detachment or "").strip(), []).append(r)
        for det_name in sorted(det_by_name.keys(), key=lambda s: s.lower()):
            lines.append(f"#### {det_name}")
            lines.append("")
            lines.append("| Stratagem | ID | Type | CP | Turn | Phase | Status | Notes |")
            lines.append("|---|---:|---|---:|---|---|---|---|")
            for r in sorted(det_by_name[det_name], key=_sort_key):
                lines.append(row_line(r))
            lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    if not os.path.exists(WAHA_DIR):
        raise SystemExit(f"wahapedia_data dir not found at: {WAHA_DIR}")
    rows = _load_stratagems()
    factions = _load_factions()
    _write_md(rows, factions)
    print(f"Wrote {OUT_PATH} ({len(rows)} stratagem rows).")


if __name__ == "__main__":
    main()

