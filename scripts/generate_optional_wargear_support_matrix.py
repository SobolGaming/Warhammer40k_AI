"""
Generate docs/OPTIONAL_WARGEAR_SUPPORT_MATRIX.md from Wahapedia Datasheets_options.json.

We treat each datasheet option line as a "wargear option rule" and classify support based on:
- Whether our option parser (parse_alternate_3) can parse the line at all.
- Whether the parsed option requires constraints we don't yet fully enforce (Partial).

Rendering:
- HTML table with bgcolor + unicode icon status column (same style as other support matrices).
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

from warhammer40k_ai.classes.wargear import parse_alternate_3
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "OPTIONAL_WARGEAR_SUPPORT_MATRIX.md")


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


def _canonicalize(desc: str) -> str:
    t = (desc or "").replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _pattern_key(desc: str) -> str:
    t = _canonicalize(desc).lower()
    parts: List[str] = []

    if t == "none":
        return "None"

    if "<ul" in t or "<li" in t:
        parts.append("HTML list")
    if "one of the following" in t:
        parts.append("One-of list")
    if "up to" in t:
        parts.append("Up to N")
    if "any number of" in t:
        parts.append("Any number")
    if t.startswith("for every"):
        parts.append("For every N models")
    if t.startswith("if this unit contains"):
        parts.append("If unit contains N models")
    if "can be replaced with" in t or "replaced with" in t:
        parts.append("Replacement")
    elif "can be equipped with" in t or "be equipped with" in t:
        parts.append("Additional")
    else:
        parts.append("Other / unclassified")

    # More granular: per-model vs unit-wide
    if "can each" in t or "each have" in t:
        parts.append("Per-model")
    elif "this unit can be equipped" in t or "in this unit" in t:
        parts.append("Unit-wide / scaling")

    return " + ".join(parts)


def _support_for_desc(desc: str) -> Tuple[str, str]:
    """
    Classification rules:
    - Supported: parsed and doesn't depend on constraints we don't enforce.
    - Partial: parsed but has complex conditionals/limits we don't fully enforce.
    - Not implemented: cannot parse.
    """
    # Create a dummy unit with models list so "any number ... max=len(models)" can work.
    dummy_unit = type("DummyUnit", (), {"models": [object() for _ in range(10)]})()

    try:
        parsed = parse_alternate_3([desc], dummy_unit)
    except Exception:
        return "Not implemented", "Parser raised while interpreting this option text (unhandled pattern)."
    if not parsed:
        return "Not implemented", "Parser could not interpret this option text."

    # Heuristic: if any option has non-trivial constraints, mark Partial.
    # Constraints we still consider "Partial" (not fully enforced / needs richer selection UI).
    hard_conditional_markers = (
        "item_limit is equal to number of equipped",
        "excluding ",
        "maximum of",
    )

    for opt in parsed:
        conds = " | ".join(getattr(opt, "conditionals", []) or []).lower()
        if any(m in conds for m in hard_conditional_markers):
            return "Partial", "Parsed, but has constraints we don’t fully enforce yet (dynamic per-equipped-item limits, exclusions, etc.)."

        item_max = getattr(getattr(opt, "item_quantity", None), "max", 1)
        if item_max and int(item_max) > 1:
            return "Partial", "Parsed, but option allows selecting multiple items (needs UI/selection + enforcement)."

        # If there are multiple choices, ensure each choice is uniquely selectable by at least one item name.
        # This matters for our current selection mechanism (apply_wargear_options(name)).
        choices = list(getattr(opt, "wargear_to", []) or [])
        if len(choices) > 1:
            sets = []
            for c in choices:
                sets.append({(str(nm or "").lower().strip()) for qty, nm in (c or []) if nm})
            # If every choice has at least one item not present in every other choice, selection-by-name is unambiguous.
            for i, s in enumerate(sets):
                others = set().union(*[sets[j] for j in range(len(sets)) if j != i]) if len(sets) > 1 else set()
                if not (s - others):
                    return "Partial", "Parsed, but choices share items (selection-by-wargear-name can be ambiguous without extra UI context)."

    return "Supported", "Parsed and choices are selectable/applicable with current mechanisms (best-effort)."


@dataclass(frozen=True)
class OptionRow:
    datasheet_id: str
    datasheet_name: str
    description: str


@dataclass(frozen=True)
class PatternGroup:
    key: str
    count: int
    supported_count: int
    partial_count: int
    not_impl_count: int
    examples: Tuple[str, ...]
    status: str
    notes: str


def main() -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    waha = WahaHelper(data_dir=os.path.join(ROOT, "wahapedia_data"))
    opts_path = os.path.join(ROOT, "wahapedia_data", "Datasheets_options.json")
    with open(opts_path, "r", encoding="utf-8") as f:
        options = json.load(f)

    rows: List[OptionRow] = []
    for opt in options:
        ds_id = opt.get("datasheet_id", "")
        ds = waha.datasheets.get(ds_id, {})
        rows.append(
            OptionRow(
                datasheet_id=str(ds_id),
                datasheet_name=str(ds.get("name", "")),
                description=str(opt.get("description", "")),
            )
        )

    groups: Dict[str, List[OptionRow]] = {}
    for r in rows:
        groups.setdefault(_pattern_key(r.description), []).append(r)

    # Cache per-line classification to keep grouping + summary consistent
    status_cache: Dict[str, Tuple[str, str]] = {}
    def _status_for(desc: str) -> Tuple[str, str]:
        if desc not in status_cache:
            status_cache[desc] = _support_for_desc(desc)
        return status_cache[desc]

    pattern_groups: List[PatternGroup] = []
    for key, items in groups.items():
        statuses = [_status_for(s.description)[0] for s in items]
        supported_c = sum(1 for s in statuses if s == "Supported")
        partial_c = sum(1 for s in statuses if s == "Partial")
        not_impl_c = sum(1 for s in statuses if s == "Not implemented")

        # Dominant status for readability, but we also print the breakdown columns.
        if supported_c >= partial_c and supported_c >= not_impl_c:
            status = "Supported"
        elif partial_c >= not_impl_c:
            status = "Partial"
        else:
            status = "Not implemented"

        notes = f"Breakdown: Supported={supported_c}, Partial={partial_c}, Not implemented={not_impl_c}."

        examples = tuple(
            f"{it.datasheet_name} (`{it.datasheet_id}`): {_canonicalize(it.description)[:140]}{'…' if len(_canonicalize(it.description)) > 140 else ''}"
            for it in sorted(items, key=lambda x: (x.datasheet_name.lower(), x.datasheet_id))[:3]
        )
        pattern_groups.append(
            PatternGroup(
                key=key,
                count=len(items),
                supported_count=supported_c,
                partial_count=partial_c,
                not_impl_count=not_impl_c,
                examples=examples,
                status=status,
                notes=notes,
            )
        )

    pattern_groups.sort(key=lambda pg: (-pg.count, pg.key.lower()))

    total = len(rows)
    supported_n = sum(1 for r in rows if _status_for(r.description)[0] == "Supported")
    partial_n = sum(1 for r in rows if _status_for(r.description)[0] == "Partial")
    not_impl_n = total - supported_n - partial_n

    lines: List[str] = []
    lines.append("# Optional wargear support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/Datasheets_options.json` (optional wargear allowances/replacements).")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append("- **Green**: Supported")
    lines.append("- **Yellow**: Partial")
    lines.append("- **Red**: Not implemented")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Option lines: {total}")
    lines.append(f"- Supported (parser + simple apply): {supported_n}")
    lines.append(f"- Partial (parsed, but constraints not fully enforced): {partial_n}")
    lines.append(f"- Not implemented (unparsed): {not_impl_n}")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("<table>")
    lines.append("<thead>")
    lines.append("<tr>")
    lines.append("<th>Canonical pattern</th>")
    lines.append("<th>Status</th>")
    lines.append("<th>Count</th>")
    lines.append("<th>Supported</th>")
    lines.append("<th>Partial</th>")
    lines.append("<th>Not implemented</th>")
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
        lines.append(f"<td bgcolor=\"{bg}\">{pg.supported_count}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{pg.partial_count}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{pg.not_impl_count}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{ex}</td>")
        lines.append(f"<td bgcolor=\"{bg}\">{_escape_html(pg.notes)}</td>")
        lines.append("</tr>")

    lines.append("</tbody>")
    lines.append("</table>")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Many options include unit-wide constraints (e.g. “cannot select the same weapon more than once per unit”). These are reported as **Partial** until enforced in UI/validation.")
    lines.append("- This matrix is pattern-based; a single datasheet may contain multiple option lines across different patterns.")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    print(f"Wrote {OUT_PATH} ({len(pattern_groups)} pattern groups; {total} option lines).")


if __name__ == "__main__":
    main()

