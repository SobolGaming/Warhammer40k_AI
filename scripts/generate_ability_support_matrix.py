
"""
Generate docs/ABILITY_SUPPORT_MATRIX.md from Wahapedia JSON.

Output structure:
- Collapsible Core section (core abilities + core stratagems)
- Collapsible per-faction sections:
  * Army rules
  * Mustering restrictions
  * Detachments (each collapsible; abilities + restrictions + enhancements + stratagems)
  * Datasheet abilities (per faction)

Support status is derived from code (managers, explicit support lists, and pattern-based rules).
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WAHA_DIR = os.path.join(ROOT, "wahapedia_data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "ABILITY_SUPPORT_MATRIX.md")
FACTION_DOCS_DIR = os.path.join(DOCS_DIR, "factions")

SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from warhammer40k_ai.utility.faction_rule_metadata import FACTION_RULE_METADATA
from warhammer40k_ai.classes.army import SUPPORTED_FACTION_IDS
from warhammer40k_ai.classes.stratagems import IMPLEMENTED_STRATAGEM_NAMES
from warhammer40k_ai.classes.enhancement_effects import classify_enhancement_support


STATUS_COLORS = {
    "supported": "#e6f4ea",
    "implemented": "#e6f4ea",
    "partial": "#fff4cc",
    "not implemented": "#fdecea",
}

ABILITY_SUPPORT_BY_ID: Dict[str, Tuple[str, str]] = {}
ABILITY_SUPPORT_BY_NAME_FACTION: Dict[Tuple[str, str], Tuple[str, str]] = {}


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _norm(text: str) -> str:
    t = str(text or "").lower()
    t = t.replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("\u2019", "'")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ascii_text(text: str) -> str:
    t = str(text or "")
    t = t.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    return t


def _escape(text: str) -> str:
    return html.escape(_ascii_text(text), quote=True)


def _status_color(status: str) -> str:
    key = _norm(status)
    return STATUS_COLORS.get(key, "#fdecea")

def _status_icon(status: str) -> str:
    key = _norm(status)
    if key in ("supported", "implemented"):
        return ":green_square:"
    if key == "partial":
        return ":yellow_square:"
    return ":red_square:"


def _summary_status(supported: int, total: int) -> str:
    if total <= 0 or supported <= 0:
        return "Not implemented"
    if supported >= total:
        return "Supported"
    return "Partial"


def _summary_icon(supported: int, total: int) -> str:
    return _status_icon(_summary_status(supported, total))


def _status_is_supported(status: str) -> bool:
    return _norm(status) in ("supported", "implemented")


def _format_units(units: Sequence[str]) -> str:
    clean = sorted({u for u in units if u}, key=lambda s: s.lower())
    if not clean:
        return "-"
    if len(clean) > 4:
        body = "<br/>".join(_escape(u) for u in clean)
        return f"<details><summary>{len(clean)} units</summary>{body}</details>"
    return ", ".join(_escape(u) for u in clean)


def _details(summary: str, body: str) -> str:
    return f"<details><summary>{_escape(summary)}</summary>{body}</details>"


def _desc_block(rules_text: str, engine_text: str) -> str:
    rules = _escape(rules_text or "-")
    engine = _escape(engine_text or "-")
    body = f"<strong>Rules:</strong> {rules}<br/><strong>Engine:</strong> {engine}"
    return _details("Description", body)

def _engine_block(engine_text: str) -> str:
    engine = _escape(engine_text or "-")
    body = f"<strong>Engine:</strong> {engine}"
    return _details("Description", body)

def _ability_id_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Acts of Faith": ("Supported", "Miracle dice pool with per-phase Act usage and substitution tracking."),
        "Martial Ka'tah": ("Supported", "Fight-phase Ka'tah selection with Lethal/Sustained hit hooks."),
        "Doctrina Imperatives": ("Supported", "Round-based imperatives with WS/BS/AP/heavy/assault modifiers."),
        "Voice of Command": ("Supported", "Order issuing in Command phase with stat modifiers."),
        "Gate of Infinity": ("Supported", "Teleport eligible units with placement validation."),
        "Assigned Agents": ("Supported", "Imperial Agents ally caps enforced by battle size."),
        "Code Chivalric": ("Supported", "Deed/Quality tracking with on-roll effects."),
        "Bondsman": ("Supported", "Bondsman buffs applied to Armiger units."),
        "Super-heavy Walker": ("Partial", "Terrain traversal handling only."),
        "Battle Focus": ("Supported", "Token system + maneuver selection with per-phase limits."),
        "Power from Pain": ("Partial", "Pain token engine with partial ability coverage."),
        "Cult Ambush": ("Supported", "Resurgence points, ambush markers, reinforcements."),
        "Prioritised Efficiency": ("Supported", "Yield points + mode tracking with objective checks."),
        "Reanimation Protocols": ("Supported", "Command-phase reanimation sequencing for Necrons."),
        "Waaagh!": ("Supported", "Once-per-battle Waaagh effects tracked and applied."),
        "For the Greater Good": ("Supported", "Observer/Guided targeting with markerlight bonuses."),
        "Synapse": ("Supported", "Synapse aura checks via distance rules."),
        "Shadow in the Warp": ("Supported", "Once-per-battle armywide Battle-shock trigger."),
        "The Shadow of Chaos": ("Supported", "Shadow zones + manifestations/terror handling."),
        "Harbingers of Dread": ("Supported", "Dread ability selection and aura checks."),
        "Dark Pacts": ("Supported", "Dark Pacts selection with lethal/sustained hooks."),
        "Nurgle's Gift (Aura)": ("Supported", "Contagion range + plague effects."),
        "Thrill Seekers": ("Supported", "EC core rule hooks for crits and movement bonuses."),
        "Pact of Decay": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Excess": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Sorcery": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Blood": ("Supported", "Army faction restriction enforced during validation."),
        "Cabal of Sorcerers": ("Supported", "Cabal rituals and warp charge checks."),
        "Blessings of Khorne": ("Supported", "Blessings dice engine + effects."),
        "Oath of Moment": ("Supported", "Target selection + hit/wound bonuses."),
        "Templar Vows": ("Supported", "Vow selection with combat/objective effects."),
        "Leader": ("Supported", "Attach Leaders during battle formations; protect Characters until Bodyguard is gone."),
        "Deep Strike": ("Supported", "Reserves placement in Reinforcements step; enforces >9\" distance."),
        "Feel No Pain": ("Supported", "Post-damage roll to ignore wounds, including mortals."),
        "Fights First": ("Supported", "Fight phase sequencing uses Fights First step."),
        "Fight on Death": ("Supported", "Destroyed units can fight after attacker resolves."),
        "Shoot on Death": ("Supported", "Destroyed units can shoot after attacker resolves."),
        "Firing Deck": ("Supported", "Transports fire with selected embarked weapons; marks passengers as shot."),
        "Infiltrators": ("Supported", "Forward deploy placement >9\" from enemy zone/models."),
        "Lone Operative": ("Supported", "Ranged targeting blocked beyond 12\" when not Attached."),
        "Scouts": ("Supported", "Pre-game Scout move, including transport use when applicable."),
        "Stealth": ("Supported", "Apply -1 to hit vs ranged attacks."),
        "Deadly Demise": ("Supported", "On destruction, roll 6+ to deal mortals within 6\"."),
        "Plunging Fire": ("Supported", "Extra AP vs targets below attacker elevation."),
        "Hover": ("Not implemented", "No hover-specific handling."),
    }
    return {_norm(name): val for name, val in raw.items()}


def _detachment_ability_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Quicksilver Grace": ("Supported", "Mercurial Host: reroll Advance rolls for eligible units."),
        "Exquisite Swordsmanship": ("Supported", "Peerless Bladesmen: on charge choose Lethal or Sustained for melee."),
        "Mechanised Murder": ("Supported", "Rapid Evisceration: reroll Hit/Wound rolls of 1 for eligible units."),
        "Daemonic Empowerment": ("Supported", "Carnival of Excess: empowered units gain Sustained Hits."),
        "Pledges to the Dark Prince": ("Supported", "Coterie pledges tracked per round; pact points unlock bonuses."),
        "Internal Rivalries": ("Supported", "Slaanesh's Chosen: ignore negative Move/Advance/Charge; Favoured reroll Wounds."),
        "Sensational Performance": ("Supported", "Court of the Phoenician: optional +1 S/AP on charge."),
        "Master of the Pageant": ("Supported", "Court of the Phoenician: once per round -1 CP stratagem cost."),
    }
    return {_norm(name): val for name, val in raw.items()}


def _restriction_support_by_name() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Freeblades": ("Supported", "Imperial Knights ally and detachment restrictions enforced."),
        "Disparate Paths": ("Supported", "Harlequin/Ynnari ally validation in mustering."),
        "Corsairs and Travelling Players": ("Supported", "Corsairs/Travelling Players ally limits enforced."),
        "Daemonic Pact": ("Supported", "Chaos Daemon ally validation with caps and keyword rules."),
        "Dreadblades": ("Supported", "Chaos Knights ally validation and model caps."),
        "Cult of the Dark Gods": ("Supported", "Cult ally points caps and keyword adjustments."),
        "Pact of Decay": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Excess": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Sorcery": ("Supported", "Army faction restriction enforced during validation."),
        "Pact of Blood": ("Supported", "Army faction restriction enforced during validation."),
        "Space Marine Chapters": ("Supported", "Chapter keyword restrictions and unit bans."),
        "Deathwatch": ("Supported", "Deathwatch-only chapter restrictions."),
    }
    return {_norm(name): val for name, val in raw.items()}


def _datasheet_ability_support_global() -> Dict[str, Tuple[str, str]]:
    raw = {
        "Supreme Commander": ("Supported", "If any SUPREME COMMANDER unit is in the army, one must be the Warlord."),
        "One Shot": ("Supported", "Weapon-level one-shot tracking enforced per model."),
        "Super-heavy Walker": ("Partial", "Terrain traversal handling only."),
    }
    return {_norm(name): val for name, val in raw.items()}


def _datasheet_ability_support_by_name_faction() -> Dict[Tuple[str, str], Tuple[str, str]]:
    raw = {
        ("WE", "Reborn in Blood"): ("Partial", "Revive + reserves placement; next Movement phase-only not enforced."),
        ("WE", "Lord of Murder"): ("Supported", "Conditional Lone Operative within 3\" of friendly WORLD EATERS INFANTRY."),
        ("WE", "Beacons of Rage (Aura)"): ("Supported", "+1 hit (melee) and +1 wound vs Below Half-strength; excludes Monster/Vehicle."),
        ("WE", "Fire Riders"): ("Partial", "Deep Strike detected; movement/leading-only clauses not enforced."),
        ("WE", "Forwards, for Blood!"): ("Partial", "Advance reroll detected; Blood Surge reroll/leading-only clauses not enforced."),
        ("WE", "Bloody Fury"): ("Partial", "Charge reroll detected; closest-target/ranged reroll clauses not enforced."),
        ("WE", "To Slake its Rage"): ("Supported", "Advance-and-charge eligibility."),
        ("WE", "Idol of Blessed Blood"): ("Supported", "Adds an extra Blessings die for each on-battlefield model with this ability."),
        ("WE", "Murderlust"): ("Supported", "Advance-and-charge eligibility."),
        ("WE", "Collar of Khorne"): ("Supported", "Feel No Pain 3+ against Psychic attacks."),
        ("WE", "Possessed Lord"): ("Supported", "Once-per-battle Fight phase: +3 Attacks and Devastating Wounds."),
        ("WE", "Lord of the Eightbound"): ("Partial", "Deep Strike/Scouts 6\" detected; attachment requirement not enforced."),
        ("WE", "Rage Embodied (Aura)"): ("Supported", "+1 melee Attacks aura within 6\" for BLOOD LEGIONS."),
        ("WE", "Daemon Lord of Khorne (Aura)"): ("Supported", "+1 to hit in melee aura within 6\" for BLOOD LEGIONS."),
        ("CD", "Monarch of the Hunt"): ("Supported", "Quarry selection + melee reroll hooks vs quarry."),
    }
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (fid, name), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name))] = val
    return out


def _datasheet_support_by_name_faction() -> Dict[Tuple[str, str], Tuple[str, str]]:
    """
    Explicit full-datasheet support overrides.
    Use this only when abilities, wargear, points, keywords, damaged profiles,
    and other special sections are all confirmed supported.
    """
    raw: Dict[Tuple[str, str], Tuple[str, str]] = {
        # ("WE", "Angron"): ("Supported", "Full datasheet support verified."),
    }
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (fid, name), val in raw.items():
        out[(str(fid or "").strip().upper(), _norm(name))] = val
    return out

def _seed_ability_support_maps(abilities: List[dict], det_abilities_rows: List[dict]) -> None:
    global ABILITY_SUPPORT_BY_ID, ABILITY_SUPPORT_BY_NAME_FACTION
    ABILITY_SUPPORT_BY_ID = {}
    ABILITY_SUPPORT_BY_NAME_FACTION = {}

    name_to_ids: Dict[str, List[str]] = {}
    for ab in abilities:
        ab_id = str(ab.get("id", "") or "").strip()
        if not ab_id:
            continue
        name_norm = _norm(ab.get("name", "") or "")
        if not name_norm:
            continue
        name_to_ids.setdefault(name_norm, []).append(ab_id)
    for name_norm, val in _ability_id_support_by_name().items():
        for ab_id in name_to_ids.get(name_norm, []):
            ABILITY_SUPPORT_BY_ID[ab_id] = val

    det_name_to_ids: Dict[str, List[str]] = {}
    for row in det_abilities_rows:
        det_id = str(row.get("id", "") or "").strip()
        if not det_id:
            continue
        name_norm = _norm(row.get("name", "") or "")
        if not name_norm:
            continue
        det_name_to_ids.setdefault(name_norm, []).append(det_id)
    for name_norm, val in _detachment_ability_support_by_name().items():
        for det_id in det_name_to_ids.get(name_norm, []):
            ABILITY_SUPPORT_BY_ID[det_id] = val

    restriction_support = _restriction_support_by_name()
    for fid, meta in FACTION_RULE_METADATA.items():
        fid_norm = str(fid or "").strip().upper()
        for restriction in list(meta.get("restrictions", []) or []):
            key = _norm(restriction)
            if key in restriction_support:
                ABILITY_SUPPORT_BY_NAME_FACTION[(fid_norm, key)] = restriction_support[key]

    for name_norm, val in _datasheet_ability_support_global().items():
        for fid in SUPPORTED_FACTION_IDS:
            fid_norm = str(fid or "").strip().upper()
            ABILITY_SUPPORT_BY_NAME_FACTION[(fid_norm, name_norm)] = val

    for key, val in _datasheet_ability_support_by_name_faction().items():
        ABILITY_SUPPORT_BY_NAME_FACTION[key] = val


def _classify_ability(name: str, description: str, *, ability_id: str = "", faction_id: str = "") -> Tuple[str, str]:
    ab_id = str(ability_id or "").strip()
    if ab_id:
        return ABILITY_SUPPORT_BY_ID.get(ab_id, ("Not implemented", ""))

    fid = str(faction_id or "").strip().upper()
    name_norm = _norm(name)
    if name_norm and (fid, name_norm) in ABILITY_SUPPORT_BY_NAME_FACTION:
        return ABILITY_SUPPORT_BY_NAME_FACTION[(fid, name_norm)]
    return ("Not implemented", "")


def _datasheet_support_status(
    *,
    faction_id: str,
    datasheet_name: str,
    ability_statuses: Sequence[str],
    overrides: Dict[Tuple[str, str], Tuple[str, str]],
) -> Tuple[str, str]:
    fid = str(faction_id or "").strip().upper()
    key = (fid, _norm(datasheet_name))
    if key in overrides:
        return overrides[key]

    total = len(list(ability_statuses or []))
    supported = sum(1 for s in ability_statuses if _status_is_supported(s))
    partial = sum(1 for s in ability_statuses if _norm(s) == "partial")
    not_impl = total - supported - partial

    base_note = (
        "Wargear/points/keywords/damaged profiles/other sections (e.g., Orders) not audited."
    )

    if total == 0:
        return ("Not implemented", f"No datasheet abilities detected. {base_note}")
    if not_impl == total:
        return ("Not implemented", f"Abilities not implemented ({not_impl}/{total}). {base_note}")
    if supported == total and partial == 0:
        return ("Partial", f"Abilities supported ({supported}/{total}). {base_note}")
    return (
        "Partial",
        f"Abilities: {supported} supported, {partial} partial, {not_impl} not implemented. {base_note}",
    )

def _enhancement_support(name: str, enh_id: str, description: str) -> Tuple[str, str]:
    explicit = {
        "000008432002": "Berzerker Glaive: +1A/+1D to bearer melee weapons (excluding Extra Attacks).",
        "000008432003": "Helm of Brazen Ire: reduce damage by 1 (min 1).",
        "000008432004": "Favoured of Khorne: Blessings rerolls while bearer on battlefield.",
        "000008432005": "Battle-lust: re-roll Charge; +1 Charge with Unbridled Bloodlust.",
        "000009899002": "Phoenix Gem: return on 2+ at end of phase after first destruction.",
        "000009899003": "Timeless Strategist: +1 Battle Focus token if bearer on battlefield.",
        "000009899004": "Gift of Foresight: Command Re-roll for 0CP once per battle round.",
        "000009899005": "Psychic Destroyer: +1 Damage to bearer ranged Psychic weapons.",
    }
    if enh_id in explicit:
        return ("Supported", explicit[enh_id])

    status, notes = classify_enhancement_support(description)
    if status == "Supported":
        return (status, notes)
    return (status, notes)


def _stratagem_support(name: str) -> Tuple[str, str, str]:
    name_u = (name or "").strip().upper()
    notes = {
        "COMMAND RE-ROLL": "Queued on roll; executes reroll callback; once-per-phase rule enforced.",
        "COUNTER-OFFENSIVE": "Fight phase: select a unit to fight next after enemy unit fights.",
        "EPIC CHALLENGE": "Fight phase: selected CHARACTER gains Precision for melee attacks.",
        "FIRE OVERWATCH": "Queued on enemy movement; resolves shooting on 6s to hit.",
        "GO TO GROUND": "Shooting phase: INFANTRY gains cover + 6++ until end of phase.",
        "GRENADE": "Shooting phase: 6D6 vs 4+ for mortal wounds within 8\".",
        "HEROIC INTERVENTION": "Charge phase: select unit to charge after enemy charge ends.",
        "INSANE BRAVERY": "Command phase: auto-pass Battle-shock once per battle.",
        "NEW ORDERS": "Command phase: discard a Secondary and draw a new one.",
        "RAPID INGRESS": "Movement phase: place a reserves unit at end of opponent move.",
        "SMOKESCREEN": "Shooting phase: SMOKE unit gains cover + Stealth.",
        "TANK SHOCK": "Charge phase: roll vs Toughness to deal mortals (max 6).",
        "APOPLECTIC FRENZY": "Advance and Charge for a BERZERKERS unit; Berzerker Warband only.",
        "BLOOD OFFERING": "Sticky objective on unit destruction; Berzerker Warband only.",
        "UNBOUND ARROGANCE": "Coterie of the Conceited pledge increases by 1 (once per battle round).",
    }

    if name_u in IMPLEMENTED_STRATAGEM_NAMES:
        return ("Implemented", notes.get(name_u, "Implemented in engine."), name_u)
    return ("Not implemented", "No effect logic currently wired.", name_u)


def _extract_restrictions(desc_html: str) -> List[str]:
    if not desc_html:
        return []
    text = desc_html
    if "RESTRICTIONS" not in text.upper():
        return []

    m = re.search(r"RESTRICTIONS</span>(.*?)</ul>", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)
        items = re.findall(r"<li[^>]*>(.*?)</li>", block, flags=re.IGNORECASE | re.DOTALL)
        out = []
        for item in items:
            clean = _strip_html(item)
            if clean:
                out.append(clean)
        return out

    # Fallback: strip tags, take lines after RESTRICTIONS
    clean_text = _strip_html(text)
    upper = clean_text.upper()
    idx = upper.find("RESTRICTIONS")
    if idx == -1:
        return []
    after = clean_text[idx + len("RESTRICTIONS") :]
    parts = [p.strip(" -") for p in after.split("\n") if p.strip()]
    return parts


def _row(cells: Sequence[str], status: str) -> str:
    color = _status_color(status)
    tds = "".join(f"<td bgcolor=\"{color}\">{c}</td>" for c in cells)
    return f"<tr>{tds}</tr>"


def _table(headers: Sequence[str], rows: Sequence[Tuple[Sequence[str], str]]) -> str:
    ths = "".join(f"<th>{_escape(h)}</th>" for h in headers)
    body = "".join(_row(cells, status) for cells, status in rows)
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"

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
        out[fid] = {
            "name": item.get("name", "") or fid,
            "link": item.get("link", "") or "",
        }
    return out


def _load_detachments() -> Dict[str, dict]:
    path = os.path.join(WAHA_DIR, "Detachments.json")
    raw = _read_json(path)
    out = {}
    for d in raw:
        did = (d.get("id") or "").strip()
        if not did:
            continue
        out[did] = d
    return out


def _detachment_is_boarding(det: dict) -> bool:
    return str(det.get("type", "") or "").strip().lower() == "boarding actions"


def _build_datasheet_map() -> Dict[str, dict]:
    raw = _read_json(os.path.join(WAHA_DIR, "Datasheets.json"))
    out = {}
    for ds in raw:
        did = ds.get("id", "") or ""
        if not did:
            continue
        out[did] = ds
    return out


def _ability_entry_by_name(abilities: List[dict], name: str, faction_id: Optional[str] = None) -> Optional[dict]:
    target = _norm(name)
    best = None
    for a in abilities:
        if _norm(a.get("name", "")) != target:
            continue
        if faction_id and str(a.get("faction_id", "") or "").strip().upper() != faction_id:
            continue
        best = a
        break
    if best is not None:
        return best
    # Fallback without faction match
    for a in abilities:
        if _norm(a.get("name", "")) == target:
            return a
    return None


def _collect_units_for_ability(
    ability_id: str,
    ds_abilities_rows: List[dict],
    ds_map: Dict[str, dict],
    faction_id: Optional[str] = None,
) -> List[str]:
    names = []
    for r in ds_abilities_rows:
        if str(r.get("ability_id", "") or "").strip() != ability_id:
            continue
        dsid = str(r.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        if faction_id and fid != str(faction_id or "").strip().upper():
            continue
        names.append(ds.get("name", dsid))
    return names


def _collect_units_for_detachment_ability(ability_id: str, ds_det_rows: List[dict], ds_map: Dict[str, dict]) -> List[str]:
    names = []
    for r in ds_det_rows:
        if str(r.get("detachment_ability_id", "") or "").strip() != ability_id:
            continue
        dsid = str(r.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        names.append(ds.get("name", dsid))
    return names


def _summarize_section_count(items: Iterable[Tuple[str, str]]) -> Tuple[int, int]:
    total = 0
    supported = 0
    for status, _name in items:
        total += 1
        if _status_is_supported(status):
            supported += 1
    return supported, total


def _summary_color(supported: int, total: int) -> str:
    if total <= 0:
        return STATUS_COLORS["not implemented"]
    if supported <= 0:
        return STATUS_COLORS["not implemented"]
    if supported >= total:
        return STATUS_COLORS["supported"]
    return STATUS_COLORS["partial"]


def _summary_span(title: str, supported: int, total: int) -> str:
    return _summary_span_with_label(title, supported, total, "abilities")


def _summary_span_with_label(title: str, supported: int, total: int, label: str) -> str:
    color = _summary_color(supported, total)
    label = f"{_escape(title)} ({supported} out of {total} {label} supported)"
    return f"<span style=\"background-color:{color}; padding:2px 6px; display:block;\">{label}</span>"


def _details_raw(summary_html: str, body: str) -> str:
    return f"<details><summary>{summary_html}</summary>\n{body}\n</details>"


def _engine_notes(status: str, notes: str) -> str:
    if notes:
        return notes
    key = _norm(status)
    if key in ("supported", "implemented"):
        return "Implemented in engine."
    if key == "partial":
        return "Partially implemented in engine."
    return "No effect logic wired."


def _slugify(name: str) -> str:
    txt = _ascii_text(name)
    txt = re.sub(r"[^a-zA-Z0-9]+", "_", txt).strip("_").lower()
    return txt or "faction"


def _restriction_rule_and_engine(name: str, abilities: List[dict], faction_id: Optional[str]) -> Tuple[str, str]:
    key = _norm(name)
    ability = _ability_entry_by_name(abilities, name, faction_id=faction_id)
    desc = _strip_html(ability.get("description", "")) if ability else ""
    pact_match = re.search(r"cannot select\s+(.+?)\s+as your army faction", desc, flags=re.IGNORECASE)
    if pact_match:
        forbidden = pact_match.group(1).strip().strip(".")
        return (
            f"Army Faction cannot be {forbidden}.",
            "Validated in army detachment restrictions.",
        )
    rules = {
        "freeblades": (
            "Imperial Knights allies only; army must be IMPERIUM; allied Knights cannot be Warlord or take Enhancements; "
            "max 1 TITANIC or 3 ARMIGER, and cannot mix both.",
            "Validated in Army._validate_freeblades.",
        ),
        "disparate paths": (
            "Allows base faction plus HARLEQUINS/YNNARI; other faction keywords are rejected.",
            "Validated in Army.validate_allies.",
        ),
        "corsairs and travelling players": (
            "Allows DRUKHARI plus HARLEQUINS/ANHRATHE; allied units cannot be Warlord or take Enhancements; "
            "points cap enforced by battle size.",
            "Validated in Army._validate_corsairs_and_travelling_players.",
        ),
        "daemonic pact": (
            "LEGIONES DAEMONICA allies allowed only in CSM/Chaos Knights; allies cannot be Warlord or take Enhancements; "
            "points cap enforced and god non-Battleline cannot exceed Battleline.",
            "Validated in Army._validate_daemonic_pact.",
        ),
        "dreadblades": (
            "Chaos Knights allies: only TITANIC or WAR DOG; cannot mix; max 1 TITANIC or 3 WAR DOG.",
            "Validated in Army.validate_dreadblades.",
        ),
        "cult of the dark gods": (
            "Cult ally points cap enforced; cult units forced to Heretic Astartes keywords.",
            "Validated in Army.validate_cult_of_dark_gods.",
        ),
        "space marine chapters": (
            "All Adeptus Astartes units must share a single Chapter keyword; mixed chapters disallowed.",
            "Validated in Army.validate_space_marine_chapters.",
        ),
        "deathwatch": (
            "Deathwatch armies cannot include non-Deathwatch Astartes or banned units; AoI Deathwatch excluded.",
            "Validated in Army.validate_space_marine_chapters.",
        ),
    }
    if key in rules:
        return rules[key]
    return (desc or name, "Validated in army restrictions.")


def _build_faction_content(
    *,
    faction_id: str,
    meta: dict,
    abilities: List[dict],
    det_abilities_by_det: Dict[str, List[dict]],
    enhancements: List[dict],
    stratagems: List[dict],
    detachments: Dict[str, dict],
    ds_abilities_rows: List[dict],
    datasheet_abilities_by_faction: Dict[str, Dict[Tuple[str, ...], dict]],
    datasheet_abilities_by_datasheet: Dict[str, Dict[Tuple[str, ...], dict]],
    datasheets_by_faction: Dict[str, List[dict]],
    datasheet_support_overrides: Dict[Tuple[str, str], Tuple[str, str]],
) -> Tuple[str, int, int]:
    faction_name = str(meta.get("faction_name", "") or faction_id)
    faction_items: List[Tuple[str, str]] = []
    faction_body: List[str] = []

    # Army rules
    army_rule_rows = []
    for rule_name in list(meta.get("army_rules", []) or []):
        entry = _ability_entry_by_name(abilities, rule_name, faction_id=faction_id)
        desc = entry.get("description", "") if entry else ""
        ability_id = str(entry.get("id", "") or "") if entry else ""
        status, notes = _classify_ability(rule_name, desc, ability_id=ability_id, faction_id=faction_id)
        faction_items.append((status, rule_name))
        army_rule_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(rule_name),
                    _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if army_rule_rows:
        faction_body.append("## Army Rules")
        faction_body.append(_table(["Status", "Army Rule", "Description"], army_rule_rows))
        faction_body.append("")

    # Mustering restrictions
    restriction_rows = []
    for restriction in list(meta.get("restrictions", []) or []):
        status, notes = _classify_ability(restriction, "", faction_id=faction_id)
        rules_text, engine_text = _restriction_rule_and_engine(restriction, abilities, faction_id)
        faction_items.append((status, restriction))
        restriction_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(restriction),
                    _desc_block(rules_text, engine_text or _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if restriction_rows:
        faction_body.append("## Mustering Restrictions")
        faction_body.append(_table(["Status", "Restriction", "Description"], restriction_rows))
        faction_body.append("")

    # Detachments
    dets = [
        d for d in detachments.values()
        if str(d.get("faction_id", "") or "").strip().upper() == faction_id
        and not _detachment_is_boarding(d)
    ]
    dets.sort(key=lambda d: _norm(d.get("name", "")))
    if dets:
        faction_body.append("## Detachments")
        for det in dets:
            det_name = str(det.get("name", "") or "Detachment")
            det_id = str(det.get("id", "") or "").strip()
            det_body: List[str] = []

            # Detachment abilities
            det_ability_rows = []
            det_restrictions: List[str] = []
            for ability in det_abilities_by_det.get(det_id, []):
                name = ability.get("name", "") or ""
                desc = ability.get("description", "") or ""
                ability_id = str(ability.get("id", "") or "")
                status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id=faction_id)
                faction_items.append((status, name))
                det_ability_rows.append(
                    (
                        [
                            _escape(_status_icon(status)),
                            _escape(name),
                            _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                        ],
                        status,
                    )
                )
                det_restrictions.extend(_extract_restrictions(desc))
            if det_ability_rows:
                det_body.append("**Detachment Abilities**")
                det_body.append(_table(["Status", "Ability", "Description"], det_ability_rows))
                det_body.append("")

            det_restrictions = sorted({r for r in det_restrictions if r}, key=str.lower)
            if det_restrictions:
                det_restriction_rows = []
                for restriction in det_restrictions:
                    status, notes = _classify_ability(restriction, "", faction_id=faction_id)
                    rules_text, engine_text = _restriction_rule_and_engine(restriction, abilities, faction_id)
                    faction_items.append((status, restriction))
                    det_restriction_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(restriction),
                                _desc_block(rules_text, engine_text or _engine_notes(status, notes)),
                            ],
                            status,
                        )
                    )
                det_body.append("**Detachment Restrictions**")
                det_body.append(_table(["Status", "Restriction", "Description"], det_restriction_rows))
                det_body.append("")

            # Enhancements
            det_enh = [e for e in enhancements if str(e.get("detachment_id", "") or "").strip() == det_id]
            if det_enh:
                enh_rows = []
                for enh in det_enh:
                    name = enh.get("name", "") or ""
                    desc = enh.get("description", "") or ""
                    enh_id = str(enh.get("id", "") or "")
                    status, notes = _enhancement_support(name, enh_id, desc)
                    enh_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(name),
                                _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                            ],
                            status,
                        )
                    )
                det_body.append("**Enhancements**")
                det_body.append(_table(["Status", "Enhancement", "Description"], enh_rows))
                det_body.append("")

            # Stratagems
            det_strats = []
            for s in stratagems:
                if str(s.get("detachment_id", "") or "").strip() != det_id:
                    continue
                ttype = (s.get("type", "") or "").strip().lower()
                if "boarding" in ttype or "challenger" in ttype:
                    continue
                det_strats.append(s)
            if det_strats:
                det_strats.sort(key=lambda s: _norm(s.get("name", "")))
                strat_rows = []
                for s in det_strats:
                    status, notes, _ = _stratagem_support(s.get("name", ""))
                    strat_rows.append(
                        (
                            [
                                _escape(_status_icon(status)),
                                _escape(s.get("name", "")),
                                f"<code>{_escape(s.get('id', ''))}</code>",
                                _escape(s.get("type", "")),
                                _escape(s.get("cp_cost", "")),
                                _escape(s.get("turn", "")),
                                _escape(s.get("phase", "")),
                                _escape(notes),
                            ],
                            status,
                        )
                    )
                det_body.append("**Stratagems**")
                det_body.append(
                    _table(
                        ["Status", "Stratagem", "ID", "Type", "CP", "Turn", "Phase", "Notes"],
                        strat_rows,
                    )
                )
                det_body.append("")

            if not det_body:
                det_body.append("_No detachment data available._")
            faction_body.append(_details_raw(_escape(det_name), "\n".join(det_body)))
            faction_body.append("")

    # Datasheet abilities
    ds_ability_rows = []
    ability_entries = list(datasheet_abilities_by_faction.get(faction_id, {}).values())
    ability_entries.sort(key=lambda e: (_norm(e.get("name", "")), _norm(_strip_html(e.get("description", "")))))
    for entry in ability_entries:
        name = entry.get("name", "") or ""
        desc = entry.get("description", "") or ""
        ability_id = str(entry.get("ability_id", "") or "")
        status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id=faction_id)
        faction_items.append((status, name))
        units = sorted({u for u in (entry.get("units") or set()) if u}, key=lambda s: s.lower())
        ds_ability_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(name),
                    _format_units(units),
                    _desc_block(_strip_html(desc), _engine_notes(status, notes)),
                ],
                status,
            )
        )
    if ds_ability_rows:
        faction_body.append("## Datasheet Abilities")
        faction_body.append(_table(["Status", "Ability", "Units", "Description"], ds_ability_rows))
        faction_body.append("")

    # Datasheet support summary
    ds_units = list(datasheets_by_faction.get(faction_id, []) or [])
    if ds_units:
        ds_units.sort(key=lambda d: (_norm(d.get("name", "")), str(d.get("id", "") or "")))
        ds_rows = []
        for ds in ds_units:
            dsid = str(ds.get("id", "") or "").strip()
            name = str(ds.get("name", "") or dsid)
            ability_entries = list(datasheet_abilities_by_datasheet.get(dsid, {}).values())
            ability_statuses: List[str] = []
            for entry in ability_entries:
                ab_name = entry.get("name", "") or ""
                ab_desc = entry.get("description", "") or ""
                ab_id = str(entry.get("ability_id", "") or "")
                ab_status, _ab_notes = _classify_ability(ab_name, ab_desc, ability_id=ab_id, faction_id=faction_id)
                ability_statuses.append(ab_status)

            status, note = _datasheet_support_status(
                faction_id=faction_id,
                datasheet_name=name,
                ability_statuses=ability_statuses,
                overrides=datasheet_support_overrides,
            )
            ds_rows.append(
                (
                    [
                        _escape(_status_icon(status)),
                        _escape(name),
                        _escape(note),
                    ],
                    status,
                )
            )
        faction_body.append("## Datasheets")
        faction_body.append(_table(["Status", "Unit", "Notes"], ds_rows))
        faction_body.append("")

    supported, total = _summarize_section_count(faction_items)
    header = [
        f"# {faction_name} Ability Support",
        "",
        "Generated from `wahapedia_data/*.json` using `scripts/generate_ability_support_matrix.py`.",
        "",
        f"Back to [Ability Support Matrix](../ABILITY_SUPPORT_MATRIX.md).",
        "",
        "## Legend",
        _table(
            ["Status", "Meaning"],
            [
                ([_escape(_status_icon("supported")), "Implemented in engine."], "Supported"),
                ([_escape(_status_icon("partial")), "Partially implemented in engine."], "Partial"),
                ([_escape(_status_icon("not implemented")), "Not implemented."], "Not implemented"),
            ],
        ),
        "",
    ]
    return "\n".join(header + faction_body).rstrip() + "\n", supported, total


def _build_matrix() -> str:
    abilities = _read_json(os.path.join(WAHA_DIR, "Abilities.json"))
    det_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Detachment_abilities.json"))
    ds_abilities_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_abilities.json"))
    ds_det_rows = _read_json(os.path.join(WAHA_DIR, "Datasheets_detachment_abilities.json"))
    enhancements = _read_json(os.path.join(WAHA_DIR, "Enhancements.json"))
    stratagems = _read_json(os.path.join(WAHA_DIR, "Stratagems.json"))
    detachments = _load_detachments()
    ds_map = _build_datasheet_map()

    _seed_ability_support_maps(abilities, det_abilities_rows)

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
    datasheet_abilities_by_datasheet: Dict[str, Dict[Tuple[str, ...], dict]] = {}
    for row in ds_abilities_rows:
        dsid = str(row.get("datasheet_id", "") or "").strip()
        ds = ds_map.get(dsid)
        if not ds:
            continue
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
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
            key = ("row", _norm(name), _norm(_strip_html(desc)))

        bucket = datasheet_abilities_by_faction.setdefault(fid, {})
        if key not in bucket:
            bucket[key] = {"name": name, "description": desc, "ability_id": ability_id, "units": set()}
        bucket[key]["units"].add(ds.get("name", dsid))

        ds_bucket = datasheet_abilities_by_datasheet.setdefault(dsid, {})
        if key not in ds_bucket:
            ds_bucket[key] = {"name": name, "description": desc, "ability_id": ability_id}

    datasheets_by_faction: Dict[str, List[dict]] = {}
    for ds in ds_map.values():
        fid = str(ds.get("faction_id", "") or "").strip().upper()
        if fid not in SUPPORTED_FACTION_IDS:
            continue
        datasheets_by_faction.setdefault(fid, []).append(ds)

    datasheet_support_overrides = _datasheet_support_by_name_faction()

    lines: List[str] = []
    lines.append("# Ability support matrix (Wahapedia)")
    lines.append("")
    lines.append("Generated from `wahapedia_data/*.json` using `scripts/generate_ability_support_matrix.py`.")
    lines.append("")
    lines.append("## Legend")
    legend_rows = [
        ([_escape(_status_icon("supported")), "Implemented in engine."], "Supported"),
        ([_escape(_status_icon("partial")), "Partially implemented in engine."], "Partial"),
        ([_escape(_status_icon("not implemented")), "Not implemented."], "Not implemented"),
    ]
    lines.append(_table(["Status", "Meaning"], legend_rows))
    lines.append("")

    # ---------------- Core section ----------------
    core_abilities = [a for a in abilities if not a.get("faction_id")]
    core_abilities.sort(key=lambda a: _norm(a.get("name", "")))
    core_rows = []
    core_items: List[Tuple[str, str]] = []
    for ab in core_abilities:
        name = ab.get("name", "") or ""
        desc = ab.get("description", "") or ""
        ability_id = str(ab.get("id", "") or "")
        status, notes = _classify_ability(name, desc, ability_id=ability_id, faction_id="")
        core_items.append((status, name))
        core_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(name),
                    _engine_block(_engine_notes(status, notes)),
                ],
                status,
            )
        )
    core_table = _table(["Status", "Ability", "Description"], core_rows)

    core_strats = []
    for s in stratagems:
        if (s.get("faction_id") or "").strip():
            continue
        ttype = (s.get("type", "") or "").strip().lower()
        if "core" not in ttype:
            continue
        if "boarding" in ttype or "challenger" in ttype:
            continue
        core_strats.append(s)

    def _id_key(entry: dict) -> int:
        try:
            return int((entry.get("id") or "0").strip())
        except Exception:
            return 0

    by_name: Dict[str, dict] = {}
    for entry in core_strats:
        name_key = _norm(entry.get("name", ""))
        if not name_key:
            continue
        prev = by_name.get(name_key)
        if prev is None or _id_key(entry) > _id_key(prev):
            by_name[name_key] = entry
    core_strats = list(by_name.values())
    core_strats.sort(key=lambda e: _norm(e.get("name", "")))

    core_strat_rows = []
    core_strat_items: List[Tuple[str, str]] = []
    for s in core_strats:
        status, notes, _ = _stratagem_support(s.get("name", ""))
        core_strat_items.append((status, s.get("name", "") or ""))
        core_strat_rows.append(
            (
                [
                    _escape(_status_icon(status)),
                    _escape(s.get("name", "")),
                    f"<code>{_escape(s.get('id', ''))}</code>",
                    _escape(s.get("type", "")),
                    _escape(s.get("cp_cost", "")),
                    _escape(s.get("turn", "")),
                    _escape(s.get("phase", "")),
                    _escape(notes),
                ],
                status,
            )
        )
    core_strat_table = _table(
        ["Status", "Stratagem", "ID", "Type", "CP", "Turn", "Phase", "Notes"],
        core_strat_rows,
    )

    core_supported, core_total = _summarize_section_count(core_items)
    core_body = "\n".join(
        [
            "### Core Abilities",
            core_table,
        ]
    )
    lines.append(_details_raw(_summary_span("Core", core_supported, core_total), core_body))
    lines.append("")

    core_strat_supported, core_strat_total = _summarize_section_count(core_strat_items)
    core_strat_body = "\n".join(
        [
            "### Core Stratagems",
            core_strat_table,
        ]
    )
    lines.append(
        _details_raw(
            _summary_span_with_label("Core Stratagems", core_strat_supported, core_strat_total, "stratagems"),
            core_strat_body,
        )
    )
    lines.append("")

    # ---------------- Faction summary + files ----------------
    os.makedirs(FACTION_DOCS_DIR, exist_ok=True)
    summary_rows = []
    summary_entries = []
    for faction_id, meta in FACTION_RULE_METADATA.items():
        if faction_id not in SUPPORTED_FACTION_IDS:
            continue
        faction_name = str(meta.get("faction_name", "") or faction_id)
        content, supported, total = _build_faction_content(
            faction_id=faction_id,
            meta=meta,
            abilities=abilities,
            det_abilities_by_det=det_abilities_by_det,
            enhancements=enhancements,
              stratagems=stratagems,
              detachments=detachments,
              ds_abilities_rows=ds_abilities_rows,
              datasheet_abilities_by_faction=datasheet_abilities_by_faction,
              datasheet_abilities_by_datasheet=datasheet_abilities_by_datasheet,
              datasheets_by_faction=datasheets_by_faction,
              datasheet_support_overrides=datasheet_support_overrides,
          )
        slug = _slugify(faction_name)
        rel_path = f"factions/{slug}.md"
        out_path = os.path.join(FACTION_DOCS_DIR, f"{slug}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        summary_entries.append((faction_name, supported, total, rel_path))

    summary_entries.sort(key=lambda t: t[0].lower())
    for faction_name, supported, total, rel_path in summary_entries:
        status = _summary_status(supported, total)
        summary_rows.append(
            (
                [
                    _escape(faction_name),
                    _escape(_summary_icon(supported, total)),
                    _escape(f"{supported} out of {total}"),
                    f"<a href=\"{_escape(rel_path)}\">View</a>",
                ],
                status,
            )
        )
    lines.append("## Factions")
    lines.append(_table(["Faction", "Status", "Supported", "Link"], summary_rows))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    os.makedirs(DOCS_DIR, exist_ok=True)
    content = _build_matrix()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
