#!/usr/bin/env python3
"""
Generate a .txt table of unique ability description keys with counts and support status.

Format per line:
 | XXX | Y | ZZZZZ | 
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import generate_ability_support_matrix as gsm


def _normalize_description(text: str) -> str:
    return gsm._strip_html(text or "").lower()


def _status_flag(status: str) -> str:
    key = gsm._norm(status)
    if key in ("supported", "implemented"):
        return "Y"
    if key == "partial":
        return "P"
    return "N"


def _summarize_status(statuses: Iterable[str]) -> str:
    statuses = list(statuses)
    total = len(statuses)
    if total == 0:
        return "N"
    supported = sum(1 for s in statuses if gsm._status_is_supported(s))
    partial = sum(1 for s in statuses if gsm._norm(s) == "partial")
    not_impl = total - supported - partial
    if supported == total and partial == 0:
        return "Y"
    if supported == 0 and partial == 0 and not_impl == total:
        return "N"
    return "P"


def _load_data() -> dict:
    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    det_abilities_rows = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    ds_abilities_rows = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Datasheets_abilities.json"))
    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    detachments = gsm._load_detachments()
    sources = gsm._load_sources()
    ds_map = gsm._build_datasheet_map(sources)

    virtual_datasheet_ids = {dsid for dsid, ds in ds_map.items() if gsm._is_virtual_datasheet(ds)}
    virtual_unit_names = {
        ds.get("name", "") or ""
        for dsid, ds in ds_map.items()
        if dsid in virtual_datasheet_ids
    }

    abilities_by_id = {str(a.get("id", "") or ""): a for a in abilities if a.get("id")}

    det_abilities_by_det: Dict[str, List[dict]] = {}
    for row in det_abilities_rows:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        det_abilities_by_det.setdefault(det_id, []).append(row)

    enh_by_det: Dict[str, List[dict]] = {}
    for row in enhancements:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        enh_by_det.setdefault(det_id, []).append(row)

    strats_by_det: Dict[str, List[dict]] = {}
    for row in stratagems:
        det_id = str(row.get("detachment_id", "") or "").strip()
        if not det_id:
            continue
        ttype = (row.get("type", "") or "").strip().lower()
        if "boarding" in ttype or "challenger" in ttype:
            continue
        strats_by_det.setdefault(det_id, []).append(row)

    datasheet_abilities_by_faction: Dict[str, Dict[Tuple[str, ...], dict]] = {}
    for row in ds_abilities_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        if dsid in virtual_datasheet_ids:
            continue
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in gsm.SUPPORTED_FACTION_IDS:
            continue

        ability_id = str(row.get("ability_id", "") or "").strip()
        entry = abilities_by_id.get(ability_id) if ability_id else None
        name = (entry.get("name", "") if entry else "") or row.get("name", "") or ""
        desc = (entry.get("description", "") if entry else "") or row.get("description", "") or ""
        if not name and not desc:
            continue
        if not name:
            name = "Unnamed ability"

        if ability_id:
            key = ("id", ability_id)
        else:
            key = ("row", gsm._norm(name), gsm._norm(gsm._strip_html(desc)))

        bucket = datasheet_abilities_by_faction.setdefault(fid, {})
        if key not in bucket:
            bucket[key] = {
                "name": name,
                "description": desc,
                "ability_id": ability_id,
                "units": set(),
                "datasheet_ids": set(),
            }
        bucket[key]["units"].add(ds.get("name", dsid))
        bucket[key]["datasheet_ids"].add(dsid)

    return {
        "abilities": abilities,
        "det_abilities_by_det": det_abilities_by_det,
        "enh_by_det": enh_by_det,
        "strats_by_det": strats_by_det,
        "detachments": detachments,
        "datasheet_abilities_by_faction": datasheet_abilities_by_faction,
        "virtual_unit_names": virtual_unit_names,
    }


def _iter_faction_ability_entries(data: dict) -> Iterable[Tuple[str, str]]:
    abilities = data["abilities"]
    det_abilities_by_det = data["det_abilities_by_det"]
    enh_by_det = data["enh_by_det"]
    strats_by_det = data["strats_by_det"]
    detachments = data["detachments"]
    datasheet_abilities_by_faction = data["datasheet_abilities_by_faction"]
    virtual_unit_names = data["virtual_unit_names"]

    for faction_id, meta in gsm.FACTION_RULE_METADATA.items():
        fid = str(faction_id or "").strip().upper()
        if fid not in gsm.SUPPORTED_FACTION_IDS:
            continue

        # Army rules
        for rule_name in list(meta.get("army_rules", []) or []):
            entry = gsm._ability_entry_by_name(abilities, rule_name, faction_id=fid)
            desc = entry.get("description", "") if entry else ""
            ability_id = str(entry.get("id", "") or "") if entry else ""
            status, _notes = gsm._classify_ability(rule_name, desc, ability_id=ability_id, faction_id=fid)
            yield desc, status

        # Mustering restrictions
        for restriction in list(meta.get("restrictions", []) or []):
            entry = gsm._ability_entry_by_name(abilities, restriction, faction_id=fid)
            if entry:
                desc = entry.get("description", "") or ""
            else:
                desc = gsm._restriction_rule_and_engine(restriction, abilities, fid)[0]
            status, _notes = gsm._classify_ability(restriction, "", faction_id=fid)
            yield desc, status

        # Detachments
        dets = [
            d for d in detachments.values()
            if str(d.get("faction_id", "") or "").strip().upper() == fid
            and not gsm._detachment_is_boarding(d)
        ]
        for det in dets:
            det_id = str(det.get("id", "") or "").strip()
            det_name = str(det.get("name", "") or "Detachment")

            det_restrictions: List[str] = []
            for ability in det_abilities_by_det.get(det_id, []):
                name = ability.get("name", "") or ""
                desc = ability.get("description", "") or ""
                ability_id = str(ability.get("id", "") or "")
                status, _notes = gsm._classify_ability(name, desc, ability_id=ability_id, faction_id=fid)
                yield desc, status
                det_restrictions.extend(gsm._extract_restrictions(desc))

            det_restrictions = sorted({r for r in det_restrictions if r}, key=str.lower)
            if not gsm._detachment_has_restrictions(det_id, det_name):
                det_restrictions = []
            for restriction in det_restrictions:
                entry = gsm._ability_entry_by_name(abilities, restriction, faction_id=fid)
                if entry:
                    desc = entry.get("description", "") or ""
                else:
                    desc = gsm._restriction_rule_and_engine(restriction, abilities, fid)[0]
                status, _notes = gsm._classify_ability(restriction, "", faction_id=fid)
                yield desc, status

            for enh in enh_by_det.get(det_id, []):
                name = enh.get("name", "") or ""
                desc = enh.get("description", "") or ""
                enh_id = str(enh.get("id", "") or "")
                status, _notes = gsm._enhancement_support(name, enh_id, desc)
                yield desc, status

            for strat in strats_by_det.get(det_id, []):
                name = strat.get("name", "") or ""
                desc = strat.get("description", "") or ""
                status, _notes, _why = gsm._stratagem_support(name)
                yield desc, status

        # Datasheet abilities
        ability_entries = list(datasheet_abilities_by_faction.get(fid, {}).values())
        if ability_entries:
            filtered_entries = []
            for entry in ability_entries:
                units = set(entry.get("units") or set())
                if units:
                    kept = {u for u in units if u not in virtual_unit_names}
                    kept = {u for u in kept if not gsm._is_kill_team_unit(u)}
                    if not kept:
                        continue
                    entry = dict(entry)
                    entry["units"] = kept
                filtered_entries.append(entry)
            ability_entries = filtered_entries

        ability_entries.sort(
            key=lambda e: (gsm._norm(e.get("name", "")), gsm._norm(gsm._strip_html(e.get("description", ""))))
        )
        name_variants: Dict[str, set[str]] = {}
        for entry in ability_entries:
            nm = gsm._norm(entry.get("name", "") or "")
            if not nm:
                continue
            desc_norm = gsm._norm(gsm._strip_html(entry.get("description", "")))
            name_variants.setdefault(nm, set()).add(desc_norm)
        ambiguous_names = {nm for nm, descs in name_variants.items() if len(descs) > 1}

        for entry in ability_entries:
            name = entry.get("name", "") or ""
            desc = entry.get("description", "") or ""
            ability_id = str(entry.get("ability_id", "") or "")
            name_norm = gsm._norm(name)
            ds_ids = sorted(
                {str(d or "").strip() for d in (entry.get("datasheet_ids") or set()) if str(d or "").strip()}
            )
            if name_norm and name_norm in ambiguous_names:
                if len(ds_ids) == 1:
                    status, _notes = gsm._classify_ability(
                        name, desc, ability_id=ability_id, faction_id=fid, datasheet_id=ds_ids[0]
                    )
                elif ds_ids:
                    statuses = []
                    for dsid in ds_ids:
                        st, _nt = gsm._classify_ability(
                            name, desc, ability_id=ability_id, faction_id=fid, datasheet_id=dsid
                        )
                        statuses.append(st)
                    if len(set(statuses)) == 1:
                        status = statuses[0]
                    else:
                        status, _notes = gsm._abilities_support_summary(statuses)
                else:
                    status, _notes = gsm._classify_ability(name, desc, ability_id=ability_id, faction_id=fid)
            else:
                status, _notes = gsm._classify_ability(name, desc, ability_id=ability_id, faction_id=fid)
            yield desc, status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a table of unique ability descriptions with counts and support status."
    )
    default_out = os.path.join(gsm.DOCS_DIR, "ability_description_key_table.txt")
    parser.add_argument(
        "-o",
        "--output",
        default=default_out,
        help=f"Output path (default: {default_out})",
    )
    args = parser.parse_args()

    gsm._seed_ability_support_maps(
        gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json")),
        gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json")),
    )
    data = _load_data()

    counts: Dict[str, int] = defaultdict(int)
    statuses_by_key: Dict[str, List[str]] = defaultdict(list)
    for desc, status in _iter_faction_ability_entries(data):
        key = _normalize_description(desc)
        counts[key] += 1
        statuses_by_key[key].append(status)

    rows = []
    for key, count in counts.items():
        flag = _summarize_status(statuses_by_key.get(key, []))
        rows.append((count, key, flag))

    rows.sort(key=lambda r: (-r[0], r[1]))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for count, key, flag in rows:
            f.write(f" | {count:03d} | {flag} | {key} | \n")

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
