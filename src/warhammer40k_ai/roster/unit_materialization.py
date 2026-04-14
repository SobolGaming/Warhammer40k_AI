"""Runtime unit materialization helpers for authored and parsed rosters."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import TYPE_CHECKING

from ..units.unit import Unit
from ..waha_helper import WahaHelper
from .army import ArmyValidationError
from .army_build import EnhancementAssignment, RosterEntry, ValidatedMuster

if TYPE_CHECKING:
    from .army import Army
    from warhammer40k_ai.rules.enhancement import Enhancement

logger = logging.getLogger(__name__)

_WARGEAR_PATTERN = re.compile(
    r"^(?:(?P<model>[^:]+):\s*)?(?:(?P<quantity>\d+)\s*x\s+)?(?P<name>.+)$",
    flags=re.IGNORECASE,
)


def _normalize_gear_name(text: str) -> str:
    return (
        str(text or "")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u00e2\u0080\u0099", "'")
        .lower()
    )


def _coerce_positive_int(value: object, *, field_name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _set_build_entry_id(unit: object, entry_id: str | None) -> None:
    if not entry_id:
        return
    set_entry_id = getattr(unit, "set_build_entry_id", None)
    if callable(set_entry_id):
        set_entry_id(entry_id)
        return
    setattr(unit, "build_entry_id", str(entry_id))


def resolve_roster_entry_datasheet(
    entry: RosterEntry,
    *,
    faction_id: str,
    waha_helper: WahaHelper,
):
    datasheet_id = str((entry.metadata or {}).get("datasheet_id", "") or "").strip() or None
    datasheet = waha_helper.get_full_datasheet_info_by_name(
        entry.name,
        datasheet_id=datasheet_id,
        faction_id=str(faction_id or "").strip() or None,
    )
    if datasheet is None:
        datasheet = waha_helper.get_full_datasheet_info_by_name(
            entry.name,
            datasheet_id=datasheet_id,
        )
    if datasheet is None:
        raise ArmyValidationError(
            f"Roster entry '{entry.entry_id}' could not resolve datasheet '{entry.name}'."
        )
    return datasheet


def _wargear_dict_from_metadata(
    entry: RosterEntry,
    raw_value: object,
) -> dict[str, set[tuple[str, int]]]:
    if not isinstance(raw_value, Mapping):
        raise ValueError(
            f"Roster entry '{entry.entry_id}' metadata.wargear_by_model must be a mapping."
        )
    wargear_dict: dict[str, set[tuple[str, int]]] = {}
    for raw_model_name, raw_assignments in raw_value.items():
        model_name = str(raw_model_name or "").strip()
        if not isinstance(raw_assignments, list):
            raise ValueError(
                f"Roster entry '{entry.entry_id}' metadata.wargear_by_model['{model_name}'] "
                "must be a list."
            )
        wargear_dict[model_name] = set()
        for assignment_index, raw_assignment in enumerate(raw_assignments, start=1):
            if not isinstance(raw_assignment, Mapping):
                raise ValueError(
                    f"Roster entry '{entry.entry_id}' metadata.wargear_by_model['{model_name}']"
                    f"[{assignment_index - 1}] must be an object."
                )
            gear_name = str(raw_assignment.get("name", "") or "").strip()
            if not gear_name:
                raise ValueError(
                    f"Roster entry '{entry.entry_id}' metadata.wargear_by_model['{model_name}']"
                    f"[{assignment_index - 1}].name is required."
                )
            quantity = _coerce_positive_int(
                raw_assignment.get("quantity", 1),
                field_name=(
                    "Roster entry "
                    f"'{entry.entry_id}' metadata.wargear_by_model['{model_name}']"
                    f"[{assignment_index - 1}].quantity"
                ),
            )
            wargear_dict[model_name].add((gear_name, quantity))
    return wargear_dict


def _wargear_dict_from_strings(entry: RosterEntry) -> dict[str, set[tuple[str, int]]]:
    wargear_dict: dict[str, set[tuple[str, int]]] = {}
    for index, raw_item in enumerate(list(entry.wargear or []), start=1):
        item_text = str(raw_item or "").strip()
        if not item_text:
            continue
        match = _WARGEAR_PATTERN.match(item_text)
        if match is None:
            raise ValueError(
                f"Roster entry '{entry.entry_id}' wargear[{index - 1}] could not be parsed: "
                f"{item_text!r}."
            )
        model_name = str(match.group("model") or "").strip()
        quantity = _coerce_positive_int(
            match.group("quantity") or 1,
            field_name=f"Roster entry '{entry.entry_id}' wargear[{index - 1}] quantity",
        )
        gear_name = str(match.group("name") or "").strip()
        if not gear_name:
            raise ValueError(
                f"Roster entry '{entry.entry_id}' wargear[{index - 1}] is missing a name."
            )
        wargear_dict.setdefault(model_name, set()).add((gear_name, quantity))
    return wargear_dict


def wargear_dict_for_entry(entry: RosterEntry) -> dict[str, set[tuple[str, int]]]:
    metadata = dict(entry.metadata or {})
    if "wargear_by_model" in metadata:
        return _wargear_dict_from_metadata(entry, metadata.get("wargear_by_model"))
    return _wargear_dict_from_strings(entry)


def add_materialized_unit_to_army(
    army: "Army",
    unit: Unit,
    model_count: int,
    wargear_dict: dict[str, set[tuple[str, int]]],
    enhancement: "Enhancement | None",
    waha_helper: WahaHelper,
    is_warlord: bool,
    *,
    build_entry_id: str | None = None,
    assignment_metadata: dict[str, object] | None = None,
    strict_unknown_wargear: bool = False,
) -> None:
    """Apply loadout choices to a runtime unit and add it to the army."""

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

                if not target_models:
                    raise ValueError(
                        f"Invalid wargear assignment for '{unit.name}': no models named "
                        f"'{model_name}' to receive '{gear_name}'."
                    )
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
                continue

            matching_option = None
            for gear in unit.wargear_options:
                for choice in gear.wargear_to or []:
                    for _quantity, name in choice or []:
                        if name and _normalize_gear_name(name) == gear_name:
                            matching_option = gear
                            break
                    if matching_option is not None:
                        break
                if matching_option is not None:
                    break
            if matching_option is not None:
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
            if matching_ability is not None:
                unit.add_ability(matching_ability, model_name)
                continue

            if strict_unknown_wargear:
                raise ArmyValidationError(
                    f"Could not resolve wargear option '{wargear_name}' for unit '{unit.name}'."
                )

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
    _set_build_entry_id(unit, build_entry_id)
    if enhancement is not None:
        army.add_enhancement(
            enhancement,
            unit,
            assignment_metadata=dict(assignment_metadata or {}),
        )
    army.add_unit(unit)
    if is_warlord:
        army.select_warlord(unit)


def _resolve_enhancement(
    assignment: EnhancementAssignment,
    *,
    waha_helper: WahaHelper,
) -> "Enhancement":
    enhancement = waha_helper.get_enhancement_by_name(assignment.enhancement_name)
    if enhancement is None:
        raise ArmyValidationError(
            f"Enhancement assignment '{assignment.assignment_id}' could not resolve enhancement "
            f"'{assignment.enhancement_name}'."
        )
    return enhancement


def materialize_roster_entry(
    army: "Army",
    entry: RosterEntry,
    *,
    faction_id: str,
    waha_helper: WahaHelper,
    enhancement_assignments: list[EnhancementAssignment] | None = None,
    strict_unknown_wargear: bool = False,
) -> Unit:
    datasheet = resolve_roster_entry_datasheet(
        entry,
        faction_id=faction_id,
        waha_helper=waha_helper,
    )
    unit = Unit(datasheet)
    assignments = list(enhancement_assignments or [])
    enhancement = None
    assignment_metadata = None
    if assignments:
        enhancement = _resolve_enhancement(assignments[0], waha_helper=waha_helper)
        assignment_metadata = dict(assignments[0].metadata or {})
    add_materialized_unit_to_army(
        army,
        unit,
        entry.count,
        wargear_dict_for_entry(entry),
        enhancement,
        waha_helper,
        entry.is_warlord,
        build_entry_id=entry.entry_id,
        assignment_metadata=assignment_metadata,
        strict_unknown_wargear=strict_unknown_wargear,
    )
    return unit


def materialize_validated_muster_units(
    army: "Army",
    validated_muster: ValidatedMuster,
    *,
    waha_helper: WahaHelper,
    strict_unknown_wargear: bool = False,
) -> list[Unit]:
    blueprint = validated_muster.blueprint
    assignments_by_entry_id: dict[str, list[EnhancementAssignment]] = {}
    for assignment in list(blueprint.enhancement_assignments or []):
        assignments_by_entry_id.setdefault(assignment.target_entry_id, []).append(assignment)

    units: list[Unit] = []
    for entry in list(blueprint.unit_entries or []):
        units.append(
            materialize_roster_entry(
                army,
                entry,
                faction_id=validated_muster.faction_id,
                waha_helper=waha_helper,
                enhancement_assignments=assignments_by_entry_id.get(entry.entry_id, []),
                strict_unknown_wargear=strict_unknown_wargear,
            )
        )
    return units


__all__ = [
    "add_materialized_unit_to_army",
    "materialize_roster_entry",
    "materialize_validated_muster_units",
    "resolve_roster_entry_datasheet",
    "wargear_dict_for_entry",
]
