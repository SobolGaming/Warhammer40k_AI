from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, ORDER_TAKE_AIM
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        datasheet_id: str | None = None,
        attached_to=None,
        model_count: int = 1,
        move: int = 6,
        toughness: int = 4,
        save: int = 4,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ) -> None:
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _ability(name: str, description: str = "", ability_type: str = "Datasheet") -> dict:
    return {
        "name": name,
        "description": description,
        "type": ability_type,
        "parameter": "",
    }


def _voice_of_command_abilities(order_text: str) -> list[dict]:
    return [
        _ability("Voice of Command", "Voice of Command", "Army"),
        _ability("Orders", order_text),
    ]


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    datasheet_id: str | None = None,
    attached_to=None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 4,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            datasheet_id=datasheet_id,
            attached_to=attached_to,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    return unit


def _build_game(detachment: str, *, control: PlayerControl = PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    am_army = Army.with_detachment("Astra Militarum", detachment)
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=control, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    am_player.command_points = 5
    enemy_player.command_points = 5
    am_army.configure_rule_managers(force=True)
    am_player.stratagems.refresh_available()
    return game, am_player, enemy_player, am_army, enemy_army


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
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _destroy_unit(unit: Unit) -> None:
    unit.models = []


def test_inspired_command_allows_extra_order_after_regular_capacity_used_this_battle_round():
    game, am_player, enemy_player, am_army, _enemy_army = _build_game("Combined Arms")
    officer = _make_unit(
        "Cadian Castellan",
        keywords=["OFFICER", "REGIMENT", "ASTRA MILITARUM"],
        abilities=_voice_of_command_abilities('This model can issue 1 Order to REGIMENT units within 6".'),
    )
    target_a = _make_unit("Infantry Squad A", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"])
    target_b = _make_unit("Infantry Squad B", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"])
    am_army.add_unit(officer)
    am_army.add_unit(target_a)
    am_army.add_unit(target_b)
    _deploy_unit(game, officer, 10.0, 10.0)
    _deploy_unit(game, target_a, 12.0, 10.0)
    _deploy_unit(game, target_b, 12.0, 12.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    assert am_army.voice_of_command.issue_order(game, officer, target_a, ORDER_MOVE.key, phase_name="COMMAND_PHASE")

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert am_player.stratagems.use(
        "INSPIRED COMMAND",
        officer_unit=officer,
        order_target_unit=target_b,
        order_key=ORDER_MOVE.key,
        phase_name="Command phase",
    )
    assert ORDER_MOVE.key in list(am_army.voice_of_command.get_active_order_keys(target_b) or [])


def test_snap_to_it_allows_extra_order_after_regular_capacity_used_this_battle_round():
    game, am_player, _enemy_player, am_army, _enemy_army = _build_game("Grizzled Company")
    officer = _make_unit(
        "Officer",
        keywords=["OFFICER", "ASTRA MILITARUM"],
        abilities=_voice_of_command_abilities('This model can issue 1 Order to REGIMENT units within 6".'),
    )
    target_a = _make_unit("Infantry A", keywords=["REGIMENT", "ASTRA MILITARUM"])
    target_b = _make_unit("Infantry B", keywords=["REGIMENT", "ASTRA MILITARUM"])
    am_army.add_unit(officer)
    am_army.add_unit(target_a)
    am_army.add_unit(target_b)
    _deploy_unit(game, officer, 10.0, 10.0)
    _deploy_unit(game, target_a, 12.0, 10.0)
    _deploy_unit(game, target_b, 12.0, 12.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    assert am_army.voice_of_command.issue_order(game, officer, target_a, ORDER_MOVE.key, phase_name="COMMAND_PHASE")

    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)
    assert am_player.stratagems.use(
        "SNAP TO IT",
        officer_unit=officer,
        order_target_unit=target_b,
        order_key=ORDER_MOVE.key,
        phase_name="Movement phase",
    )
    assert ORDER_MOVE.key in list(am_army.voice_of_command.get_active_order_keys(target_b) or [])


def test_same_order_multiple_times_does_not_stack():
    game, am_player, _enemy_player, am_army, _enemy_army = _build_game("Combined Arms")
    officer_a = _make_unit(
        "Officer A",
        keywords=["OFFICER", "REGIMENT", "ASTRA MILITARUM"],
        abilities=_voice_of_command_abilities('This model can issue 1 Order to REGIMENT units within 6".'),
    )
    officer_b = _make_unit(
        "Officer B",
        keywords=["OFFICER", "REGIMENT", "ASTRA MILITARUM"],
        abilities=_voice_of_command_abilities('This model can issue 1 Order to REGIMENT units within 6".'),
    )
    target = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"])
    am_army.add_unit(officer_a)
    am_army.add_unit(officer_b)
    am_army.add_unit(target)
    _deploy_unit(game, officer_a, 10.0, 10.0)
    _deploy_unit(game, officer_b, 10.0, 12.0)
    _deploy_unit(game, target, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    voice = am_army.voice_of_command
    assert voice.issue_order(game, officer_a, target, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE")
    assert voice.issue_order(game, officer_b, target, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE")

    assert list(voice.get_active_order_keys(target) or []) == [ORDER_TAKE_AIM.key]


def test_reinforcements_cannot_target_battle_shocked_destroyed_unit():
    game, am_player, _enemy_player, am_army, _enemy_army = _build_game("Combined Arms")
    destroyed_unit = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"])
    am_army.add_unit(destroyed_unit)
    _destroy_unit(destroyed_unit)
    destroyed_unit.status_effects.append(BattleShockEffect())

    start_cp = int(am_player.command_points or 0)
    assert am_player.stratagems.use(
        "REINFORCEMENTS!",
        destroyed_unit=destroyed_unit,
        candidates=[destroyed_unit],
        phase_name="Fight phase",
    ) is False
    assert int(am_player.command_points or 0) == start_cp


def test_vox_caster_duplicate_bearers_only_attempt_once():
    unit = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"], model_count=2)
    army = Army.with_detachment("Astra Militarum", "Combined Arms")
    army.faction_id = "AM"
    army.units = [unit]
    unit.set_parent_army(army)
    player = Player("Astra Militarum", control=PlayerControl.LOCAL, army=army)
    player.set_game(SimpleNamespace(turn=1))
    unit.special_rules["stratagem_target_cp_refund_specs"] = [
        {"roll_min": 5, "cp_gain": 1, "name": "Vox-caster", "source_model_id": "vox-a"},
        {"roll_min": 5, "cp_gain": 1, "name": "Vox-caster", "source_model_id": "vox-b"},
    ]
    player._unit_has_alive_model_id = lambda _unit, _model_id: True
    player.command_points = 2
    player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
    player._pending_stratagem_name = "Rapid Fire"

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 6]):
        assert player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem")

    assert int(player.command_points or 0) == 1


def test_destroyed_vox_caster_unit_does_not_refund_cp_for_reinforcements():
    unit = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"])
    army = Army.with_detachment("Astra Militarum", "Combined Arms")
    army.faction_id = "AM"
    army.units = [unit]
    unit.set_parent_army(army)
    player = Player("Astra Militarum", control=PlayerControl.LOCAL, army=army)
    player.set_game(SimpleNamespace(turn=1))
    unit.special_rules["stratagem_target_cp_refund_specs"] = [
        {"roll_min": 5, "cp_gain": 1, "name": "Vox-caster"}
    ]
    _destroy_unit(unit)
    player.command_points = 3
    player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
    player._pending_stratagem_name = "Reinforcements!"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
        assert player.spend_command_points(2, reason="Stratagem: Reinforcements!", source="stratagem")

    assert int(player.command_points or 0) == 1


def test_ogryn_bodyguard_attached_to_tempestus_command_squad_cannot_deep_strike():
    army = Army.with_detachment("Astra Militarum", "Combined Arms")
    army.faction_id = "AM"
    command_squad = _make_unit(
        "Militarum Tempestus Command Squad",
        keywords=["INFANTRY", "OFFICER", "ASTRA MILITARUM"],
        abilities=[_ability("Deep Strike", "Deep Strike", "Core")],
        datasheet_id="militarum-tempestus-command-squad",
    )
    ogryn_bodyguard = _make_unit(
        "Ogryn Bodyguard",
        keywords=["CHARACTER", "INFANTRY", "OGRYN", "ASTRA MILITARUM"],
        datasheet_id="ogryn-bodyguard",
        attached_to=["militarum-tempestus-command-squad"],
    )
    army.add_unit(command_squad)
    army.add_unit(ogryn_bodyguard)

    ogryn_bodyguard.attach_to_unit(command_squad)

    assert command_squad.has_deep_strike() is False
    assert ogryn_bodyguard.has_deep_strike() is False
