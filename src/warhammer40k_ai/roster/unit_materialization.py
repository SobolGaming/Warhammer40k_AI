"""Runtime unit materialization helpers for authored and parsed rosters."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import logging
import re
from typing import TYPE_CHECKING

from ..units.unit import Unit
from ..utility.text_normalization import canonical_rules_key, normalize_display_text
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
    return canonical_rules_key(text)


def _singularized_gear_key(key: str) -> str:
    words: list[str] = []
    for word in str(key or "").split():
        if word.endswith("z") and len(word) > 2:
            words.append(word[:-1])
        elif word.endswith("men") and len(word) > 3:
            words.append(f"{word[:-3]}man")
        elif word.endswith("ches") and len(word) > 4:
            words.append(word[:-2])
        elif word.endswith("ies") and len(word) > 3:
            words.append(f"{word[:-3]}y")
        elif word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
            words.append(word[:-1])
        else:
            words.append(word)
    return " ".join(words).strip()


def _gear_name_match_keys(text: object) -> set[str]:
    key = _normalize_gear_name(str(text or ""))
    keys = {key} if key else set()
    if "acquila" in key:
        keys.add(key.replace("acquila", "aquila"))
    if key.startswith("chainbreaker "):
        keys.add(key.removeprefix("chainbreaker ").strip())
    if key.startswith("questoris "):
        keys.add(key.removeprefix("questoris ").strip())
    if " s " in key:
        keys.add(key.replace(" s ", "s "))
    singular_key = _singularized_gear_key(key)
    if singular_key:
        keys.add(singular_key)
    no_and_key = key.replace(" and ", " ")
    if no_and_key:
        keys.add(no_and_key)
        singular_no_and_key = _singularized_gear_key(no_and_key)
        if singular_no_and_key:
            keys.add(singular_no_and_key)
    with_prefix = key.split(" with ", 1)[0].strip()
    if with_prefix and with_prefix != key:
        keys.add(with_prefix)
        singular_with_prefix = _singularized_gear_key(with_prefix)
        if singular_with_prefix:
            keys.add(singular_with_prefix)
    leading_quantity = re.match(r"^\s*(?:up to\s+)?\d+\s+(.+)$", key)
    if leading_quantity is not None:
        quantity_suffix = leading_quantity.group(1).strip()
        if quantity_suffix:
            keys.add(quantity_suffix)
            singular_quantity_suffix = _singularized_gear_key(quantity_suffix)
            if singular_quantity_suffix:
                keys.add(singular_quantity_suffix)
    embedded_quantity = re.match(r"^.+\b\d+\s+(.+)$", key)
    if embedded_quantity is not None:
        embedded_quantity_suffix = embedded_quantity.group(1).strip()
        if embedded_quantity_suffix:
            keys.add(embedded_quantity_suffix)
            singular_embedded_quantity_suffix = _singularized_gear_key(embedded_quantity_suffix)
            if singular_embedded_quantity_suffix:
                keys.add(singular_embedded_quantity_suffix)
    if " s " in key:
        suffix = key.split(" s ", 1)[1].strip()
        if suffix:
            keys.add(suffix)
    display = normalize_display_text(text)
    possessive = re.match(r"^\s*[^']+'\s*s\s+(.+)$", display, flags=re.IGNORECASE)
    if possessive is not None:
        suffix = _normalize_gear_name(possessive.group(1))
        if suffix:
            keys.add(suffix)
    return keys


def _matches_requested_gear_name(candidate_name: object, requested_name: object) -> bool:
    candidate_keys = _gear_name_match_keys(candidate_name)
    requested_keys = _gear_name_match_keys(requested_name)
    return bool(candidate_keys and requested_keys and candidate_keys.intersection(requested_keys))


def _choice_matches_requested_wargear(
    choice: object,
    requested_wargear: list[tuple[str, int]],
) -> list[tuple[int, int]] | None:
    requested_remaining = Counter(
        {index: int(quantity or 0) for index, (_name, quantity) in enumerate(requested_wargear)}
    )
    consumed: list[tuple[int, int]] = []
    for raw_quantity, raw_name in list(choice or []):
        choice_quantity = int(raw_quantity or 0)
        choice_name = str(raw_name or "").strip()
        if choice_quantity <= 0 or not choice_name:
            return None
        matched_index = None
        for index, (requested_name, _requested_quantity) in enumerate(requested_wargear):
            if requested_remaining[index] < choice_quantity:
                continue
            if _matches_requested_gear_name(choice_name, requested_name):
                matched_index = index
                break
        if matched_index is None:
            return None
        requested_remaining[matched_index] -= choice_quantity
        consumed.append((matched_index, choice_quantity))
    return consumed


def _remove_consumed_wargear(
    requested_wargear: list[tuple[str, int]],
    consumed: list[tuple[int, int]],
) -> list[tuple[str, int]]:
    remaining_quantities = [int(quantity or 0) for _name, quantity in requested_wargear]
    for index, consumed_quantity in consumed:
        remaining_quantities[index] -= int(consumed_quantity or 0)
    remaining: list[tuple[str, int]] = []
    for index, (name, _quantity) in enumerate(requested_wargear):
        quantity = remaining_quantities[index]
        if quantity > 0:
            remaining.append((name, quantity))
    return remaining


def _unit_can_resolve_wargear_directly(unit: Unit, requested_name: object) -> bool:
    if any(
        _matches_requested_gear_name(gear.name, requested_name)
        for gear in list(getattr(unit, "possible_wargear", []) or [])
    ):
        return True
    return any(
        _matches_requested_gear_name(ability.name, requested_name)
        and getattr(ability, "type", None) == "Wargear"
        for ability in list(getattr(unit, "possible_abilities", []) or [])
    )


def _apply_exact_wargear_bundles(
    unit: Unit,
    requested_wargear: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    remaining = list(requested_wargear)
    bundle_choices: list[tuple[str, object]] = []
    for option in list(getattr(unit, "wargear_options", []) or []):
        for choice in list(getattr(option, "wargear_to", []) or []):
            if len(list(choice or [])) <= 1:
                continue
            if all(
                _unit_can_resolve_wargear_directly(unit, name)
                for _quantity, name in list(choice or [])
            ):
                continue
            bundle_label = " and ".join(
                f"{int(quantity or 0)} {name}"
                for quantity, name in list(choice or [])
                if int(quantity or 0) > 0 and str(name or "").strip()
            )
            if bundle_label:
                bundle_choices.append((bundle_label, choice))
    bundle_choices.sort(key=lambda item: canonical_rules_key(item[0]))

    changed = True
    while changed:
        changed = False
        for bundle_label, choice in bundle_choices:
            consumed = _choice_matches_requested_wargear(choice, remaining)
            if consumed is None:
                continue
            unit.apply_wargear_options_strict(bundle_label)
            remaining = _remove_consumed_wargear(remaining, consumed)
            changed = True
            break
    return remaining


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
        remaining_wargear = _apply_exact_wargear_bundles(
            unit,
            sorted(list(wargear_list or []), key=lambda item: (canonical_rules_key(item[0]), int(item[1] or 0))),
        )
        for wargear_name, quantity in remaining_wargear:
            gear_name = _normalize_gear_name(wargear_name)
            display_gear_name = normalize_display_text(wargear_name)
            matching_gear = next(
                (
                    gear
                    for gear in unit.possible_wargear
                    if _matches_requested_gear_name(gear.name, wargear_name)
                ),
                None,
            )
            if matching_gear:
                if model_name and model_name != unit.name:
                    target_models = [
                        model
                        for model in unit.models
                        if canonical_rules_key(model.name) == canonical_rules_key(model_name)
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

            matching_ability = next(
                (
                    ability
                    for ability in unit.possible_abilities
                    if _matches_requested_gear_name(ability.name, wargear_name)
                    and ability.type == "Wargear"
                ),
                None,
            )
            if matching_ability is not None:
                unit.add_ability(matching_ability, model_name)
                continue

            matching_option = None
            for gear in unit.wargear_options:
                for choice in gear.wargear_to or []:
                    for _quantity, name in choice or []:
                        if name and _matches_requested_gear_name(name, wargear_name):
                            matching_option = gear
                            display_gear_name = normalize_display_text(name)
                            break
                    if matching_option is not None:
                        break
                if matching_option is not None:
                    break
            if matching_option is not None:
                unit.apply_wargear_options_strict(display_gear_name)
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
    army.add_unit(unit)
    if enhancement is not None:
        army.add_enhancement(
            enhancement,
            unit,
            assignment_metadata=dict(assignment_metadata or {}),
        )
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
    entry_metadata = dict(entry.metadata or {})
    daemonic_allegiance = str(entry_metadata.get("daemonic_allegiance", "") or "").strip()
    if daemonic_allegiance:
        unit.daemonic_allegiance = daemonic_allegiance.upper()
    ally_context = dict(entry_metadata.get("ally_context", {}) or {})
    if ally_context:
        build_metadata = dict(getattr(unit, "build_metadata", {}) or {})
        build_metadata["ally_context"] = dict(ally_context)
        for key in ("ally_source_rule", "allied_faction", "parent_faction", "parent_faction_id", "catalog_faction_id"):
            value = entry_metadata.get(key)
            if value:
                build_metadata[key] = value
        unit.build_metadata = build_metadata
        special_rules = getattr(unit, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["ally_context"] = dict(ally_context)
        for key in ("ally_source_rule", "allied_faction", "parent_faction", "parent_faction_id", "catalog_faction_id"):
            value = entry_metadata.get(key)
            if value:
                special_rules[key] = value
        unit.special_rules = special_rules
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
