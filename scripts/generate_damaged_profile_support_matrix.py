"""
Generate docs/DAMAGED_PROFILE_SUPPORT_MATRIX.md from Wahapedia Datasheets.json.

We consider a "damaged profile" any datasheet row that has:
- damaged_w
- damaged_description

We group damaged profiles by a small set of canonical text patterns and report:
- Count of datasheets using that pattern
- A couple example datasheets
- Engine support status (Supported / Partial / Not implemented)

Rendering:
- HTML table with bgcolor per cell + unicode icon fallback (like WARGEAR_KEYWORD_SUPPORT_MATRIX.md)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from warhammer40k_ai.waha_helper.waha_helper import WahaHelper
import logging
logger = logging.getLogger(__name__)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "DAMAGED_PROFILE_SUPPORT_MATRIX.md")


def _escape_html(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _row_color(status: str) -> str:
    if status == "Supported":
        return "#d4edda"
    if status == "Partial":
        return "#fff3cd"
    return "#f8d7da"


def _status_icon(status: str) -> str:
    if status == "Supported":
        return "🟩"
    if status == "Partial":
        return "🟨"
    return "🟥"


@dataclass(frozen=True)
class DamagedRow:
    datasheet_id: str
    datasheet_name: str
    damaged_w: str
    description: str


@dataclass(frozen=True)
class PatternGroup:
    key: str
    count: int
    examples: Tuple[str, ...]
    status: str
    notes: str


_RX_HIT_MINUS = re.compile(r"subtract\s+(\d+)\s+from\s+the\s+hit\s+roll", re.IGNORECASE)
_RX_OC_MINUS = re.compile(
    r"subtract\s+(\d+)\s+from\s+(?:this\s+(?:model|unit)'?s|its)\s+objective\s+control\s+characteristic",
    re.IGNORECASE,
)
_RX_HALF_ATTACKS = re.compile(
    r"halve\s+the\s+attacks\s+characteristic|attacks\s+characteristics\s+of\s+all\s+of\s+its\s+weapons\s+are\s+halved",
    re.IGNORECASE,
)
_RX_ADD_ATTACKS_MELEE = re.compile(
    r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+melee\s+weapons",
    re.IGNORECASE,
)
_RX_ADD_ATTACKS_WEAPON = re.compile(
    r"add\s+(\d+)\s+to\s+the\s+attacks\s+characteristic\s+of\s+this\s+model'?s\s+([a-z0-9 \-']+)",
    re.IGNORECASE,
)
_RX_RELICS_LIMIT = re.compile(r"relics\s+of\s+the\s+matriarchs.*only\s+select\s+one\s+ability", re.IGNORECASE)


def _canonicalize(desc: str) -> str:
    # Already cleaned by WahaHelper, but be safe.
    t = (desc or "").replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _pattern_key(desc: str) -> str:
    t = _canonicalize(desc)
    parts: List[str] = []
    if _RX_HIT_MINUS.search(t):
        parts.append("Hit roll -N")
    if _RX_OC_MINUS.search(t):
        parts.append("OC -N")
    if _RX_HALF_ATTACKS.search(t):
        parts.append("Halve Attacks")
    if _RX_ADD_ATTACKS_MELEE.search(t):
        parts.append("Melee Attacks +N")
    else:
        m = _RX_ADD_ATTACKS_WEAPON.search(t)
        if m and "melee weapons" not in t.lower():
            # Avoid generic "weapons"
            wname = (m.group(2) or "").strip().lower()
            if wname and wname not in ("weapons", "weapon"):
                parts.append("Specific weapon Attacks +N")
    if _RX_RELICS_LIMIT.search(t):
        parts.append("Limit Relics of the Matriarchs choices")
    if not parts:
        return "Other / unclassified"
    return " + ".join(parts)


def _support_for_key(key: str) -> Tuple[str, str]:
    # Mirror current engine implementation (Unit._apply_damaged_profile_effects + WargearProfile hooks).
    supported = {
        "Hit roll -N": "Implemented: applies a damaged-profile to-hit modifier (-N) with normal +/-1 cap handling.",
        "OC -N": "Implemented: applies an additive Objective Control penalty while damaged.",
        "Halve Attacks": "Implemented: halves the weapon's attacks characteristic while damaged (round up).",
        "Hit roll -N + OC -N": "Implemented: applies both -N to hit and OC penalty while damaged.",
        "Hit roll -N + Halve Attacks": "Implemented: applies both -N to hit and halved attacks while damaged.",
        "Hit roll -N + OC -N + Halve Attacks": "Implemented: applies all three effects while damaged.",
        "Melee Attacks +N": "Implemented: adds +N attacks for melee weapons while damaged (as written on datasheet).",
        "Specific weapon Attacks +N": "Implemented: adds +N attacks for a specific named weapon while damaged (best-effort name match).",
        "Limit Relics of the Matriarchs choices": "Implemented: damaged profile limits Relics of the Matriarchs selection to one relic ability.",
    }
    if key in supported:
        return "Supported", supported[key]
    if key == "Other / unclassified":
        return "Not implemented", "No parser/engine effect wired for this damaged profile text yet."
    # Partial: we recognized some keyword but not all effect text (future-proof bucket).
    return "Partial", "Some damaged-profile text is recognized, but not all effects are implemented."


def main() -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    waha = WahaHelper(data_dir=os.path.join(ROOT, "wahapedia_data"))
    rows: List[DamagedRow] = []
    for ds in waha.datasheets.values():
        dw = ds.get("damaged_w")
        dd = ds.get("damaged_description")
        if not dw or not dd:
            continue
        rows.append(DamagedRow(datasheet_id=ds.get("id", ""), datasheet_name=ds.get("name", ""), damaged_w=str(dw), description=str(dd)))

    groups: Dict[str, List[DamagedRow]] = {}
    for r in rows:
        groups.setdefault(_pattern_key(r.description), []).append(r)

    pattern_groups: List[PatternGroup] = []
    for key, items in groups.items():
        status, notes = _support_for_key(key)
        examples = tuple(f"{it.datasheet_name} (`{it.datasheet_id}`) [{it.damaged_w}]" for it in sorted(items, key=lambda x: (x.datasheet_name.lower(), x.datasheet_id))[:3])
        pattern_groups.append(PatternGroup(key=key, count=len(items), examples=examples, status=status, notes=notes))

    pattern_groups.sort(key=lambda pg: (-pg.count, pg.key.lower()))

    total = len(rows)
    supported_n = sum(1 for r in rows if _support_for_key(_pattern_key(r.description))[0] == "Supported")

    lines: List[str] = []
    lines.append("# Damaged profile support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/Datasheets.json` (`damaged_w` + `damaged_description`).")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- **Green**: Supported")
    lines.append("- **Yellow**: Partial")
    lines.append("- **Red**: Not implemented")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Datasheets with damaged profiles: {total}")
    lines.append(f"- Supported (by current parser): {supported_n}")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("<table>")
    lines.append("<thead>")
    lines.append("<tr>")
    lines.append("<th>Canonical pattern</th>")
    lines.append("<th>Status</th>")
    lines.append("<th>Count</th>")
    lines.append("<th>Examples</th>")
    lines.append("<th>Notes</th>")
    lines.append("</tr>")
    lines.append("</thead>")
    lines.append("<tbody>")

    for pg in pattern_groups:
        bg = _row_color(pg.status)
        icon = _status_icon(pg.status)
        ex = "<br/>".join(_escape_html(e) for e in pg.examples)
        lines.append("<tr>")
        lines.append(f"<td bgcolor=\"{bg}\"><code>{_escape_html(pg.key)}</code></td>")
        lines.append(f"<td bgcolor=\"{bg}\"><b>{_escape_html(icon)} {_escape_html(pg.status)}</b></td>")
        lines.append(f"<td bgcolor=\"{bg}\">{pg.count}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{ex}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{_escape_html(pg.notes)}</td>")
        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This matrix reports common *text patterns* in degraded/damaged profiles, not per-faction rules.")
    lines.append("- Some damaged profiles reference a specific model in a unit (e.g. named character inside a multi-model unit). The engine currently applies damaged profile effects at the unit level (best-effort).")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    logger.info(f"Wrote {OUT_PATH} ({len(pattern_groups)} pattern groups; {total} datasheets).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
