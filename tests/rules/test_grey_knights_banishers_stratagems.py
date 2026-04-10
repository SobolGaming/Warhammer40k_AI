from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _ranged_wargear(name: str = "Storm Bolter") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    army_gk = Army.with_detachment("Grey Knights", "Banishers")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 6
    p2.command_points = 6
    army_gk.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_gk, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems, *, clear: bool = False) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=clear) or [])
    }


def test_banishers_stratagem_descriptors_registered():
    expected = {
        "000010357002": ("Hexwrought Reprisal", "reflect_mortal_wounds_as_psychic"),
        "000010357003": ("Warding Chant", "feel_no_pain_against_damage_1"),
        "000010357004": ("Chaos Bane", "grant_ranged_anti_chaos_4plus"),
        "000010357005": ("Celerity", "charge_after_advance"),
        "000010357006": ("Circle of Sanctuary", "reserves_denial_aura"),
        "000010357007": ("Shadow of Anarch", "reactive_move_or_enter_strategic_reserves_if_deep_strike"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_banishers_phase_start_reactions_queue_celerity_chaos_bane_and_circle():
    game, p1, p2, army_gk, _army_enemy = _build_game()
    chaos_bane_unit = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    celerity_unit = _make_unit(
        "Interceptor Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    celerity_unit.round_state.advanced_this_round = True
    character = _make_unit(
        "Brother-Captain",
        keywords=["CHARACTER", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    army_gk.add_unit(chaos_bane_unit)
    army_gk.add_unit(celerity_unit)
    army_gk.add_unit(character)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"CHAOS BANE"}

    _set_phase(game, p1, "CHARGE_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"CELERITY"}

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    assert _pending_names(p1.stratagems, clear=True) == {"CIRCLE OF SANCTUARY"}


def test_chaos_bane_grants_anti_chaos_keyword_until_phase_end():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Chaos Marines",
        keywords=["INFANTRY", "CHAOS"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    psyker.models[0].wargear = [weapon]
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "CHAOS BANE")
    assert pending is not None

    ok = p1.stratagems.use(
        "CHAOS BANE",
        unit=psyker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    bonus = psyker.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=psyker.models[0],
        weapon_profile=weapon.profiles["default"],
    )
    assert ("CHAOS", 4) in list(bonus.get("anti_specs") or [])

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    bonus_after = psyker.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=psyker.models[0],
        weapon_profile=weapon.profiles["default"],
    )
    assert ("CHAOS", 4) not in list(bonus_after.get("anti_specs") or [])


def test_celerity_allows_charge_after_advance_until_turn_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    psyker = _make_unit(
        "Interceptor Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    psyker.round_state.advanced_this_round = True
    army_gk.add_unit(psyker)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "CHARGE_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "CELERITY")
    assert pending is not None

    ok = p1.stratagems.use(
        "CELERITY",
        unit=psyker,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok
    assert psyker.can_charge_after_advance() is True

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert psyker.can_charge_after_advance() is False


def test_circle_of_sanctuary_registers_reserves_denial_for_selected_character_model():
    game, p1, p2, army_gk, _army_enemy = _build_game()
    character = _make_unit(
        "Brother-Captain",
        keywords=["CHARACTER", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    army_gk.add_unit(character)
    _deploy_unit(game, character, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    pending = _pending_by_name(p1.stratagems, "CIRCLE OF SANCTUARY")
    assert pending is not None

    ok = p1.stratagems.use(
        "CIRCLE OF SANCTUARY",
        unit=character,
        target_model=character.models[0],
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok

    game.reinforcements_step_active = True
    game.reinforcements_step_turn = game.turn
    game.reinforcements_step_player_id = p2.id
    ranges = list(game._reserves_denial_ranges_for_unit(character) or [])
    assert ranges
    entry = next(item for item in ranges if str(item.get("source", "") or "").upper() == "CIRCLE OF SANCTUARY")
    assert float(entry.get("range", 0.0) or 0.0) == 12.0
    assert bool(entry.get("horizontal_only", False)) is True
    assert str(entry.get("source_model_id", "") or "") == str(get_entity_id(character.models[0]) or "")


def test_warding_chant_applies_temporary_fnp_against_damage_one_attacks():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    enemy.models[0].wargear = [weapon]
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[psyker])
    pending = _pending_by_name(p1.stratagems, "WARDING CHANT")
    assert pending is not None

    ok = p1.stratagems.use(
        "WARDING CHANT",
        unit=psyker,
        attacking_unit=enemy,
        target_units=[psyker],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok

    fnp_entries = list(psyker.models[0].get_temporary_fnp_entries() or [])
    assert fnp_entries
    assert any(int(value or 0) == 5 for value, _condition in fnp_entries)
    condition = next(str(cond or "") for value, cond in fnp_entries if int(value or 0) == 5)
    profile = weapon.profiles["default"]
    assert psyker.models[0]._check_fnp_condition(
        condition,
        profile,
        False,
        attack_context={"attack_instance": {"damage_characteristic": 1}},
        attacker_unit=enemy,
    )
    assert not psyker.models[0]._check_fnp_condition(
        condition,
        profile,
        False,
        attack_context={"attack_instance": {"damage_characteristic": 2}},
        attacker_unit=enemy,
    )


def test_shadow_of_anarch_can_enter_strategic_reserves_if_target_has_deep_strike():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Interceptor Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Movers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(p1.stratagems, "SHADOW OF ANARCH")
    assert pending is not None

    ok = p1.stratagems.use(
        "SHADOW OF ANARCH",
        unit=psyker,
        enemy_unit=enemy,
        action="move",
        choice_key="STRATEGIC_RESERVES",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert str(getattr(psyker, "reserve_status", "") or "") == "strategic_reserves"


def test_shadow_of_anarch_queues_reactive_move_when_not_using_reserves():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Movers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(p1.stratagems, "SHADOW OF ANARCH")
    assert pending is not None

    ok = p1.stratagems.use(
        "SHADOW OF ANARCH",
        unit=psyker,
        enemy_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok

    move_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
        and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "grey_knights_shadow_of_anarch"
        and str((getattr(req, "context", {}) or {}).get("unit_id", "") or "") == str(get_entity_id(psyker) or "")
    ]
    assert move_requests


def test_hexwrought_reprisal_tracks_mortal_wounds_and_reflects_psychic_mortals():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=10,
    )
    enemy = _make_unit(
        "Enemy Sorcerers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    enemy._apply_mortal_wounds_to_unit(
        target,
        7,
        game_map=game.map,
        attacker_unit=enemy,
    )
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    pending = _pending_by_name(p1.stratagems, "HEXWROUGHT REPRISAL")
    assert pending is not None
    assert target in list(pending.get("candidates") or [])
    assert enemy is pending.get("enemy_unit")

    with patch("warhammer40k_ai.rules.stratagems_grey_knights.dice_module.get_roll", return_value=6):
        ok = p1.stratagems.use(
            "HEXWROUGHT REPRISAL",
            unit=target,
            enemy_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
    assert ok
    assert int(enemy.models[0].wounds or 0) == 4
