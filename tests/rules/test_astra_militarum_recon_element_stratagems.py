from __future__ import annotations

import copy
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: int = 3,
        base_size: str = "32mm",
        transport: str = "",
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10" if "VEHICLE" in set(self.keywords) else "6",
                "T": "10" if "VEHICLE" in set(self.keywords) else "4",
                "Sv": "3" if "VEHICLE" in set(self.keywords) else "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3" if "VEHICLE" in set(self.keywords) else "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


class _ArrivingUnit:
    def __init__(self, army):
        self._army = army
        self.models = [
            Model(
                name="Arriving",
                movement=6,
                toughness=4,
                save=4,
                wounds=2,
                leadership=7,
                objective_control=1,
                model_base=Base(BaseType.CIRCULAR, 1.0),
            )
        ]

    def get_parent_army(self):
        return self._army

    def is_in_strategic_reserves(self):
        return False

    def has_deep_strike(self):
        return True

    def calculate_model_positions(self, x, y, _game_map, **_kwargs):
        return [(x, y, 0.0, 0.0)]

    def _create_potential_base(self, x, y, z, facing, model):
        base = copy.deepcopy(model.model_base)
        base.set_position(x, y, z)
        base.set_facing(facing)
        return base


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: int = 3,
    base_size: str = "32mm",
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            base_size=base_size,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _ranged_wargear(name: str = "Longlas") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    am_army = Army.with_detachment("Astra Militarum", "Recon Element")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=PlayerControl.LOCAL, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    am_player.command_points = 10
    enemy_player.command_points = 10
    return game, am_player, enemy_player, am_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _find_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def test_recon_element_stratagem_descriptors_registered():
    expected = {
        "000009870005": ("Courageous Diversion", "feel_no_pain"),
        "000009870002": ("Crack Shots", "grant_precision_to_unit_weapons"),
        "000009870003": ("Draw Them Out", "reactive_normal_move_up_to_6"),
        "000009870007": ("Scouting Outriders", "enter_strategic_reserves"),
        "000009870004": ("Scramble Field", "reinforcements_setup_denial"),
        "000009870006": ("Tanglefoot Grenades", "enemy_charge_roll_modifier_non_cumulative_negative"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_crack_shots_grants_precision_and_cleans_up():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    shooters = _make_unit("Ratlings", keywords=["INFANTRY", "PLATOON", "REGIMENT"])
    shooters.models[0].wargear = [_ranged_wargear()]
    am_army.add_unit(shooters)
    _deploy_unit(game, shooters, 10.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("CRACK SHOTS", unit=shooters, phase_name="Shooting phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    bonuses = list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Longlas") or [])
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "PRECISION"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in bonuses
    )

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Longlas") or []) == []


def test_courageous_diversion_grants_fnp_and_hit_penalty_only_when_closest():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    protected = _make_unit("Scout Riders", keywords=["MOUNTED"])
    closer_unit = _make_unit("Infantry Screen", keywords=["INFANTRY", "REGIMENT"])
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_weapon = _ranged_wargear("Enemy Rifle")
    enemy.models[0].wargear = [enemy_weapon]
    am_army.add_unit(protected)
    am_army.add_unit(closer_unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 2.0, 10.0)
    _deploy_unit(game, closer_unit, 8.0, 10.0)
    _deploy_unit(game, protected, 14.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    pending = _pending_by_name(am_player.stratagems, "COURAGEOUS DIVERSION")
    assert pending is not None

    ok = am_player.stratagems.use(
        "COURAGEOUS DIVERSION",
        unit=protected,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert (6, None) in list(protected.models[0].get_temporary_fnp_entries() or [])

    profile = enemy_weapon.profiles["default"]
    not_closest = profile._hit_target_with_tracking(
        protected,
        enemy.models[0],
        {"attacker_model": enemy.models[0], "attacker_unit": enemy},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(not_closest.get("final_needed", 0) or 0) == 4
    assert not any("COURAGEOUS DIVERSION" in str(text or "") for text in list(not_closest.get("modifiers", []) or []))

    closer_unit.models[0].set_location(40.0, 10.0, 0.0, 0.0)
    closest = profile._hit_target_with_tracking(
        protected,
        enemy.models[0],
        {"attacker_model": enemy.models[0], "attacker_unit": enemy},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(closest.get("final_needed", 0) or 0) == 5
    assert any("COURAGEOUS DIVERSION" in str(text or "") for text in list(closest.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(protected.models[0].get_temporary_fnp_entries() or []) == []


def test_draw_them_out_queues_reactive_move_after_enemy_move_end():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    platoon = _make_unit("Shock Troops", keywords=["INFANTRY", "PLATOON", "REGIMENT"])
    enemy = _make_unit("Enemy Movers", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(platoon)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, platoon, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    pending = _pending_by_name(am_player.stratagems, "DRAW THEM OUT")
    assert pending is not None
    assert platoon in list(pending.get("candidates") or [])

    ok = am_player.stratagems.use(
        "DRAW THEM OUT",
        unit=platoon,
        enemy_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True

    request = _find_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert int(ctx.get("max_distance", 0) or 0) == 6
    assert str(ctx.get("reactive_move_source", "") or "") == "DRAW THEM OUT"


def test_scramble_field_queues_during_enemy_reinforcements_step_and_blocks_reserves_setup():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    screen = _make_unit("Recon Screen", keywords=["INFANTRY", "REGIMENT"])
    am_army.add_unit(screen)
    _deploy_unit(game, screen, 10.0, 10.0)
    game.turn = 2
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.handle_reserves_arrival_phase()

    pending = _pending_by_name(am_player.stratagems, "SCRAMBLE FIELD")
    assert pending is not None

    ok = am_player.stratagems.use(
        "SCRAMBLE FIELD",
        unit=screen,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    arriving = _ArrivingUnit(enemy_army)
    assert game.can_place_unit_arriving_from_reserves(arriving, (21.0, 10.0, 0.0)) is False
    assert game.can_place_unit_arriving_from_reserves(arriving, (24.0, 10.0, 0.0)) is True

    game.end_reinforcements_step()
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert game.can_place_unit_arriving_from_reserves(arriving, (21.0, 10.0, 0.0)) is True


def test_tanglefoot_grenades_applies_non_cumulative_charge_penalty_and_cleans_up():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    grenadiers = _make_unit("Kasrkin", keywords=["INFANTRY", "GRENADES"])
    charger = _make_unit("Enemy Chargers", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(grenadiers)
    enemy_army.add_unit(charger)
    _deploy_unit(game, grenadiers, 12.0, 10.0)
    _deploy_unit(game, charger, 6.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    charger._can_declare_charge_base = lambda _game, out_of_turn=False: True
    charger.can_declare_charge_against = lambda target, _game, out_of_turn=False: target is grenadiers

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    pending = _pending_by_name(am_player.stratagems, "TANGLEFOOT GRENADES")
    assert pending is not None

    ok = am_player.stratagems.use(
        "TANGLEFOOT GRENADES",
        unit=grenadiers,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    charger_sr = dict(getattr(charger, "special_rules", {}) or {})
    charger_sr.setdefault("charge_roll_modifiers", []).append({"value": -1, "source": "Other penalty"})
    charger.special_rules = charger_sr

    declared = game.declare_charge(charger, [grenadiers])
    assert declared is not None

    roll_state = game.roll_manager.get_roll(int(declared.get("roll_id", 0) or 0))
    assert roll_state is not None
    roll_spec = dict(getattr(roll_state, "spec", {}) or {})
    assert int(roll_spec.get("sum_modifier", 0) or 0) == -2
    assert any("TANGLEFOOT GRENADES" in str(text or "") for text in list(roll_spec.get("sum_modifier_reasons", []) or []))

    charge_mods = list((dict(getattr(charger, "special_rules", {}) or {})).get("charge_roll_modifiers", []) or [])
    assert any(
        isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "astra_militarum_tanglefoot_grenades"
        for entry in charge_mods
    )

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    charge_mods_after = list((dict(getattr(charger, "special_rules", {}) or {})).get("charge_roll_modifiers", []) or [])
    assert not any(
        isinstance(entry, dict) and str(entry.get("source_key", "") or "") == "astra_militarum_tanglefoot_grenades"
        for entry in charge_mods_after
    )


def test_scouting_outriders_queues_at_opponent_fight_phase_end_and_enters_strategic_reserves():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    outriders = _make_unit("Rough Riders", keywords=["MOUNTED"])
    am_army.add_unit(outriders)
    _deploy_unit(game, outriders, 5.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(am_player.stratagems, "SCOUTING OUTRIDERS")
    assert pending is not None

    ok = am_player.stratagems.use(
        "SCOUTING OUTRIDERS",
        unit=outriders,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert str(getattr(outriders, "reserve_status", "") or "") == "strategic_reserves"
    assert outriders not in list(getattr(game.map, "units", []) or [])
