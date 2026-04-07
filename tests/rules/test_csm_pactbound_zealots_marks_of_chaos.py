from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    toughness: str = "4",
    wounds: str = "3",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, phase_name: str):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Pactbound Zealots")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    phase_key = str(phase_name or "").strip().upper()
    phase = getattr(BattleRoundPhases, phase_key, None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_key)
    return game, csm_army, enemy_army


def _make_profile(*, weapon_type: str):
    melee = str(weapon_type).strip().lower() == "melee"
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_marks_of_chaos_assigns_default_chaos_undivided_during_validation():
    army = Army.with_detachment("Chaos Space Marines", "Pactbound Zealots")
    army.faction_id = "CSM"
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    army.add_unit(legionaries)

    army.validate_detachment_rules()

    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    assert sr.get("pactbound_zealots_mark") == "CHAOS UNDIVIDED"
    assert sr.get("pactbound_zealots_mark_source") == "Marks of Chaos"
    assert legionaries.has_any_keyword("CHAOS UNDIVIDED")


def test_marks_of_chaos_rejects_khorne_psyker_units():
    army = Army.with_detachment("Chaos Space Marines", "Pactbound Zealots")
    army.faction_id = "CSM"
    sorcerer = _make_unit(
        "Sorcerer",
        keywords=["HERETIC ASTARTES", "INFANTRY", "PSYKER", "KHORNE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    army.add_unit(sorcerer)

    with pytest.raises(ArmyValidationError, match="cannot have the KHORNE keyword"):
        army.validate_detachment_rules()


def test_character_attachment_requires_shared_mark():
    army = Army.with_detachment("Chaos Space Marines", "Pactbound Zealots")
    army.faction_id = "CSM"
    bodyguard = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    leader = _make_unit(
        "Chaos Lord",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    army.add_unit(leader)
    army.add_unit(bodyguard)

    leader.special_rules["pactbound_zealots_mark"] = "KHORNE"
    bodyguard.special_rules["pactbound_zealots_mark"] = "NURGLE"
    assert leader.can_attach_to(bodyguard) is False

    bodyguard.special_rules["pactbound_zealots_mark"] = "KHORNE"
    bodyguard.special_rules.pop("ability_added_keywords", None)
    assert leader.can_attach_to(bodyguard) is True


def test_transport_embark_requires_shared_mark():
    army = Army.with_detachment("Chaos Space Marines", "Pactbound Zealots")
    army.faction_id = "CSM"
    rhino = _make_unit(
        "Chaos Rhino",
        keywords=["HERETIC ASTARTES", "VEHICLE", "Transport"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    rhino.transport_capacity = 12
    army.add_unit(rhino)
    army.add_unit(legionaries)

    rhino.special_rules["pactbound_zealots_mark"] = "TZEENTCH"
    legionaries.special_rules["pactbound_zealots_mark"] = "SLAANESH"
    assert rhino.can_transport(legionaries) is False

    legionaries.special_rules["pactbound_zealots_mark"] = "TZEENTCH"
    legionaries.special_rules.pop("ability_added_keywords", None)
    assert rhino.can_transport(legionaries) is True


def test_marks_of_chaos_sets_crit_5_plus_for_khorne_with_lethal_hits_melee():
    game, army, enemy_army = _build_game(phase_name="FIGHT_PHASE")

    attacker_unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target_unit = _make_unit(
        "Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker_unit.special_rules["pactbound_zealots_mark"] = "KHORNE"
    attacker_unit.special_rules["dark_pacts_active"] = True
    attacker_unit.special_rules["dark_pacts_choice"] = "LETHAL HITS"
    attacker_unit.special_rules["dark_pacts_test_passed"] = True
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game.map.units = [attacker_unit, target_unit]
    game.rebuild_entity_registry()

    profile = _make_profile(weapon_type="melee")
    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 6)) == 5


def test_marks_of_chaos_sets_crit_5_plus_for_nurgle_with_sustained_hits_ranged():
    game, army, enemy_army = _build_game(phase_name="SHOOTING_PHASE")

    attacker_unit = _make_unit(
        "Havocs",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target_unit = _make_unit(
        "Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker_unit.special_rules["pactbound_zealots_mark"] = "NURGLE"
    attacker_unit.special_rules["dark_pacts_active"] = True
    attacker_unit.special_rules["dark_pacts_choice"] = "SUSTAINED HITS 1"
    attacker_unit.special_rules["dark_pacts_test_passed"] = True
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game.map.units = [attacker_unit, target_unit]
    game.rebuild_entity_registry()

    profile = _make_profile(weapon_type="ranged")
    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 6)) == 5


def test_marks_of_chaos_grants_chaos_undivided_reroll_hit_ones():
    game, army, enemy_army = _build_game(phase_name="SHOOTING_PHASE")

    attacker_unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target_unit = _make_unit(
        "Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker_unit.special_rules["pactbound_zealots_mark"] = "CHAOS UNDIVIDED"
    attacker_unit.special_rules["dark_pacts_active"] = True
    attacker_unit.special_rules["dark_pacts_choice"] = "LETHAL HITS"
    attacker_unit.special_rules["dark_pacts_test_passed"] = True
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game.map.units = [attacker_unit, target_unit]
    game.rebuild_entity_registry()

    profile = _make_profile(weapon_type="ranged")
    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Marks of Chaos" in reason for reason in list(hit_result.get("reroll_value_reasons", []) or []))


def test_marks_of_chaos_requires_dark_pacts_test_success_for_bonuses():
    game, army, enemy_army = _build_game(phase_name="FIGHT_PHASE")

    attacker_unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target_unit = _make_unit(
        "Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker_unit.special_rules["pactbound_zealots_mark"] = "KHORNE"
    attacker_unit.special_rules["dark_pacts_active"] = True
    attacker_unit.special_rules["dark_pacts_choice"] = "LETHAL HITS"
    attacker_unit.special_rules["dark_pacts_test_passed"] = False
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game.map.units = [attacker_unit, target_unit]
    game.rebuild_entity_registry()

    profile = _make_profile(weapon_type="melee")
    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 6)) == 6
