"""
Generate docs/STRATAGEM_SUPPORT_MATRIX.md from Wahapedia JSON.

Grouping:
- Core Stratagems (global faction_id == "")
  - Sub-grouped by leading "mode" derived from stratagem 'type' (e.g. "Core")
- Faction Stratagems
  - One section per faction
  - Within faction: "General" (no detachment) then one subsection per detachment

Support status is inferred from current rules engine implementation:
- Implemented: explicit gameplay logic exists (beyond CP spend + logging)
- Partial: implemented but known mismatch vs official wording/restrictions
- Not implemented: available in data but no effect logic wired in engine

Exclusions:
- Detachments with `type == "Boarding Actions"` (from `wahapedia_data/Detachments.json`) are excluded from reporting.
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
    detachment_id: str
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
            # Merge "Core Stratagem – ..." into "Core" so we don't produce a second Core section.
            if left.strip().lower() == "core stratagem":
                return "Core"
            return left or "Unknown"
    # Fallback: first word-ish
    if t.strip().lower() == "core stratagem":
        return "Core"
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
                detachment_id=item.get("detachment_id", "") or "",
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


def _load_boarding_actions_detachments() -> tuple[set[str], set[str]]:
    """
    Returns (detachment_ids, detachment_names) where detachment type is 'Boarding Actions'.
    """
    path = os.path.join(WAHA_DIR, "Detachments.json")
    if not os.path.exists(path):
        return set(), set()
    raw = _read_json(path)
    ids: set[str] = set()
    names: set[str] = set()
    for d in raw:
        try:
            if (d.get("type") or "").strip().lower() != "boarding actions":
                continue
            did = (d.get("id") or "").strip()
            if did:
                ids.add(did)
            nm = (d.get("name") or "").strip()
            if nm:
                names.add(nm)
        except Exception:
            continue
    return ids, names


def _support_classification(row: StratagemRow) -> Tuple[str, str]:
    """
    Returns (status, notes).
    """
    name_u = (row.name or "").strip().upper()
    # Implemented/partial set based on current `classes/stratagems.py`.
    implemented = {
        "COMMAND RE-ROLL": "Queued on `roll_made`; executes a reroll callback; limited by core once-per-phase stratagem rule (per player).",
        "FIRE OVERWATCH": "Queued on enemy movement start/end; resolves shooting with hit-on-6s restriction.",
        "RAPID INGRESS": "Queued at end of opponent Movement phase; places a reserves unit immediately.",
        "NEW ORDERS": "End of your Command phase: discard 1 active Secondary and draw.",
        "TANK SHOCK": "Charge phase: after a VEHICLE ends a Charge move; roll D6 equal to a VEHICLE model’s Toughness; 5+ = 1 MW (max 6).",
        "GRENADE": "Shooting phase: pick a GRENADES unit + eligible enemy within 8\"; roll 6D6; 4+ = 1 MW.",
        "GO TO GROUND": "Opponent Shooting phase: after targets selected; INFANTRY gains Benefit of Cover + 6++ until end of phase.",
        "INSANE BRAVERY": "Command phase Battle-shock step: before a unit tests; that unit auto-passes. Once per battle enforced.",
        "SMOKESCREEN": "Opponent Shooting phase: after targets selected; a SMOKE unit gains Benefit of Cover + Stealth until end of phase.",
        "EPIC CHALLENGE": "Fight phase: when a CHARACTER is selected to fight near an enemy Attached unit; one CHARACTER model’s melee attacks gain [PRECISION] until end of phase.",
    }
    if name_u in implemented:
        return ("Implemented", implemented[name_u])

    # Partial: implemented but mismatched vs official wording/restrictions.

    return ("Not implemented", "No effect logic currently wired (would just spend CP and log a warning).")


def _sort_key(row: StratagemRow) -> Tuple[str, str, str]:
    return (_escape_md(row.name).lower(), row.id, row.type)


def _write_md(rows: List[StratagemRow], factions: Dict[str, Dict[str, str]]) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    ba_detachment_ids, ba_detachment_names = _load_boarding_actions_detachments()
    excluded = 0
    filtered_rows: List[StratagemRow] = []
    for r in rows:
        mode = _mode_from_type(r.type).strip().lower()
        # We will not support the "Challenger" stratagem pack; exclude from reporting.
        if mode == "challenger":
            excluded += 1
            continue
        if mode == "boarding actions" or "boarding action" in (r.type or "").lower():
            excluded += 1
            continue
        if (r.detachment_id or "").strip() in ba_detachment_ids:
            excluded += 1
            continue
        if (r.detachment or "").strip() in ba_detachment_names:
            excluded += 1
            continue
        filtered_rows.append(r)

    # Chapter Approved scope: only list global (core) stratagems; do not list faction/detachment stratagems.
    core_all = [r for r in filtered_rows if not (r.faction_id or "").strip()]
    # Keep only the "Core" bucket (merging "Core Stratagem" into "Core" via _mode_from_type()).
    core_mode_filtered = [r for r in core_all if _mode_from_type(r.type).strip().lower() == "core"]
    # Deduplicate by name: keep newest/highest id (so NEW ORDERS is only shown once).
    by_name: Dict[str, StratagemRow] = {}
    for r in core_mode_filtered:
        key = (r.name or "").strip().upper()
        if not key:
            continue
        prev = by_name.get(key)
        if prev is None or (r.id or "") > (prev.id or ""):
            by_name[key] = r
    core = list(by_name.values())
    faction_rows: List[StratagemRow] = []

    # Core sub-group by mode (will only be "Core" in Chapter Approved scope)
    core_by_mode: Dict[str, List[StratagemRow]] = {}
    for r in core:
        core_by_mode.setdefault(_mode_from_type(r.type), []).append(r)

    def row_line(r: StratagemRow) -> str:
        status, notes = _support_classification(r)
        return (
            f"| {_escape_md(r.name)} | `{_escape_md(r.id)}` | {_escape_md(r.type)} | {_escape_md(r.cp_cost)} | "
            f"{_escape_md(r.turn)} | {_escape_md(r.phase)} | **{status}** | {_escape_md(notes)} |"
        )

    total = len(core)
    total_core = len(core)
    total_faction = len(faction_rows)
    total_detachment = 0

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
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total stratagem rows: {total}")
    lines.append(f"- Core (global) stratagem rows (`faction_id == \"\"`): {total_core}")
    lines.append(f"- Faction stratagem rows: {total_faction} (detachment-specific: {total_detachment})")
    lines.append(f"- Excluded (Boarding Actions detachments / mode): {excluded}")
    lines.append("")
    lines.append("## Core Stratagems")
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
    lines.append("<!-- Chapter Approved scope: faction/detachment stratagems intentionally omitted -->")

    content = "\n".join(lines).rstrip() + "\n"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    if not os.path.exists(WAHA_DIR):
        raise SystemExit(f"wahapedia_data dir not found at: {WAHA_DIR}")
    rows = _load_stratagems()
    factions = _load_factions()
    _write_md(rows, factions)
    print(f"Wrote {OUT_PATH}.")


if __name__ == "__main__":
    main()

