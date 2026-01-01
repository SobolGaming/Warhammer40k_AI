"""
Generate docs/ABILITY_SUPPORT_MATRIX.md from Wahapedia JSON.

This mirrors the high-level structure of STRATAGEM_SUPPORT_MATRIX.md:
- Core abilities (global Abilities.json entries)
- Faction abilities (Abilities.json entries, grouped per faction)
- Detachment abilities (Detachment_abilities.json, grouped per faction -> detachment)
- Datasheet-sourced abilities (Datasheets_abilities.json rows without ability_id),
  grouped by Datasheets_abilities.type ("Datasheet", "Wargear", "Wargear profile", etc.)

Support status is inferred from currently-implemented engine mechanics (pattern-based).

Exclusions:
- Detachments with `type == "Boarding Actions"` (from `wahapedia_data/Detachments.json`) are excluded from reporting
  for Detachment abilities.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "ABILITY_SUPPORT_MATRIX.md")


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _escape_md(text: str) -> str:
    return (text or "").replace("|", r"\|").strip()


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _strip_html_fast(text: str) -> str:
    """
    We keep this intentionally simple:
    - Remove tags
    - Collapse whitespace
    This is *only* used for pattern matching, not for rendering.
    """
    if not text:
        return ""
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize special apostrophe from Wahapedia
    text = text.replace("’", "'")
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class AbilityEntry:
    id: str
    name: str
    faction_id: str
    description: str
    legend: str


@dataclass(frozen=True)
class DetachmentAbilityEntry:
    id: str
    faction_id: str
    detachment: str
    detachment_id: str
    name: str
    description: str
    legend: str


@dataclass(frozen=True)
class DatasheetInfo:
    id: str
    name: str
    faction_id: str


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


def _load_datasheets() -> Dict[str, DatasheetInfo]:
    path = os.path.join(WAHA_DIR, "Datasheets.json")
    raw = _read_json(path)
    out: Dict[str, DatasheetInfo] = {}
    for ds in raw:
        did = ds.get("id", "") or ""
        if not did:
            continue
        out[did] = DatasheetInfo(
            id=did,
            name=ds.get("name", "") or did,
            faction_id=ds.get("faction_id", "") or "",
        )
    return out


def _load_abilities() -> List[AbilityEntry]:
    path = os.path.join(WAHA_DIR, "Abilities.json")
    raw = _read_json(path)
    out: List[AbilityEntry] = []
    for a in raw:
        out.append(
            AbilityEntry(
                id=a.get("id", "") or "",
                name=a.get("name", "") or "",
                faction_id=a.get("faction_id", "") or "",
                description=a.get("description", "") or "",
                legend=a.get("legend", "") or "",
            )
        )
    return out


def _load_detachment_abilities() -> List[DetachmentAbilityEntry]:
    path = os.path.join(WAHA_DIR, "Detachment_abilities.json")
    raw = _read_json(path)
    out: List[DetachmentAbilityEntry] = []
    for a in raw:
        out.append(
            DetachmentAbilityEntry(
                id=a.get("id", "") or "",
                faction_id=a.get("faction_id", "") or "",
                detachment=a.get("detachment", "") or "",
                detachment_id=a.get("detachment_id", "") or "",
                name=a.get("name", "") or "",
                description=a.get("description", "") or "",
                legend=a.get("legend", "") or "",
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


def _load_datasheets_abilities_rows() -> List[dict]:
    path = os.path.join(WAHA_DIR, "Datasheets_abilities.json")
    return _read_json(path)


def _load_datasheets_detachment_abilities_rows() -> List[dict]:
    path = os.path.join(WAHA_DIR, "Datasheets_detachment_abilities.json")
    return _read_json(path)


def _ability_patterns() -> List[Tuple[str, str, str]]:
    """
    Returns list of (label, status, regex) where status is Supported/Partial.
    These are intentionally conservative, matching existing engine behavior.
    """
    return [
        ("Supreme Commander (must be Warlord)", "Supported", r"\bsupreme commander\b"),
        ("Blessings of Khorne (World Eaters)", "Supported", r"\bblessings of khorne\b"),
        ("Favoured of Khorne (Blessings rerolls)", "Supported", r"\bfavoured of khorne\b|\bfavored of khorne\b"),
        ("Idol of the Blessed Blood (Blessings +1D6)", "Supported", r"\bidol of (?:the )?blessed blood\b"),
        ("Reborn in Blood (Angron)", "Supported", r"\breborn in blood\b"),
        ("Deep Strike", "Supported", r"\bdeep strike\b"),
        ("Infiltrators", "Supported", r"\binfiltrator"),
        ("Scouts", "Supported", r"\bscouts?\b"),
        ("Stealth", "Supported", r"\bstealth\b"),
        ("Lone Operative", "Supported", r"\blone operative\b"),
        ("Deadly Demise", "Supported", r"\bdeadly demise\b"),
        ("Feel No Pain", "Supported", r"\bfeel no pain\b"),
        ("Fights First", "Supported", r"\bfights first\b"),
        ("Fight on Death", "Supported", r"\bfight(s)? on death\b"),
        ("Shoot on Death", "Supported", r"\bshoot(s)? on death\b"),
        ("Redeploy", "Supported", r"\bredeploy\b|\bremove (this|that) unit from the battlefield\b"),
        ("Advance+Shoot (exact wording)", "Supported", r"\beligible to shoot\b.*\badvance(d)?\b"),
        ("Fall Back+Shoot (exact wording)", "Supported", r"\beligible to shoot\b.*\bfell back\b"),
        ("Advance+Charge (exact wording)", "Supported", r"\beligible to declare a charge\b.*\badvance(d)?\b"),
        ("Firing Deck", "Supported", r"\bfiring deck\b"),
        ("Gain CP on destroy (partial)", "Partial", r"\bgain (?:\d+|one)\s*command point|\bgain\s*cp\b"),
        ("Heal on destroy (partial)", "Partial", r"\bregain\b.*\bwounds?\b"),
        ("Plunging Fire", "Supported", r"\bplunging fire\b"),
    ]


def _classify_support(name: str, description: str) -> Tuple[str, str]:
    """
    Returns (status, notes) where status is Supported/Partial/Not implemented.
    """
    # Hard-coded known partials (core ability)
    name_u = (name or "").strip().upper()
    if name_u == "LEADER":
        return ("Partial", "Leader data exists, but full Attached allocation/rules enforcement is incomplete.")
    # World Eaters: Blood Tithe is a Khorne Daemonkin detachment mechanic. We have not implemented it yet,
    # and we do not want it to be falsely marked as Supported due to shared phrasing with Blessings/other mechanics.
    if name_u == "BLOOD TITHE":
        return ("Not implemented", "World Eaters – Khorne Daemonkin detachment mechanic; not implemented yet.")

    text = _norm(_strip_html_fast(f"{name} {description}"))
    matches: List[Tuple[str, str]] = []
    for label, status, rx in _ability_patterns():
        if re.search(rx, text, flags=re.IGNORECASE):
            matches.append((label, status))

    if not matches:
        return ("Not implemented", "")

    # If any partial match triggers, mark Partial; otherwise Supported
    status = "Supported" if all(s == "Supported" for _, s in matches) else "Partial"
    notes = ", ".join(sorted({label for label, _ in matches}, key=str.lower))
    return (status, notes)


def _write_md(
    abilities: List[AbilityEntry],
    detachment_abilities: List[DetachmentAbilityEntry],
    ds_map: Dict[str, DatasheetInfo],
    factions: Dict[str, Dict[str, str]],
    ds_abilities_rows: List[dict],
    ds_detachment_rows: List[dict],
) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)

    # ---- Build reference counts for Abilities.json abilities (via Datasheets_abilities ability_id) ----
    # We track:
    # - totals by (ability_id, type) for Core/global summary tables
    # - per-faction counts by (ability_id, type, faction_id) for faction sections
    ability_refs_rows: Dict[Tuple[str, str], int] = {}  # (ability_id, type) -> count (all factions)
    ability_refs_datasheets: Dict[Tuple[str, str], set] = {}
    ability_refs_rows_by_faction: Dict[Tuple[str, str, str], int] = {}  # (ability_id, type, faction_id) -> count
    ability_refs_datasheets_by_faction: Dict[Tuple[str, str, str], set] = {}
    for r in ds_abilities_rows:
        aid = (r.get("ability_id") or "").strip()
        typ = (r.get("type") or "").strip()
        dsid = (r.get("datasheet_id") or "").strip()
        if not aid:
            continue
        fid = (ds_map.get(dsid).faction_id if dsid in ds_map else "") or "Unknown"
        key = (aid, typ)
        ability_refs_rows[key] = ability_refs_rows.get(key, 0) + 1
        ability_refs_datasheets.setdefault(key, set()).add(dsid)
        kf = (aid, typ, fid)
        ability_refs_rows_by_faction[kf] = ability_refs_rows_by_faction.get(kf, 0) + 1
        ability_refs_datasheets_by_faction.setdefault(kf, set()).add(dsid)

    # ---- Core abilities (Abilities.json with faction_id == "") ----
    core_abilities = [a for a in abilities if not (a.faction_id or "").strip()]
    # de-dup core by id (Abilities.json may include duplicates; we keep first)
    core_by_id: Dict[str, AbilityEntry] = {}
    for a in core_abilities:
        core_by_id.setdefault(a.id, a)
    core_list = list(core_by_id.values())

    # ---- Faction abilities (Abilities.json with faction_id != "") ----
    faction_abilities = [a for a in abilities if (a.faction_id or "").strip()]
    by_faction: Dict[str, List[AbilityEntry]] = {}
    for a in faction_abilities:
        by_faction.setdefault(a.faction_id, []).append(a)

    # ---- Detachment abilities refs (Datasheets_detachment_abilities) ----
    det_refs_rows: Dict[str, int] = {}
    det_refs_datasheets: Dict[str, set] = {}
    for r in ds_detachment_rows:
        did = (r.get("detachment_ability_id") or "").strip()
        dsid = (r.get("datasheet_id") or "").strip()
        if not did:
            continue
        det_refs_rows[did] = det_refs_rows.get(did, 0) + 1
        det_refs_datasheets.setdefault(did, set()).add(dsid)

    det_by_faction: Dict[str, Dict[str, List[DetachmentAbilityEntry]]] = {}
    for da in detachment_abilities:
        det_by_faction.setdefault(da.faction_id, {}).setdefault(da.detachment or "General", []).append(da)

    # ---- Datasheet-sourced abilities (Datasheets_abilities rows without ability_id) ----
    # Group by (type -> faction -> ability_name) with occurrence counts.
    custom_index: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
    for r in ds_abilities_rows:
        aid = (r.get("ability_id") or "").strip()
        if aid:
            continue
        typ = (r.get("type") or "").strip() or "Unknown"
        name = (r.get("name") or "").strip() or "(Unnamed)"
        dsid = (r.get("datasheet_id") or "").strip()
        ds = ds_map.get(dsid)
        fid = (ds.faction_id if ds else "") or "Unknown"
        bucket = custom_index.setdefault(typ, {}).setdefault(fid, {}).setdefault(
            name,
            {
                "rows": 0,
                "datasheets": set(),
                "descriptions": [],  # keep a few samples for classification/notes
            },
        )
        bucket["rows"] += 1
        if dsid:
            bucket["datasheets"].add(dsid)
        desc = (r.get("description") or "").strip()
        if desc and len(bucket["descriptions"]) < 3:
            bucket["descriptions"].append(desc)

    # ---- Summary stats ----
    ds_types_count: Dict[str, int] = {}
    for r in ds_abilities_rows:
        t = (r.get("type") or "").strip() or "Unknown"
        ds_types_count[t] = ds_types_count.get(t, 0) + 1

    # ---- Helpers for output ----
    def faction_name(fid: str) -> str:
        return (factions.get(fid) or {}).get("name") or fid or "Unknown"

    def faction_link(fid: str) -> str:
        return (factions.get(fid) or {}).get("link") or ""

    # ---- Write markdown ----
    lines: List[str] = []
    lines.append("# Ability support matrix (Wahapedia)")
    lines.append("")
    lines.append(
        "Generated from `wahapedia_data/Abilities.json`, `wahapedia_data/Datasheets_abilities.json`, "
        "`wahapedia_data/Detachment_abilities.json`, and `wahapedia_data/Datasheets_detachment_abilities.json` "
        "(faction names/links from `wahapedia_data/Factions.json`)."
    )
    lines.append("")
    lines.append("**Definition of status**")
    lines.append("- **Supported**: the engine recognizes and applies this mechanic (typically pattern-based).")
    lines.append("- **Partial**: some support exists, but key restrictions/timing/text are not fully matched.")
    lines.append("- **Not implemented**: no gameplay effect logic wired yet.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Abilities.json rows: {len(abilities)} (core: {len(core_list)}, faction-specific: {len(faction_abilities)})")
    lines.append(f"- Detachment_abilities.json rows: {len(detachment_abilities)}")
    lines.append(f"- Datasheets_abilities.json rows: {len(ds_abilities_rows)}")
    lines.append("")
    lines.append("### Datasheet ability row types (from `Datasheets_abilities.json`)")
    lines.append("")
    lines.append("| Type | Rows |")
    lines.append("|---|---:|")
    for t, n in sorted(ds_types_count.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        lines.append(f"| {_escape_md(t)} | {n} |")
    lines.append("")
    lines.append("## Recognized mechanics (pattern-based)")
    lines.append("")
    lines.append("These mechanics are currently recognized by searching ability names/descriptions for text patterns:")
    lines.append("")
    for label, status, _ in _ability_patterns():
        lines.append(f"- {label} ({status})")
    lines.append("")

    # ---- Core abilities ----
    lines.append("## Core Abilities")
    lines.append("")
    lines.append("| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |")
    lines.append("|---|---:|---:|---:|---|---|")
    for a in sorted(core_list, key=lambda x: (_norm(x.name), x.id)):
        status, notes = _classify_support(a.name, a.description)
        ref_rows = ability_refs_rows.get((a.id, "Core"), 0)
        ref_ds = len(ability_refs_datasheets.get((a.id, "Core"), set()))
        # Keep the matrix focused on abilities that are actually referenced by datasheets.
        if ref_rows == 0 and ref_ds == 0:
            continue
        lines.append(
            f"| {_escape_md(a.name)} | `{_escape_md(a.id)}` | {ref_rows} | {ref_ds} | **{status}** | {_escape_md(notes)} |"
        )
    lines.append("")

    # ---- Faction abilities ----
    lines.append("## Faction Abilities")
    lines.append("")
    for fid in sorted(by_faction.keys(), key=lambda x: faction_name(x).lower()):
        fname = faction_name(fid)
        flink = faction_link(fid)
        header = f"### {fname} (`{fid}`)"
        if flink:
            header += f" — `{_escape_md(flink)}`"
        lines.append(header)
        lines.append("")
        lines.append("| Ability | Ability ID | Datasheet refs (rows) | Datasheets | Status | Notes |")
        lines.append("|---|---:|---:|---:|---|---|")
        # Deduplicate by (id, name) within faction
        seen = set()
        items = []
        for a in by_faction[fid]:
            k = (a.id, a.name)
            if k in seen:
                continue
            seen.add(k)
            items.append(a)
        for a in sorted(items, key=lambda x: (_norm(x.name), x.id)):
            status, notes = _classify_support(a.name, a.description)
            ref_rows = ability_refs_rows_by_faction.get((a.id, "Faction", fid), 0)
            ref_ds = len(ability_refs_datasheets_by_faction.get((a.id, "Faction", fid), set()))
            # Keep the matrix focused on abilities that are actually referenced by datasheets.
            if ref_rows == 0 and ref_ds == 0:
                continue
            lines.append(
                f"| {_escape_md(a.name)} | `{_escape_md(a.id)}` | {ref_rows} | {ref_ds} | **{status}** | {_escape_md(notes)} |"
            )
        lines.append("")

    # ---- Detachment abilities ----
    lines.append("## Detachment Abilities")
    lines.append("")
    for fid in sorted(det_by_faction.keys(), key=lambda x: faction_name(x).lower()):
        fname = faction_name(fid)
        flink = faction_link(fid)
        header = f"### {fname} (`{fid}`)"
        if flink:
            header += f" — `{_escape_md(flink)}`"
        lines.append(header)
        lines.append("")
        for det_name in sorted(det_by_faction[fid].keys(), key=lambda s: (s or "").lower()):
            lines.append(f"#### {det_name}")
            lines.append("")
            lines.append("| Ability | ID | Datasheet refs (rows) | Datasheets | Status | Notes |")
            lines.append("|---|---:|---:|---:|---|---|")
            for da in sorted(det_by_faction[fid][det_name], key=lambda x: (_norm(x.name), x.id)):
                status, notes = _classify_support(da.name, da.description)
                ref_rows = det_refs_rows.get(da.id, 0)
                ref_ds = len(det_refs_datasheets.get(da.id, set()))
                # Keep the matrix focused on detachment abilities that are actually referenced by datasheets.
                # (This also drops Wahapedia artefacts like "KEYWORDS" rows that are not linked to datasheets.)
                if ref_rows == 0 and ref_ds == 0:
                    continue
                lines.append(
                    f"| {_escape_md(da.name)} | `{_escape_md(da.id)}` | {ref_rows} | {ref_ds} | **{status}** | {_escape_md(notes)} |"
                )
            lines.append("")

    # ---- Datasheet-sourced abilities (no ability_id) ----
    lines.append("## Datasheet-sourced Abilities (no `ability_id`)")
    lines.append("")
    lines.append(
        "These come directly from `Datasheets_abilities.json` rows where `ability_id` is empty (per-datasheet named rules). "
        "They are grouped by the row `type` field (e.g. Datasheet/Wargear/Wargear profile/Special/etc.)."
    )
    lines.append("")

    for typ in sorted(custom_index.keys(), key=lambda s: s.lower()):
        lines.append(f"### {typ}")
        lines.append("")
        for fid in sorted(custom_index[typ].keys(), key=lambda x: faction_name(x).lower()):
            fname = faction_name(fid)
            lines.append(f"#### {fname} (`{fid}`)")
            lines.append("")
            lines.append("| Ability | Occurrences (rows) | Datasheets | Status | Notes |")
            lines.append("|---|---:|---:|---|---|")
            items = custom_index[typ][fid]

            def _row_sort(kv: Tuple[str, Dict[str, Any]]) -> Tuple[int, str]:
                name, meta = kv
                return (-int(meta.get("rows", 0)), _norm(name))

            for name, meta in sorted(items.items(), key=_row_sort):
                # Use up to 3 description samples for classification matching
                sample_desc = " ".join(meta.get("descriptions") or [])
                status, notes = _classify_support(name, sample_desc)
                lines.append(
                    f"| {_escape_md(name)} | {int(meta.get('rows', 0))} | {len(meta.get('datasheets', set()))} | **{status}** | {_escape_md(notes)} |"
                )
            lines.append("")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> None:
    if not os.path.exists(WAHA_DIR):
        raise SystemExit(f"wahapedia_data dir not found at: {WAHA_DIR}")

    factions = _load_factions()
    ds_map = _load_datasheets()
    abilities = _load_abilities()
    detachment_abilities = _load_detachment_abilities()
    ds_abilities_rows = _load_datasheets_abilities_rows()
    ds_detachment_rows = _load_datasheets_detachment_abilities_rows()

    # Exclude Boarding Actions detachments entirely from detachment-ability reporting.
    ba_ids = _load_boarding_actions_detachment_ids()
    if ba_ids:
        detachment_abilities = [a for a in detachment_abilities if (a.detachment_id or "").strip() not in ba_ids]
        allowed_det_ability_ids = {a.id for a in detachment_abilities}
        ds_detachment_rows = [r for r in ds_detachment_rows if (r.get("detachment_ability_id") or "").strip() in allowed_det_ability_ids]

    _write_md(
        abilities=abilities,
        detachment_abilities=detachment_abilities,
        ds_map=ds_map,
        factions=factions,
        ds_abilities_rows=ds_abilities_rows,
        ds_detachment_rows=ds_detachment_rows,
    )
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

