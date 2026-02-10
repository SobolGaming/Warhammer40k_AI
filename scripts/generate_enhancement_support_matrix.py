"""
Generate docs/ENHANCEMENT_SUPPORT_MATRIX.md from Wahapedia JSON.

Enhancements are sourced from `wahapedia_data/Enhancements.json` and grouped:
- Faction
  - Detachment

Support definitions (current engine state):
- Supported: enhancement rules effects are applied by the engine.
- Partial: enhancement can be loaded/assigned/scored (points/UI), but effects are not executed.
- Not implemented: enhancement cannot be loaded/assigned at all.

Exclusions:
- Detachments with `type == "Boarding Actions"` (from `wahapedia_data/Detachments.json`) are excluded from reporting.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import re
import logging
logger = logging.getLogger(__name__)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "ENHANCEMENT_SUPPORT_MATRIX.md")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _escape_md(text: str) -> str:
    return (text or "").replace("|", r"\|").strip()


@dataclass(frozen=True)
class EnhRow:
    id: str
    name: str
    faction_id: str
    detachment: str
    detachment_id: str
    cost: str
    legend: str
    description: str


def _load_factions() -> Dict[str, Dict[str, str]]:
    path = os.path.join(WAHA_DIR, "Factions.json")
    if not os.path.exists(path):
        return {}
    raw = _read_json(path)
    out: Dict[str, Dict[str, str]] = {}
    for item in raw:
        fid = item.get("id", "") or ""
        if not fid:
            continue
        out[fid] = {"name": item.get("name", "") or fid, "link": item.get("link", "") or ""}
    return out


def _load_enhancements() -> List[EnhRow]:
    path = os.path.join(WAHA_DIR, "Enhancements.json")
    raw = _read_json(path)
    out: List[EnhRow] = []
    for e in raw:
        out.append(
            EnhRow(
                id=e.get("id", "") or "",
                name=e.get("name", "") or "",
                faction_id=e.get("faction_id", "") or "",
                detachment=e.get("detachment", "") or "",
                detachment_id=e.get("detachment_id", "") or "",
                cost=e.get("cost", "") or "",
                legend=e.get("legend", "") or "",
                description=e.get("description", "") or "",
            )
        )
    return out


def _load_boarding_actions_detachment_ids() -> set[str]:
    path = os.path.join(WAHA_DIR, "Detachments.json")
    if not os.path.exists(path):
        return set()
    raw = _read_json(path)
    ids: set[str] = set()
    for d in raw:
        try:
            if (d.get("type") or "").strip().lower() != "boarding actions":
                continue
            did = (d.get("id") or "").strip()
            if did:
                ids.add(did)
        except Exception:
            continue
    return ids


def _normalize(text: str) -> str:
    t = (text or "").replace("’", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _strip_eligibility_prefix(text: str) -> str:
    t = _normalize(text)
    lower = t.lower()
    for marker in (" model only.", " models only."):
        idx = lower.find(marker)
        if idx != -1:
            return t[idx + len(marker) :].strip()
    return t


def _support_status(row: EnhRow) -> Tuple[str, str]:
    """
    Mirror the engine-side small pattern-based enhancement system.
    """
    rules = _strip_eligibility_prefix(row.description)

    # Supported patterns:
    m = re.search(r"add\s+(\d+)\s*\"\s+to\s+the\s+bearer'?s\s+move\s+characteristic\.", rules, flags=re.IGNORECASE)
    if m:
        return ("Supported", f'Add {m.group(1)}" to bearer Move.')

    m = re.search(r"add\s+(\d+)\s+to\s+the\s+bearer'?s\s+wounds\s+characteristic\.", rules, flags=re.IGNORECASE)
    if m:
        return ("Supported", f"Add {m.group(1)} to bearer Wounds.")

    m = re.search(
        r"improve\s+the\s+attacks,\s*strength\s+and\s+damage\s+characteristics\s+of\s+melee\s+weapons\s+equipped\s+by\s+the\s+bearer\s+by\s+(\d+)\.",
        rules,
        flags=re.IGNORECASE,
    )
    if m:
        return ("Supported", f"Improve melee weapons' A/S/D by {m.group(1)}.")

    m = re.search(
        r"each\s+time\s+an\s+attack\s+is\s+allocated\s+to\s+the\s+bearer,\s+subtract\s+(\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack\.",
        rules,
        flags=re.IGNORECASE,
    )
    if m:
        if re.search(r"\bif\s+that\s+attack\b", rules, flags=re.IGNORECASE):
            return ("Partial", "Conditional damage reduction (unconditional portion supported).")
        return ("Supported", f"Reduce damage allocated to bearer by {m.group(1)} (min 1).")

    return ("Partial", "Loadable/assignable + points counted + UI display; rules effects not executed yet.")


def _write_md(rows: List[EnhRow], factions: Dict[str, Dict[str, str]], excluded: int = 0) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    by_faction: Dict[str, List[EnhRow]] = {}
    for r in rows:
        by_faction.setdefault(r.faction_id, []).append(r)

    def faction_name(fid: str) -> str:
        return (factions.get(fid) or {}).get("name") or fid or "Unknown"

    def faction_link(fid: str) -> str:
        return (factions.get(fid) or {}).get("link") or ""

    lines: List[str] = []
    lines.append("# Enhancement support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/Enhancements.json` (faction names/links from `wahapedia_data/Factions.json`).")
    lines.append("")
    lines.append("**Definition of status**")
    lines.append("- **Supported**: enhancement rules effects are applied by the engine.")
    lines.append("- **Partial**: enhancement can be loaded/assigned/scored (points/UI), but effects are not executed.")
    lines.append("- **Not implemented**: enhancement cannot be loaded/assigned at all.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total enhancements: {len(rows)}")
    lines.append(f"- Factions: {len(by_faction)}")
    if excluded:
        lines.append(f"- Excluded (Boarding Actions detachments): {excluded}")
    lines.append("")
    lines.append("## Faction Enhancements")
    lines.append("")

    for fid in sorted(by_faction.keys(), key=lambda x: faction_name(x).lower()):
        header = f"### {faction_name(fid)} (`{fid}`)"
        link = faction_link(fid)
        if link:
            header += f" — `{_escape_md(link)}`"
        lines.append(header)
        lines.append("")

        # Group by detachment
        det_map: Dict[str, List[EnhRow]] = {}
        for r in by_faction[fid]:
            det_map.setdefault(r.detachment, []).append(r)

        for det in sorted(det_map.keys(), key=lambda s: (s or "").lower()):
            lines.append(f"#### {det}")
            lines.append("")
            lines.append("| Enhancement | ID | Cost | Status | Notes |")
            lines.append("|---|---:|---:|---|---|")
            for r in sorted(det_map[det], key=lambda x: (x.name.lower(), x.id)):
                status, notes = _support_status(r)
                lines.append(
                    f"| {_escape_md(r.name)} | `{_escape_md(r.id)}` | {_escape_md(r.cost)} | **{status}** | {_escape_md(notes)} |"
                )
            lines.append("")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> None:
    if not os.path.exists(WAHA_DIR):
        raise SystemExit(f"wahapedia_data dir not found at: {WAHA_DIR}")
    factions = _load_factions()
    rows = _load_enhancements()
    ba_ids = _load_boarding_actions_detachment_ids()
    excluded = 0
    if ba_ids:
        before = len(rows)
        rows = [r for r in rows if (r.detachment_id or "").strip() not in ba_ids]
        excluded = before - len(rows)
    _write_md(rows, factions, excluded=excluded)
    logger.info(f"Wrote {OUT_PATH} ({len(rows)} enhancements).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()

