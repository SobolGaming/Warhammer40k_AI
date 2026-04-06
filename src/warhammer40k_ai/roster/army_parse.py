"""Army-list parsing helpers split out of roster.army for PR-002."""

from __future__ import annotations

import codecs
import logging
import os
import re
import tempfile
from typing import Dict, Set, Tuple

from ..units.unit import Unit
from ..waha_helper import WahaHelper
from warhammer40k_ai.rules.enhancement import Enhancement

from .army import Army, _assert_supported_faction, get_faction_id_from_name
from .army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry, ValidatedMuster
from .army_runtime import apply_validated_muster_to_army

logger = logging.getLogger(__name__)

_SECTION_HEADERS = {
    "CHARACTER",
    "CHARACTERS",
    "BATTLELINE",
    "DEDICATED TRANSPORTS",
    "OTHER DATASHEETS",
}
_BULLET_PREFIXES = ("\u2022", "\u25e6", "-", "*")


def _find_points_limit(raw_lines: list[str], *, file_path: str) -> int:
    for line in raw_lines:
        match = re.search(r"\(([\d,]+)\s*points?\)", line, flags=re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))
    raise ValueError(f"Could not find points limit in army list header: {file_path!r}")


def _is_app_export(raw_lines: list[str]) -> bool:
    return any("exported with app version" in (line or "").lower() for line in raw_lines)


def _first_section_index(stripped_lines: list[str]) -> int:
    for index, line in enumerate(stripped_lines):
        if (line or "").strip().upper() in _SECTION_HEADERS:
            return index
    return 0


def _is_bullet_line(text: str) -> bool:
    return text.startswith(_BULLET_PREFIXES)


def _strip_bullet(text: str) -> str:
    for prefix in _BULLET_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _serialize_wargear_dict(
    wargear_dict: Dict[str, Set[Tuple[str, int]]],
) -> tuple[list[str], dict[str, list[dict[str, int | str]]]]:
    flattened: list[str] = []
    metadata: dict[str, list[dict[str, int | str]]] = {}
    for model_name in sorted(str(name or "").strip() for name in wargear_dict.keys()):
        entries = sorted(
            list(wargear_dict.get(model_name, set()) or []),
            key=lambda item: (str(item[0] or ""), int(item[1] or 0)),
        )
        metadata[model_name] = []
        for wargear_name, quantity in entries:
            quantity_value = int(quantity or 0)
            wargear_label = str(wargear_name or "").strip()
            metadata[model_name].append({"name": wargear_label, "quantity": quantity_value})
            if model_name:
                flattened.append(f"{model_name}: {quantity_value}x {wargear_label}")
            else:
                flattened.append(f"{quantity_value}x {wargear_label}")
    return flattened, metadata


def _append_parsed_build_entry(
    unit_entries: list[RosterEntry],
    enhancement_assignments: list[EnhancementAssignment],
    *,
    entry_id: str,
    unit_name: str,
    model_count: int,
    wargear_dict: Dict[str, Set[Tuple[str, int]]],
    enhancement: Enhancement | None,
    is_warlord: bool,
) -> None:
    wargear, wargear_metadata = _serialize_wargear_dict(wargear_dict)
    entry = RosterEntry(
        entry_id=entry_id,
        name=unit_name,
        count=max(int(model_count or 0), 1),
        detachment_selection_id="parsed_detachment_1",
        wargear=wargear,
        enhancement_names=[enhancement.name] if enhancement is not None else [],
        is_warlord=bool(is_warlord),
        metadata={
            "source": "army_list_parse",
            "raw_model_count": int(model_count or 0),
            "wargear_by_model": wargear_metadata,
        },
    )
    unit_entries.append(entry)
    if enhancement is None:
        return
    enhancement_assignments.append(
        EnhancementAssignment(
            assignment_id=f"{entry_id}_enhancement_1",
            enhancement_name=enhancement.name,
            target_entry_id=entry_id,
            detachment_selection_id="parsed_detachment_1",
            metadata={"source": "army_list_parse"},
        )
    )


def parse_army_list(file_path: str, waha_helper: WahaHelper) -> Army:
    with codecs.open(file_path, "r", encoding="utf-8-sig") as handle:
        lines = handle.readlines()
        if lines and lines[0].startswith("\ufeff"):
            lines[0] = lines[0][1:]

    stripped = [line.strip() for line in lines]
    if not stripped:
        raise ValueError(f"Army list is empty: {file_path!r}")

    points_limit = _find_points_limit(lines, file_path=file_path)
    is_app_format = _is_app_export(lines)
    if is_app_format:
        faction_keyword = ""
        detachment_type = ""
        for line in stripped[1:]:
            if not line:
                continue
            if line.lower().startswith("exported with"):
                break
            if "strike force" in line.lower():
                continue
            if not faction_keyword:
                faction_keyword = line
                continue
            if not detachment_type:
                detachment_type = line
                break
        if not faction_keyword:
            raise ValueError(f"Could not determine faction from app-export header: {file_path!r}")
        if not detachment_type:
            detachment_type = "Unknown Detachment"
    else:
        faction_header = (stripped[0] or "").strip()
        if not faction_header:
            raise ValueError(f"Army list header is missing faction info: {file_path!r}")
        faction_keyword = (
            re.split(r"\s*[-\u2013]\s*", faction_header) or [faction_header]
        )[-1].strip() or faction_header
        detachment_type = (stripped[2] or "").strip() if len(stripped) > 2 else "Unknown Detachment"

    start_index = _first_section_index(stripped)
    logger.info(
        "Parsing army: %s - %s (%s points)",
        faction_keyword,
        detachment_type,
        points_limit,
    )

    army = Army(faction=faction_keyword, detachment_type=detachment_type, points_limit=points_limit)
    faction_id = get_faction_id_from_name(faction_keyword)
    _assert_supported_faction(faction_keyword, faction_id)
    if faction_id:
        logger.info("Using faction ID: %s for datasheet lookups", faction_id)
        army.faction_id = faction_id
    else:
        logger.warning(
            "Warning: Could not determine faction ID for '%s', using generic lookup",
            faction_keyword,
        )
    army.configure_rule_managers()

    current_unit = None
    current_model_count = 0
    current_model_name = None
    current_wargear: Dict[str, Set[Tuple[str, int]]] = {}
    current_enhancement = None
    is_warlord = False
    parsed_unit_entries: list[RosterEntry] = []
    parsed_enhancement_assignments: list[EnhancementAssignment] = []

    for line in lines[start_index:]:
        line = line.strip()
        if not line or line.upper() in _SECTION_HEADERS:
            continue
        if line.startswith("Exported with"):
            break

        if not _is_bullet_line(line):
            if current_unit:
                parsed_entry_id = f"parsed_unit_{len(parsed_unit_entries) + 1}"
                add_unit_to_army(
                    army,
                    current_unit,
                    current_model_count,
                    current_wargear,
                    current_enhancement,
                    waha_helper,
                    is_warlord,
                    build_entry_id=parsed_entry_id,
                )
                _append_parsed_build_entry(
                    parsed_unit_entries,
                    parsed_enhancement_assignments,
                    entry_id=parsed_entry_id,
                    unit_name=current_unit.name,
                    model_count=current_model_count,
                    wargear_dict=current_wargear,
                    enhancement=current_enhancement,
                    is_warlord=is_warlord,
                )
                current_unit = None
                current_model_name = None
                current_model_count = 0
                current_wargear = {}
                current_enhancement = None
                is_warlord = False

            unit_name = line.split(" (")[0].strip()
            if faction_id:
                datasheet = waha_helper.get_full_datasheet_info_by_name(
                    unit_name,
                    faction_id=faction_id,
                )
                if not datasheet:
                    logger.warning(
                        "Warning: Faction-specific datasheet not found for %s (faction: %s)",
                        unit_name,
                        faction_id,
                    )
            else:
                datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name)

            if datasheet:
                current_unit = Unit(datasheet)
            else:
                logger.warning("Warning: Datasheet not found for %s", unit_name)
            continue

        data = _strip_bullet(line)
        if data.lower() == "warlord":
            is_warlord = True
            continue
        if data.lower().startswith("enhancement"):
            enhancement_name = data.split(":", 1)[1].strip()
            current_enhancement = waha_helper.get_enhancement_by_name(enhancement_name)
            if not current_enhancement:
                logger.warning("Warning: Enhancement not found for %s", enhancement_name)
            continue
        if data.lower().startswith("daemonic allegiance:"):
            allegiance = data.split(":", 1)[1].strip()
            if current_unit is not None:
                current_unit.daemonic_allegiance = allegiance
            continue

        if "x " in data:
            quantity_text, item_name = data.split("x ", 1)
            quantity = int(quantity_text)
        else:
            quantity = 1
            item_name = data

        if current_unit and any(
            item_name.strip() in model_name.rstrip("s")
            for model_name in current_unit.unit_composition.keys()
        ):
            current_model_count += quantity
            current_model_name = item_name.strip()
            current_wargear[current_model_name] = set()
            continue

        target_name = current_model_name or (current_unit.name if current_unit is not None else "")
        current_wargear.setdefault(target_name, set()).add((item_name.strip(), quantity))

    if current_unit:
        parsed_entry_id = f"parsed_unit_{len(parsed_unit_entries) + 1}"
        add_unit_to_army(
            army,
            current_unit,
            current_model_count,
            current_wargear,
            current_enhancement,
            waha_helper,
            is_warlord,
            build_entry_id=parsed_entry_id,
        )
        _append_parsed_build_entry(
            parsed_unit_entries,
            parsed_enhancement_assignments,
            entry_id=parsed_entry_id,
            unit_name=current_unit.name,
            model_count=current_model_count,
            wargear_dict=current_wargear,
            enhancement=current_enhancement,
            is_warlord=is_warlord,
        )

    validated_muster = ValidatedMuster(
        blueprint=ArmyBlueprint(
            faction=faction_keyword,
            points_limit=points_limit,
            detachments=[
                DetachmentSelection(
                    selection_id="parsed_detachment_1",
                    detachment_type=detachment_type,
                    detachment_points_cost=0,
                    metadata={"source": "army_list_parse"},
                )
            ],
            unit_entries=parsed_unit_entries,
            enhancement_assignments=parsed_enhancement_assignments,
            metadata={"source": "army_list_parse", "file_path": os.path.normpath(file_path)},
        ),
        faction_id=str(faction_id or ""),
        detachment_points_spent=0,
    )
    apply_validated_muster_to_army(army, validated_muster)

    logger.info("Finished parsing. Total units: %s", len(army.units))
    return army


def parse_army_list_text(
    list_text: str,
    waha_helper: WahaHelper,
    *,
    list_name: str = "army_list",
) -> Army:
    if list_text is None:
        raise ValueError("Army list text is required.")

    safe_name = "".join(
        character
        for character in (list_name or "army_list")
        if character.isalnum() or character in ("_", "-")
    )
    if not safe_name:
        safe_name = "army_list"

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=f"_{safe_name}.txt",
            delete=False,
        ) as handle:
            temp_path = handle.name
            handle.write(list_text)
        return parse_army_list(temp_path, waha_helper)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def add_unit_to_army(
    army: Army,
    unit: Unit,
    model_count: int,
    wargear_dict: Dict[str, Set[Tuple[str, int]]],
    enhancement: Enhancement | None,
    waha_helper: WahaHelper,
    is_warlord: bool,
    *,
    build_entry_id: str | None = None,
) -> None:
    def _normalize_gear_name(text: str) -> str:
        return (
            str(text or "")
            .replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u00e2\u0080\u0099", "'")
            .lower()
        )

    unit.configure_models(model_count, [])

    for model_name, wargear_list in wargear_dict.items():
        for wargear_name, quantity in wargear_list:
            gear_name = _normalize_gear_name(wargear_name)
            matching_gear = next(
                (
                    gear
                    for gear in unit.possible_wargear
                    if _normalize_gear_name(gear.name) == gear_name
                ),
                None,
            )
            if matching_gear:
                if model_name and model_name != unit.name:
                    target_models = [
                        model
                        for model in unit.models
                        if model.name.lower() == model_name.lower()
                    ]
                else:
                    target_models = unit.models

                if target_models:
                    if quantity == len(target_models):
                        for model in target_models:
                            model.wargear.append(matching_gear)
                    elif quantity < len(target_models):
                        for index in range(quantity):
                            target_models[index].wargear.append(matching_gear)
                    else:
                        items_per_model = quantity // len(target_models)
                        remainder = quantity % len(target_models)
                        for index, model in enumerate(target_models):
                            for _ in range(items_per_model):
                                model.wargear.append(matching_gear)
                            if index < remainder:
                                model.wargear.append(matching_gear)
                else:
                    raise ValueError(
                        f"Invalid wargear assignment for '{unit.name}': no models named '{model_name}' "
                        f"to receive '{gear_name}'."
                    )
                continue

            matching_gear = None
            for gear in unit.wargear_options:
                for choice in gear.wargear_to or []:
                    for _quantity, name in choice or []:
                        if name and _normalize_gear_name(name) == gear_name:
                            matching_gear = gear
                            break
                    if matching_gear:
                        break
                if matching_gear:
                    break
            if matching_gear:
                unit.apply_wargear_options_strict(gear_name)
                continue

            matching_ability = next(
                (
                    ability
                    for ability in unit.possible_abilities
                    if _normalize_gear_name(ability.name) == gear_name
                    and ability.type == "Wargear"
                ),
                None,
            )
            if matching_ability:
                unit.add_ability(matching_ability, model_name)
                continue

            logger.warning(
                "Warning: %s not found in %s's possible wargear or abilities.",
                gear_name,
                unit.name,
            )
            for gear in unit.possible_wargear:
                logger.info("  - %s", gear.name)
            for ability in unit.possible_abilities:
                logger.info("  - %s (Ability Wargear)", ability.name)

    unit.apply_daemonic_allegiance_selection()
    unit.validate_wargear_selection()
    if build_entry_id:
        set_entry_id = getattr(unit, "set_build_entry_id", None)
        if callable(set_entry_id):
            set_entry_id(build_entry_id)
        else:
            unit.build_entry_id = str(build_entry_id)
    if enhancement:
        army.add_enhancement(enhancement, unit)
    army.add_unit(unit)
    if is_warlord:
        army.select_warlord(unit)
