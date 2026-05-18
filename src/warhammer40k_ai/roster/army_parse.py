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
from .unit_materialization import add_materialized_unit_to_army
from ..utility.text_normalization import canonical_rules_key

logger = logging.getLogger(__name__)

_SECTION_HEADERS = {
    "ALLIED UNITS",
    "ALLIES",
    "BATTLELINE / INFANTRY",
    "CHARACTER",
    "CHARACTERS",
    "BATTLELINE",
    "DEDICATED TRANSPORTS",
    "ENHANCEMENT",
    "ENHANCEMENTS",
    "FORTIFICATION",
    "FORTIFICATIONS",
    "OTHER DATASHEETS",
    "VEHICLES / OTHER UNITS",
}
_BULLET_PREFIXES = ("\u2022", "\u25e6", "-", "*")


def _find_points_limit(raw_lines: list[str], *, file_path: str) -> int:
    for line in raw_lines:
        match = re.search(r"\(([\d,.]+)\s*points?\)", line, flags=re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", "").replace(".", ""))
    raise ValueError(f"Could not find points limit in army list header: {file_path!r}")


def _normalized_detachment_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _datasheet_has_keyword(datasheet: object, keyword: str) -> bool:
    target = str(keyword or "").strip().upper()
    if not target or datasheet is None:
        return False
    keywords = [
        str(value or "").strip().upper()
        for value in list(getattr(datasheet, "keywords", []) or [])
        if str(value or "").strip()
    ]
    faction_keywords = [
        str(value or "").strip().upper()
        for value in list(getattr(datasheet, "faction_keywords", []) or [])
        if str(value or "").strip()
    ]
    return target in set(keywords + faction_keywords)


def _pact_ally_datasheet_metadata(
    datasheet: object,
    *,
    faction_id: str,
    detachment_type: str,
) -> dict[str, str]:
    if str(getattr(datasheet, "faction_id", "") or "").strip().upper() != "CD":
        return {}
    primary = str(faction_id or "").strip().upper()
    detachment_key = _normalized_detachment_name(detachment_type)
    if primary == "WE" and "khorne daemonkin" in detachment_key and _datasheet_has_keyword(datasheet, "KHORNE"):
        return {
            "ally_source_rule": "Pact of Blood",
            "allied_faction": "Blood Legions",
            "parent_faction": "World Eaters",
            "parent_faction_id": "WE",
        }
    if primary == "EC" and "carnival of excess" in detachment_key and _datasheet_has_keyword(datasheet, "SLAANESH"):
        return {
            "ally_source_rule": "Pact of Excess",
            "allied_faction": "Legions of Excess",
            "parent_faction": "Emperor's Children",
            "parent_faction_id": "EC",
        }
    return {}


_IMPERIUM_AGENT_PARENT_FACTION_IDS = {"AC", "ADM", "AM", "AS", "GK", "QI", "SM"}
_GENERIC_DAEMON_PACT_PARENT_FACTION_IDS = {"CSM", "QT"}


def _resolve_pact_ally_datasheet(
    waha_helper: WahaHelper,
    unit_name: str,
    *,
    faction_id: str,
    detachment_type: str,
) -> tuple[object | None, dict[str, str]]:
    if str(faction_id or "").strip().upper() not in {"WE", "EC"}:
        primary = str(faction_id or "").strip().upper()
        if primary in _GENERIC_DAEMON_PACT_PARENT_FACTION_IDS:
            datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name, faction_id="CD")
            if datasheet is not None and _datasheet_has_keyword(datasheet, "LEGIONES DAEMONICA"):
                return (datasheet, {})
        if primary in _IMPERIUM_AGENT_PARENT_FACTION_IDS:
            agents_faction_id = get_faction_id_from_name("Imperial Agents") or "AoI"
            datasheet = waha_helper.get_full_datasheet_info_by_name(
                unit_name,
                faction_id=agents_faction_id,
            )
            if datasheet is not None and _datasheet_has_keyword(datasheet, "AGENTS OF THE IMPERIUM"):
                return (datasheet, {})
        return (None, {})
    datasheet = waha_helper.get_full_datasheet_info_by_name(unit_name, faction_id="CD")
    metadata = _pact_ally_datasheet_metadata(
        datasheet,
        faction_id=faction_id,
        detachment_type=detachment_type,
    )
    if not metadata:
        return (None, {})
    return (datasheet, metadata)


def _apply_pact_ally_metadata(unit: Unit, metadata: dict[str, str]) -> None:
    if not metadata:
        return
    build_metadata = dict(getattr(unit, "build_metadata", {}) or {})
    build_metadata["ally_context"] = dict(metadata)
    build_metadata.update(dict(metadata))
    unit.build_metadata = build_metadata
    special_rules = getattr(unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    special_rules["ally_context"] = dict(metadata)
    special_rules.update(dict(metadata))
    unit.special_rules = special_rules


def _is_app_export(raw_lines: list[str]) -> bool:
    return any("exported with app version" in (line or "").lower() for line in raw_lines)


def _first_section_index(stripped_lines: list[str]) -> int:
    for index, line in enumerate(stripped_lines):
        if _is_section_header(line):
            return index
    return 0


def _is_section_header(line: object) -> bool:
    text = str(line or "").strip()
    upper = text.upper()
    if upper in _SECTION_HEADERS:
        return True
    if "(" in text or "[" in text or ":" in text:
        return False
    if "/" not in text:
        return False
    return bool(re.fullmatch(r"[A-Za-z ]+(?:\s*/\s*[A-Za-z ]+)+", text))


def _first_points_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(list(lines or [])):
        if re.search(r"\(([\d,]+)\s*points?\)", str(line or ""), flags=re.IGNORECASE):
            return index
    return None


def _plain_header_faction_and_detachment(stripped_lines: list[str], *, section_index: int) -> tuple[str, str]:
    header_lines = [
        str(line or "").strip()
        for line in list(stripped_lines[: max(0, int(section_index))] or [])
        if str(line or "").strip()
    ]
    if not header_lines:
        raise ValueError("Army list header is missing faction info.")
    points_index = _first_points_line_index(header_lines)
    if points_index is None:
        faction_header = header_lines[0]
        faction_keyword = (
            re.split(r"\s*[-\u2013]\s*", faction_header) or [faction_header]
        )[-1].strip() or faction_header
        detachment_type = header_lines[2] if len(header_lines) > 2 else "Unknown Detachment"
        return faction_keyword, detachment_type

    if points_index == 0 and len(header_lines) > 2:
        return header_lines[1], header_lines[2]

    if points_index + 1 < len(header_lines):
        detachment_type = header_lines[points_index + 1]
        faction_keyword = header_lines[points_index - 1] if points_index >= 1 else header_lines[0]
        return faction_keyword, detachment_type

    detachment_type = header_lines[points_index - 1] if points_index >= 1 else "Unknown Detachment"
    faction_keyword = header_lines[points_index - 2] if points_index >= 2 else header_lines[0]
    return faction_keyword, detachment_type


def _is_bullet_line(text: str) -> bool:
    return text.startswith(_BULLET_PREFIXES)


def _strip_bullet(text: str) -> str:
    for prefix in _BULLET_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _looks_like_unit_detail_continuation(line: object) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower == "warlord" or (
        lower.startswith("enhancement") and ":" in lower
    ) or lower.startswith("daemonic allegiance:") or lower.startswith("mark of chaos:") or re.search(
        r"\bkeywords?:", lower
    ):
        return True
    if re.match(r"^\d+\s*x\s+\S", text, flags=re.IGNORECASE) is None:
        return False
    return re.search(r"\(([\d,]+)\s*points?\)", text, flags=re.IGNORECASE) is None


def _model_name_variants(value: object) -> set[str]:
    key = canonical_rules_key(value)
    if not key:
        return set()
    variants = {key}
    singular_words: list[str] = []
    for word in key.split():
        if word.endswith("z") and len(word) > 2:
            singular_words.append(word[:-1])
        elif word.endswith("men") and len(word) > 3:
            singular_words.append(f"{word[:-3]}man")
        elif word == "chaos" or word.endswith("ss"):
            singular_words.append(word)
        elif word.endswith("ches") and len(word) > 4:
            singular_words.append(word[:-2])
        elif word.endswith("ies") and len(word) > 3:
            singular_words.append(f"{word[:-3]}y")
        elif word.endswith("s") and len(word) > 3:
            singular_words.append(word[:-1])
        else:
            singular_words.append(word)
    singular_key = " ".join(singular_words).strip()
    if singular_key:
        variants.add(singular_key)
    if key.endswith("ies") and len(key) > 3:
        variants.add(f"{key[:-3]}y")
    if key.endswith("ches") and len(key) > 4:
        variants.add(key[:-2])
    if key.endswith("men") and len(key) > 3:
        variants.add(f"{key[:-3]}man")
    if key.endswith("s") and len(key) > 1:
        variants.add(key[:-1])
    return {variant for variant in variants if variant}


def _composition_model_match_rank(item_label: object, model_label: object) -> tuple[int, int, str] | None:
    item_key = canonical_rules_key(item_label)
    model_key = canonical_rules_key(model_label)
    if not item_key or not model_key:
        return None
    if item_key == model_key:
        return (0, -len(model_key), model_key)
    item_variants = _model_name_variants(item_key)
    model_variants = _model_name_variants(model_key)
    if item_variants.intersection(model_variants):
        return (1, -len(model_key), model_key)
    # App-export model headings can include a model name plus a qualifier. Keep
    # this narrower than substring matching so "Dire Avenger" does not match
    # "Dire Avenger Exarch".
    qualifier_prefixes = ("with", "w", "equipped with")
    for variant in sorted(model_variants, key=len, reverse=True):
        for qualifier in qualifier_prefixes:
            if item_key.startswith(f"{variant} {qualifier} "):
                return (2, -len(model_key), model_key)
    for item_variant in sorted(item_variants, key=len, reverse=True):
        for model_variant in sorted(model_variants, key=len, reverse=True):
            if item_variant.endswith(f" {model_variant}"):
                return (3, -len(model_key), model_key)
            if model_variant.startswith(f"{item_variant} "):
                return (4, -len(model_key), model_key)
    return None


def _match_composition_model_name(current_unit: Unit, item_label: object, *, quantity: int) -> str | None:
    matches: list[tuple[tuple[int, int, str], str]] = []
    for model_name in current_unit.unit_composition.keys():
        model_label = str(model_name or "").strip()
        rank = _composition_model_match_rank(item_label, model_label)
        if rank is not None:
            matches.append((rank, model_label))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    matched_label = matches[0][1]
    resolve_model_name = getattr(current_unit, "_resolve_composition_model_name", None)
    if callable(resolve_model_name):
        return str(
            resolve_model_name(
                getattr(current_unit, "_datasheet", None),
                matched_label,
                model_count=quantity,
            )
        ).strip()
    return matched_label


def _unit_heading_name(line: str) -> str:
    text = str(line or "").strip()
    match = re.match(
        r"^(.*?)\s*(?:\(|\[)\s*[\d,]+\s*points?\s*(?:\]|\))",
        text,
        flags=re.IGNORECASE,
    )
    if match is not None:
        return match.group(1).strip()
    return text.split(" (")[0].strip()


def _apply_parsed_keyword_line(current_unit: Unit, data: str) -> None:
    if current_unit is None:
        return
    _, _, raw_keywords = str(data or "").partition(":")
    selected_keywords = [
        str(keyword or "").strip().upper()
        for keyword in re.split(r"[,;/]", raw_keywords)
        if str(keyword or "").strip()
    ]
    if not selected_keywords:
        return
    existing = [
        str(keyword or "").strip().upper()
        for keyword in list(getattr(current_unit, "keywords", []) or [])
        if str(keyword or "").strip()
    ]
    for keyword in selected_keywords:
        if keyword not in existing:
            existing.append(keyword)
    current_unit.keywords = existing
    build_metadata = dict(getattr(current_unit, "build_metadata", {}) or {})
    build_metadata.setdefault("parsed_keyword_selections", [])
    build_metadata["parsed_keyword_selections"].extend(selected_keywords)
    current_unit.build_metadata = build_metadata


def _apply_mark_of_chaos_line(current_unit: Unit, data: str) -> None:
    if current_unit is None:
        return
    _, _, raw_mark = str(data or "").partition(":")
    mark = str(raw_mark or "").strip()
    if not mark:
        return
    build_metadata = dict(getattr(current_unit, "build_metadata", {}) or {})
    build_metadata["mark_of_chaos"] = mark
    current_unit.build_metadata = build_metadata
    special_rules = getattr(current_unit, "special_rules", None)
    if not isinstance(special_rules, dict):
        special_rules = {}
    special_rules["mark_of_chaos"] = mark
    current_unit.special_rules = special_rules


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
    daemonic_allegiance: str | None = None,
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
            **(
                {"daemonic_allegiance": str(daemonic_allegiance or "").strip().upper()}
                if str(daemonic_allegiance or "").strip()
                and str(daemonic_allegiance or "").strip().upper() != "UNSET"
                else {}
            ),
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
    start_index = _first_section_index(stripped)
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
        try:
            faction_keyword, detachment_type = _plain_header_faction_and_detachment(
                stripped,
                section_index=start_index,
            )
        except ValueError as exc:
            raise ValueError(f"{exc} Army list: {file_path!r}") from exc

    logger.info(
        "Parsing army: %s - %s (%s points)",
        faction_keyword,
        detachment_type,
        points_limit,
    )

    army = Army.with_detachment(faction=faction_keyword, detachment_type=detachment_type, points_limit=points_limit)
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
        if not line or _is_section_header(line):
            continue
        if line.startswith("Exported with"):
            break

        is_detail_continuation = bool(
            current_unit is not None
            and not _is_bullet_line(line)
            and _looks_like_unit_detail_continuation(line)
        )
        if not _is_bullet_line(line) and not is_detail_continuation:
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
                    daemonic_allegiance=getattr(current_unit, "daemonic_allegiance", None),
                )
                current_unit = None
                current_model_name = None
                current_model_count = 0
                current_wargear = {}
                current_enhancement = None
                is_warlord = False

            current_model_name = None
            current_model_count = 0
            current_wargear = {}
            current_enhancement = None
            is_warlord = False
            unit_name = _unit_heading_name(line)
            ally_metadata: dict[str, str] = {}
            if faction_id:
                datasheet, ally_metadata = _resolve_pact_ally_datasheet(
                    waha_helper,
                    unit_name,
                    faction_id=faction_id,
                    detachment_type=detachment_type,
                )
                if not datasheet:
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
                _apply_pact_ally_metadata(current_unit, ally_metadata)
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
        if data.lower().startswith("mark of chaos:"):
            _apply_mark_of_chaos_line(current_unit, data)
            continue
        if re.search(r"\bkeywords?:", data, flags=re.IGNORECASE):
            _apply_parsed_keyword_line(current_unit, data)
            continue

        if "x " in data:
            quantity_text, item_name = data.split("x ", 1)
            quantity = int(quantity_text)
        else:
            quantity = 1
            item_name = data

        matched_model_name = None
        if current_unit:
            item_label = item_name.strip()
            matched_model_name = _match_composition_model_name(
                current_unit,
                item_label,
                quantity=quantity,
            )

        if matched_model_name:
            current_model_count += quantity
            current_model_name = matched_model_name
            current_wargear.setdefault(current_model_name, set())
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
            daemonic_allegiance=getattr(current_unit, "daemonic_allegiance", None),
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
    add_materialized_unit_to_army(
        army,
        unit,
        model_count,
        wargear_dict,
        enhancement,
        waha_helper,
        is_warlord,
        build_entry_id=build_entry_id,
    )
