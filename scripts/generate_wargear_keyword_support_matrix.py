"""
Generate docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md from Wahapedia JSON.

Keywords are extracted from `wahapedia_data/Datasheets_wargear.json` in the "description" field.
We treat the comma-separated "weapon abilities" list as keywords (after stripping HTML).

Output:
- HTML table (for row coloring) with Supported/Partial/Not implemented.
- Includes occurrence counts and a couple example renderings per keyword group.
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
        "rapid fire": "Adds attacks at half range.",
        "sustained hits": "Critical hits generate extra hits (integer values supported).",
        "torrent": "Auto-hits (also works under Overwatch restriction).",
        "anti": "Critical wound threshold vs matching target keyword (e.g. Anti-Infantry 4+).",
        "melta": "Adds damage at half range (integer values supported).",
    }

    # Partials: some related logic exists but full 10e rules not fully enforced.
    partial_notes: Dict[str, str] = {
        "pistol": "Used for fall back + shoot gating; full PISTOL targeting/engagement rules are not fully enforced.",
        "psychic": "Used for conditional FNP parsing (e.g. 'against psychic attacks'); no other special handling.",
        "feel no pain": "Supported as a defensive mechanic, but this list is extracted from weapon keywords; treat as informational.",
    }

    if c in supported_notes:
        # Validate parameter parsing limitations for some keyword families.
        if c == "rapid fire" and not _is_all_int_suffix(examples, "rapid fire"):
            return ("Partial", "Rapid Fire is implemented, but non-integer values (e.g. D3) are not supported.")
        if c == "sustained hits" and not _is_all_int_suffix(examples, "sustained hits"):
            return ("Partial", "Sustained Hits is implemented, but non-integer values (e.g. D3) are not supported.")
        if c == "melta":
            # melta parsing expects integer values
            for ex in examples:
                t = _normalize_token(ex)
                if t.startswith("melta "):
                    parts = t.split()
                    if len(parts) >= 2 and not parts[1].isdigit():
                        return ("Partial", "Melta is implemented, but non-integer values are not supported.")
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
        lines.append(f"<tr style=\"background-color: {bg};\">")
        lines.append(f"<td><code>{_escape_html(meta.canonical)}</code></td>")
        lines.append(f"<td><b>{_escape_html(status)}</b></td>")
        lines.append(f"<td>{meta.count}</td>")
        lines.append(f"<td>{ex_text}</td>")
        lines.append(f"<td>{_escape_html(notes)}</td>")
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

