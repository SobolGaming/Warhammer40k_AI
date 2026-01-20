"""
Generate docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md from Wahapedia JSON.

Keywords are extracted from `wahapedia_data/Datasheets_wargear.json` in the "description" field.
We treat the comma-separated "weapon abilities" list as keywords (after stripping HTML).

Output:
- HTML table (for row coloring) with Supported/Partial/Not implemented.
- Includes occurrence counts and a couple example renderings per keyword group.

Note on Boarding Actions detachments:
- This matrix is generated from `Datasheets_wargear.json`, which is **not detachment-scoped** (no detachment_id/type),
  so "Boarding Actions" detachment filtering does not apply here in a meaningful way.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "WARGEAR_KEYWORD_SUPPORT_MATRIX.md")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = text.replace("’", "'")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _escape_html(text: str) -> str:
    # For table rendering safety
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _normalize_token(token: str) -> str:
    t = _strip_html(token).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .;")


def _canonical_keyword(token: str) -> str:
    """
    Canonicalize parameterized keywords so we don't explode the matrix into 200 variants.
    """
    t = _normalize_token(token)
    if not t:
        return ""
    if t.startswith("anti-"):
        return "anti"
    if t.startswith("rapid fire"):
        return "rapid fire"
    if t.startswith("sustained hits"):
        return "sustained hits"
    if t.startswith("melta"):
        return "melta"
    if t.startswith("feel no pain"):
        return "feel no pain"
    return t


@dataclass(frozen=True)
class KeywordMeta:
    canonical: str
    count: int
    examples: Tuple[str, ...]


def _parse_keywords_from_wargear() -> Tuple[Dict[str, int], Dict[str, Set[str]]]:
    path = os.path.join(WAHA_DIR, "Datasheets_wargear.json")
    rows = _read_json(path)
    counts: Dict[str, int] = {}
    examples: Dict[str, Set[str]] = {}
    for r in rows:
        desc = r.get("description", "")
        if not desc:
            continue
        # Wahapedia's "description" is typically a comma-separated list of keyword-ish items.
        # Some entries also use " . " or ";" as separators. We treat those as separators too.
        desc_text = _strip_html(desc)
        parts = [p.strip() for p in re.split(r"\s*,\s*|\s*;\s*|\s+\.\s+", desc_text) if p.strip()]
        for raw in parts:
            canon = _canonical_keyword(raw)
            if not canon:
                continue
            counts[canon] = counts.get(canon, 0) + 1
            examples.setdefault(canon, set()).add(_strip_html(raw))
    return counts, examples


def _is_all_int_suffix(examples: Set[str], prefix: str) -> bool:
    """
    Examples:
      "rapid fire 1" -> ok
      "rapid fire d3" -> not ok
      "rapid fire" -> ok (defaults)
    """
    p = prefix.lower()
    for ex in examples:
        t = _normalize_token(ex)
        if not t.startswith(p):
            continue
        parts = t.split()
        if len(parts) <= 2:
            continue
        if not parts[2].isdigit():
            return False
    return True


def _keyword_support(canon: str, examples: Set[str]) -> Tuple[str, str]:
    """
    Returns (status, notes), where status is Supported / Partial / Not implemented.
    This is based on the current rules engine behavior in `classes/wargear.py`, `classes/unit.py`, and `classes/map.py`.
    """
    c = canon.lower().strip()

    # Supported keywords with explicit gameplay effects implemented:
    supported_notes: Dict[str, str] = {
        "assault": "Shooting after Advance is allowed for Assault profiles.",
        "blast": "Adds attacks based on target unit size.",
        "devastating wounds": "Critical wounds become mortal wounds.",
        "hazardous": "Hazardous test after attacking; on 1 suffer mortal wounds.",
        "heavy": "+1 to hit if the firing unit Remained Stationary.",
        "ignores cover": "Cancels Benefit of Cover from terrain and Indirect Fire.",
        "indirect fire": "No-LOS penalties and grants target Benefit of Cover (unless Ignores Cover).",
        "lethal hits": "Critical hits auto-wound.",
        "plunging fire": "AP improves by 1 when plunging fire conditions are met.",
        "rapid fire": "Adds attacks at half range (supports dice values like D3/D6+X).",
        "sustained hits": "Critical hits generate extra hits (supports dice values like D3/D6+X; rolled per critical hit).",
        "torrent": "Auto-hits (also works under Overwatch restriction).",
        "anti": "Critical wound threshold vs matching target keyword (e.g. Anti-Infantry 4+).",
        "melta": "Adds damage at half range (supports dice values like D3/D6+X).",
        "extra attacks": "Melee selection supports 1 primary weapon plus all [EXTRA ATTACKS] weapons.",
        "one shot": "Enforced: each model can use a ONE SHOT weapon once per battle.",
        "pistol": "Engaged shooting + pistol-vs-other-ranged choice enforced (10e).",
        "lance": "If the bearer charged this turn, +1 to wound rolls for this weapon.",
        "twin-linked": "Re-roll failed wound rolls for attacks made with this weapon.",
        "precision": "Allows allocating a successful wound to a visible CHARACTER in an Attached unit.",
        "psychic": "Tags Psychic attacks; conditional defenses (FNP/Invulnerable) check this keyword.",
        "conversion": "Unmodified successful hits of 4+ become critical hits when the target is beyond the Conversion distance.",
        # Ork-specific keywords
        "bubblechukka": "Random profile selection via D6 roll (1-2: big bubble, 3-4: wobbly bubble, 5-6: dense bubble).",
        "dead choppy": "+1 Attacks for each additional dread klaw equipped.",
        "harpooned": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.",
        "hooked": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.",
        "impaled": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.",
        "snagged": "Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.",
    }

    # Partials: some related logic exists but full 10e rules not fully enforced.
    partial_notes: Dict[str, str] = {
        "feel no pain": "Supported as a defensive mechanic, but this list is extracted from weapon keywords; treat as informational.",
    }

    if c in supported_notes:
        # Validate parameter parsing limitations for some keyword families.
        # Rapid Fire / Sustained Hits / Melta support dice expressions in the engine now.
        if c == "anti":
            # anti parsing expects "anti-<keyword> <num>+"
            for ex in examples:
                t = _normalize_token(ex)
                if t.startswith("anti-"):
                    # crude validation
                    m = re.match(r"^anti-[a-z0-9\- ]+\s+\d\+?$", t)
                    if not m:
                        return ("Partial", "Anti is implemented, but some unusual formatting may not be parsed correctly.")
        return ("Supported", supported_notes[c])

    if c in partial_notes:
        return ("Partial", partial_notes[c])

    return ("Not implemented", "No explicit gameplay effect currently wired for this keyword.")


def _row_color(status: str) -> str:
    # Soft bootstrap-like colors that work on GitHub
    if status == "Supported":
        return "#d4edda"  # green-ish
    if status == "Partial":
        return "#fff3cd"  # yellow-ish
    return "#f8d7da"  # red-ish


def _status_icon(status: str) -> str:
    # Fallback for renderers that strip HTML attributes/styles
    if status == "Supported":
        return "🟩"
    if status == "Partial":
        return "🟨"
    return "🟥"


def _write_md(counts: Dict[str, int], examples: Dict[str, Set[str]]) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    items: List[KeywordMeta] = []
    for canon, cnt in counts.items():
        ex = tuple(sorted(examples.get(canon, set()))[:3])
        items.append(KeywordMeta(canonical=canon, count=cnt, examples=ex))

    # Sort alphabetically (stable for quick lookup)
    items.sort(key=lambda k: k.canonical.lower())

    lines: List[str] = []
    lines.append("# Wargear keyword support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/Datasheets_wargear.json` (`description` field).")
    lines.append("")
    lines.append("> Note: Boarding Actions detachment filtering is not applicable here (wargear keywords are not detachment-scoped in Wahapedia data).")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- **Green**: Supported")
    lines.append("- **Yellow**: Partial")
    lines.append("- **Red**: Not implemented")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("<table>")
    lines.append("<thead>")
    lines.append("<tr>")
    lines.append("<th>Keyword (canonical)</th>")
    lines.append("<th>Status</th>")
    lines.append("<th>Occurrences</th>")
    lines.append("<th>Examples</th>")
    lines.append("<th>Notes</th>")
    lines.append("</tr>")
    lines.append("</thead>")
    lines.append("<tbody>")

    for meta in items:
        status, notes = _keyword_support(meta.canonical, examples.get(meta.canonical, set()))
        bg = _row_color(status)
        ex_text = "<br/>".join(_escape_html(e) for e in meta.examples) if meta.examples else ""
        # Many renderers strip CSS from HTML in Markdown. `bgcolor` is more broadly supported,
        # so apply it per-cell. Also include a status icon fallback.
        icon = _status_icon(status)
        lines.append("<tr>")
        lines.append(f"<td bgcolor=\"{bg}\"><code>{_escape_html(meta.canonical)}</code></td>")
        lines.append(f"<td bgcolor=\"{bg}\"><b>{_escape_html(icon)} {_escape_html(status)}</b></td>")
        lines.append(f"<td bgcolor=\"{bg}\">{meta.count}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{ex_text}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{_escape_html(notes)}</td>")
        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This is keyword-level support only. Many faction/unit abilities interact with attacks outside these keywords.")
    lines.append("- This matrix groups parameterized keywords (e.g. `anti-infantry 4+`, `anti-vehicle 3+`) under a single canonical row (`anti`).")
    lines.append("")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> None:
    if not os.path.exists(WAHA_DIR):
        raise SystemExit(f"wahapedia_data dir not found at: {WAHA_DIR}")
    counts, examples = _parse_keywords_from_wargear()
    _write_md(counts, examples)
    print(f"Wrote {OUT_PATH} ({len(counts)} canonical keywords).")


if __name__ == "__main__":
    main()
