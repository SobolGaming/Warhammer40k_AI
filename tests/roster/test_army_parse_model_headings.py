from __future__ import annotations

import logging
from collections import Counter

from warhammer40k_ai.roster.army import parse_army_list_text
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper import WahaHelper


def test_configure_models_preserves_required_later_composition_rows() -> None:
    waha = WahaHelper(data_dir="wahapedia_data")
    datasheet = waha.get_full_datasheet_info_by_name("Crusader Squad", faction_id="SM")
    unit = Unit(datasheet)

    unit.configure_models(10, [])

    assert Counter(model.name for model in unit.models) == {
        "Sword Brother": 1,
        "Initiate": 5,
        "Neophyte": 4,
    }


def test_army_parser_maps_singular_model_headings_to_runtime_model_names() -> None:
    roster = """Black Templars Test (150 Points)

Black Templars
Wrathful Procession
Strike Force (150 Points)

BATTLELINE

Crusader Squad (150 Points)
  • 1x Sword Brother
     ◦ 1x Heavy bolt pistol
     ◦ 1x Master-crafted power weapon
  • 5x Initiate
     ◦ 5x Bolt pistol
     ◦ 5x Bolt rifle
     ◦ 5x Close combat weapon
  • 4x Neophyte
     ◦ 4x Astartes chainsword
     ◦ 4x Bolt pistol

Exported with app version: Warhammer40k_AI Roster Synthesizer
"""
    army = parse_army_list_text(roster, WahaHelper(data_dir="wahapedia_data"), list_name="bt_crusader")

    [unit] = army.units
    assert unit.name == "Crusader Squad"
    assert Counter(model.name for model in unit.models) == {
        "Sword Brother": 1,
        "Initiate": 5,
        "Neophyte": 4,
    }
    assert army.get_total_points() == 150


def _wargear_counts_by_model(unit) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {}
    for model in list(getattr(unit, "models", []) or []):
        model_name = str(getattr(model, "name", "") or "")
        bucket = counts.setdefault(model_name, Counter())
        for wargear in list(getattr(model, "wargear", []) or []):
            bucket[str(getattr(wargear, "name", "") or "")] += 1
    return counts


def test_army_parser_does_not_match_regular_model_headings_to_exarchs() -> None:
    roster = """Aeldari Test (255 Points)

Aeldari
Aspect Host
Strike Force (255 Points)

OTHER DATASHEETS

Dire Avengers (150 Points)
  \u2022 2x Aspect Shrine Token
  \u2022 1x Dire Avenger Exarch
     \u25e6 2x Avenger shuriken catapult
     \u25e6 1x Close combat weapon
  \u2022 9x Dire Avenger
     \u25e6 9x Avenger shuriken catapult
     \u25e6 9x Close combat weapon

Warp Spiders (105 Points)
  \u2022 1x Aspect Shrine Token
  \u2022 1x Warp Spider Exarch
     \u25e6 1x Close combat weapon
     \u25e6 1x Powerblade array
  \u2022 4x Warp Spider
     \u25e6 4x Close combat weapon
     \u25e6 4x Death spinner

Exported with app version: Warhammer40k_AI Roster Synthesizer
"""
    army = parse_army_list_text(roster, WahaHelper(data_dir="wahapedia_data"), list_name="aeldari_exarchs")
    assert army.get_primary_detachment_type() == "Aspect Host"

    dire_avengers = next(unit for unit in army.units if unit.name == "Dire Avengers")
    dire_counts = _wargear_counts_by_model(dire_avengers)
    assert Counter(model.name for model in dire_avengers.models) == {
        "Dire Avenger Exarch": 1,
        "Dire Avenger": 9,
    }
    assert dire_counts["Dire Avenger Exarch"] == {
        "Avenger shuriken catapult": 2,
        "Close combat weapon": 1,
    }
    assert dire_counts["Dire Avenger"] == {
        "Avenger shuriken catapult": 9,
        "Close combat weapon": 9,
    }

    warp_spiders = next(unit for unit in army.units if unit.name == "Warp Spiders")
    warp_counts = _wargear_counts_by_model(warp_spiders)
    assert Counter(model.name for model in warp_spiders.models) == {
        "Warp Spider Exarch": 1,
        "Warp Spider": 4,
    }
    assert warp_counts["Warp Spider Exarch"] == {
        "Close combat weapon": 1,
        "Powerblade array": 1,
    }
    assert warp_counts["Warp Spider"] == {
        "Close combat weapon": 4,
        "Death spinner": 4,
    }


def test_army_parser_keeps_missing_bullet_wargear_with_current_model_heading() -> None:
    roster = """Space Marines
Blood Angels
Strike Force (500 points)
Liberator Assault Group

CHARACTERS

Captain with Jump Pack (100 points)
\u2022 1x Hand flamer
1x Power fist
\u2022 Enhancement: Speed of the Primarch

Commander Dante (120 points)
\u2022 Warlord
\u2022 1x Perdition Pistol
1x The Axe Mortalis

BATTLELINE

Intercessor Squad (80 points)
\u2022 1x Intercessor Sergeant
\u2022 1x Astartes grenade launcher
1x Bolt pistol
1x Bolt rifle
1x Power fist
\u2022 4x Intercessor
\u2022 4x Bolt pistol
4x Bolt rifle
4x Close combat weapon

OTHER DATASHEETS

Death Company Marines with Jump Packs (230 points)
\u2022 10x Death Company Marine with Jump Packs
\u2022 5x Astartes chainsword
2x Eviscerator
6x Heavy bolt pistol
2x Inferno pistol
2x Plasma pistol
3x Power fist
"""
    army = parse_army_list_text(
        roster,
        WahaHelper(data_dir="wahapedia_data"),
        list_name="blood_angels_missing_bullets",
    )

    assert army.get_primary_detachment_type() == "Liberator Assault Group"
    assert army.get_total_points() == 530

    captain = next(unit for unit in army.units if unit.name == "Captain With Jump Pack")
    assert getattr(captain, "enhancement", None) is not None
    assert captain.enhancement.name == "Speed of the Primarch"
    captain_counts = _wargear_counts_by_model(captain)
    assert captain_counts["Captain with Jump Pack"] == {
        "Hand flamer": 1,
        "Power fist": 1,
    }

    dante = next(unit for unit in army.units if unit.name == "Commander Dante")
    assert getattr(dante, "enhancement", None) is None
    assert dante.is_warlord is True
    dante_counts = _wargear_counts_by_model(dante)
    assert dante_counts["Commander Dante"] == {
        "Perdition Pistol": 1,
        "The Axe Mortalis": 1,
    }

    intercessors = next(unit for unit in army.units if unit.name == "Intercessor Squad")
    intercessor_counts = _wargear_counts_by_model(intercessors)
    assert Counter(model.name for model in intercessors.models) == {
        "Intercessor Sergeant": 1,
        "Intercessor": 4,
    }
    assert intercessor_counts["Intercessor Sergeant"] == {
        "Astartes grenade launcher": 1,
        "Bolt pistol": 1,
        "Bolt rifle": 1,
        "Power fist": 1,
    }
    assert intercessor_counts["Intercessor"] == {
        "Bolt pistol": 4,
        "Bolt rifle": 4,
        "Close combat weapon": 4,
    }

    death_company = next(unit for unit in army.units if unit.name == "Death Company Marines With Jump Packs")
    death_company_counts = _wargear_counts_by_model(death_company)
    assert Counter(model.name for model in death_company.models) == {
        "Death Company Marines with Jump Pack": 10,
    }
    assert death_company_counts["Death Company Marines with Jump Pack"] == {
        "Astartes chainsword": 5,
        "Eviscerator": 2,
        "Heavy bolt pistol": 6,
        "Inferno pistol": 2,
        "Plasma pistol": 2,
        "Power fist": 3,
    }


def test_army_parser_resolves_tournament_wargear_aliases_without_warnings(
    caplog,
) -> None:
    roster = """Tau Empire
Mont'ka
Strike Force (400 points)

OTHER DATASHEETS

Breacher Team (90 points)
- 1x Breacher Fire Warrior Shas'ui
  - 1x Close combat weapon
  - 1x Guardian drone
  - 1x Gun drone with twin pulse carbine
  - 1x Pulse blaster
  - 1x Pulse pistol
- 9x Breacher Fire Warriors
  - 9x Close combat weapon
  - 9x Pulse blaster
  - 9x Pulse pistol

Devilfish (85 points)
- 1x Devilfish
  - 2x Seeker missiles
  - 2x Twin pulse carbines
  - 1x Accelerator burst cannon
  - 1x Armoured hull

Kroot War Shaper (75 points)
- 1x Kroot War Shaper
  - 1x Dart-bow & tri-blade
  - 1x Kroot pistol
  - 1x Shaper's blade

Pathfinder Team (90 points)
- 1x Pathfinder Shas'ui
  - 1x Close combat weapon
  - 1x Recon drone with burst cannon
  - 1x Gun drone with twin pulse carbine
  - 1x Pulse carbine
  - 1x Pulse pistol
- 6x Pathfinders
  - 6x Close combat weapon
  - 6x Pulse carbine
  - 6x Pulse pistol
- 3x Pathfinders
  - 3x Close combat weapon
  - 3x Ion rifle
  - 3x Pulse pistol
"""
    with caplog.at_level(logging.WARNING):
        army = parse_army_list_text(
            roster,
            WahaHelper(data_dir="wahapedia_data"),
            list_name="tau_tournament_aliases",
        )

    assert army.faction_id == "TAU"
    assert army.get_total_points() == 315
    assert not [
        record
        for record in caplog.records
        if "not found in" in record.getMessage()
        or "Datasheet not found" in record.getMessage()
    ]


def test_army_parser_handles_tournament_metadata_lines_without_unit_leaks(caplog) -> None:
    roster = """Chaos Space Marines
Pactbound Zealots
Strike Force (50 points)

BATTLELINE

Cultist Mob (50 points)
Mark of Chaos: Nurgle
1x Cultist Champion
1x Bolt pistol
1x Brutal assault weapon
9x Chaos Cultist
9x Autopistol
9x Brutal assault weapon

"""
    with caplog.at_level(logging.WARNING):
        army = parse_army_list_text(
            roster,
            WahaHelper(data_dir="wahapedia_data"),
            list_name="csm_tournament_metadata",
        )

    cultists = next(unit for unit in army.units if unit.name == "Cultist Mob")
    assert cultists.special_rules["mark_of_chaos"] == "Nurgle"
    assert not [
        record
        for record in caplog.records
        if "Mark of Chaos" in record.getMessage()
        or "not found in" in record.getMessage()
        or "Datasheet not found" in record.getMessage()
    ]


def test_army_parser_applies_tournament_keyword_selection_before_warlord() -> None:
    roster = """Chaos Knights
Houndpack Lance
Strike Force (150 points)

CHARACTERS

War Dog Stalker (150 points)
Houndpack Lance Keyword: Character
Warlord
1x Avenger chaincannon
1x Diabolus heavy stubber
1x Reaper chaintalon
"""
    army = parse_army_list_text(
        roster,
        WahaHelper(data_dir="wahapedia_data"),
        list_name="chaos_knights_keyword_selection",
    )

    [stalker] = army.units
    assert stalker.is_character is True
    assert stalker.is_warlord is True


def test_army_parser_matches_accented_suffix_model_headings_without_warnings(caplog) -> None:
    roster = """Leagues of Votann
Hearthband
Strike Force (215 points)

OTHER DATASHEETS

Brôkhyr Thunderkyn (80 points)
- 3x Brôkhyr Thunderkyn
- 3x Close combat weapon
3x Graviton blast cannon

Einhyr Hearthguard (135 points)
- 1x Hesyr
- 1x EtaCarn plasma gun
1x Exoarmour grenade launcher
1x Graviton hammer
1x Teleport Crest
- 4x Einhyr Hearthguard
- 4x Concussion gauntlet
4x EtaCarn plasma gun
4x Exoarmour grenade launcher
"""
    with caplog.at_level(logging.WARNING):
        army = parse_army_list_text(
            roster,
            WahaHelper(data_dir="wahapedia_data"),
            list_name="votann_tournament_suffix_models",
        )

    hearthguard = next(unit for unit in army.units if unit.name == "Einhyr Hearthguard")
    assert Counter(model.name for model in hearthguard.models) == {
        "Hesyr": 1,
        "Hearthguard": 4,
    }
    assert not [
        record
        for record in caplog.records
        if "not found in" in record.getMessage()
        or "Datasheet not found" in record.getMessage()
    ]


def test_army_parser_resolves_wargear_abilities_before_ambiguous_options(caplog) -> None:
    roster = """Imperial Agents
Imperialis Fleet
Strike Force (190 points)

BATTLELINE

Deathwatch Kill Team (190 points)
- 1x Watch Sergeant
- 1x Combi-weapon
1x Xenophase blade
- 9x Deathwatch Veterans
- 2x Astartes shield
1x Black Shield blades
2x Deathwatch thunder hammer
2x Power weapon
"""
    with caplog.at_level(logging.WARNING):
        army = parse_army_list_text(
            roster,
            WahaHelper(data_dir="wahapedia_data"),
            list_name="deathwatch_ability_wargear",
        )

    [kill_team] = army.units
    assert kill_team.name == "Deathwatch Kill Team"
    assert not [
        record
        for record in caplog.records
        if "astartes shield" in record.getMessage().lower()
        or "not found in" in record.getMessage()
        or "Datasheet not found" in record.getMessage()
    ]


def test_army_parser_keeps_wargear_ability_equipped_for_runtime_rules() -> None:
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    roster = """WE Daemonkin (90 Points)

World Eaters
Khorne Daemonkin
Strike Force (90 Points)

BATTLELINE

Bloodletters (90 Points)
  \u2022 1x Bloodreaper
     \u25e6 1x Hellblade
  \u2022 9x Bloodletter
     \u25e6 1x Daemonic Icon
     \u25e6 9x Hellblade
     \u25e6 1x Instrument of Chaos

Exported with App Version: v1.36.1 (1), Data Version: v640
"""
    army = parse_army_list_text(
        roster,
        WahaHelper(data_dir="wahapedia_data"),
        list_name="world_eaters_instrument_wargear",
    )

    [bloodletters] = army.units
    assert bloodletters._has_wargear_named("Instrument of Chaos") is True

    charge_mods = list((getattr(bloodletters, "special_rules", {}) or {}).get("charge_roll_modifiers", []) or [])
    assert any(
        isinstance(mod, dict)
        and mod.get("value") == 1
        and mod.get("source") == "Instrument of Chaos"
        for mod in charge_mods
    )
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    assert game.get_charge_roll_modifiers(bloodletters) == [(1, "Instrument of Chaos")]
