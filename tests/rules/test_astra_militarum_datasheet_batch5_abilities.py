from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem, _unit_cannot_be_target_of_stratagem
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


GRENADIERS_TEXT = "Once per turn, you can target this unit with the Grenade Stratagem for 0CP."
REMOTE_MINE_TEXT = (
    "Once per battle, at the start of your Shooting phase, you can select one enemy unit within 9\" of and visible "
    "to the bearer and roll one D6: on a 3+, that enemy unit suffers D3 mortal wounds, or 2D3 mortal wounds "
    "instead if it is a VEHICLE or FORTIFICATIONS unit."
)
GRIM_DETERMINATION_TEXT = (
    "While this unit contains an OFFICER, you can target this unit with Stratagems even while it is Battle-shocked "
    "and Orders issued to this unit do not cease to affect this unit if it becomes Battle-shocked."
)
SERVO_SCRIBES_TEXT = "Once per battle, when issuing an Order, the Lord Commissar can issue one additional Order."
FINAL_DUTY_TEXT = (
    "While the Fire Coordinator model is on the battlefield, each time a Heavy Weapons Gunner model is destroyed, "
    "roll one D6: on a 3+, do not remove it from play. The destroyed model can shoot after the attacking model's "
    "unit has finished making its attacks, and is then removed from play."
)
DEATH_BEFITTING_AN_OFFICER_TEXT = (
    "When this model is destroyed, roll one D6: on a 2+, do not remove it from play - it can, after the attacking "
    "model's unit has finished making its attacks, shoot as if it were your Shooting phase and as if it had its "
    "full wounds remaining. This model is then removed from play."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        wounds: int = 2,
        save: int = 4,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    wounds: int = 2,
    save: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            wounds=wounds,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army("Astra Militarum", detachment_type="Combined Regiment")
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _option_for_target(request, target: Unit):
    target_id = str(get_entity_id(target) or "")
    return next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == target_id
    )


def _grenade_stratagem() -> Stratagem:
    return Stratagem(
        id="grenade",
        name="Grenade",
        type="Core",
        description="",
        cp_cost=1,
        turn="Your",
        phase="Shooting phase",
        detachment="",
        faction_id="",
    )


def _install_rolls(monkeypatch, rolls: list[int]) -> None:
    import warhammer40k_ai.utility.dice as dice_mod
    import warhammer40k_ai.units.unit_mixins.damage_death_mixin as damage_death_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    values = iter(list(rolls))

    def _rigged(_expr: str):
        try:
            return next(values)
        except StopIteration:
            return 6

    monkeypatch.setattr(dice_mod, "get_roll", _rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", _rigged)
    monkeypatch.setattr(damage_death_mod, "get_roll", _rigged)


def _add_simple_ranged_weapon(model: Model, *, damage: str = "1") -> None:
    gun = Wargear(
        {
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2",
            "S": "10",
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )
    model.wargear.append(gun)


def test_grenadiers_reduces_grenade_to_zero_cp_once_per_turn():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    engineers = _make_unit(
        "Krieg Combat Engineers",
        datasheet_id="krieg-combat-engineers",
        abilities=[{"name": "Grenadiers", "description": GRENADIERS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "GRENADES", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        datasheet_id="enemy-unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    am_army.add_unit(engineers)
    enemy_army.add_unit(enemy)
    _deploy(engineers, 0.0, 0.0)
    _deploy(enemy, 8.0, 0.0)
    _register_units(game, engineers, enemy)

    grenade = _grenade_stratagem()
    am_player.stratagems.available = [grenade]
    am_player.set_next_optional_decision("GRENADIERS_GRENADE", True)

    cost_info = am_player.apply_stratagem_cp_cost(grenade, target_unit=engineers, enemy_unit=enemy)
    assert "cost" in cost_info
    assert int(cost_info["cost"]) == 0
    assert engineers.grenadiers_grenade_used_this_turn(game)
    assert not engineers.can_use_grenadiers_grenade(game, stratagem_name="GRENADE")

    game.turn = 3
    assert engineers.can_use_grenadiers_grenade(game, stratagem_name="GRENADE")


def test_remote_mine_queues_visible_target_and_uses_vehicle_fortification_roll():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    engineers = _make_unit(
        "Krieg Combat Engineers",
        datasheet_id="krieg-combat-engineers",
        abilities=[{"name": "Remote Mine", "description": REMOTE_MINE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target = _make_unit(
        "Enemy Tank",
        datasheet_id="enemy-tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )
    am_army.add_unit(engineers)
    enemy_army.add_unit(target)
    _deploy(engineers, 0.0, 0.0)
    _deploy(target, 6.0, 0.0)
    _register_units(game, engineers, target)

    game._on_phase_start_shooting_phase_enemy_range_mortal_threshold(player=am_player, phase=game.phase)
    request = _find_quarry_request(game, "squig_mine")
    assert request is not None
    assert str((request.context or {}).get("alternate_mortal_wounds_roll", "") or "") == "2D3"
    assert list((request.context or {}).get("alternate_target_keywords_any", []) or []) == ["VEHICLE", "FORTIFICATIONS"]

    option = _option_for_target(request, target)

    def _roll(expr: str):
        expr_key = str(expr or "").strip().upper()
        if expr_key == "D6":
            return 3
        if expr_key == "2D3":
            return 4
        raise AssertionError(f"Unexpected roll expression: {expr_key}")

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=_roll):
        result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert int(getattr(target.models[0], "wounds", 0) or 0) == 8
    assert engineers.models[0].has_used_once_per_battle(str((request.context or {}).get("ability_key", "") or ""))


def test_grim_determination_allows_stratagem_targeting_and_preserves_orders():
    game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
    command_squad = _make_unit(
        "Krieg Command Squad",
        datasheet_id="krieg-command-squad",
        abilities=[{"name": "Grim Determination", "description": GRIM_DETERMINATION_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM", "OFFICER"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    command_squad.models[0].keywords = ["OFFICER", "INFANTRY", "ASTRA MILITARUM"]
    am_army.add_unit(command_squad)
    _deploy(command_squad, 0.0, 0.0)
    _register_units(game, command_squad)

    command_squad.special_rules["cannot_use_stratagems"] = True
    command_squad.is_battle_shocked = lambda: True
    assert _unit_cannot_be_target_of_stratagem(command_squad) is False

    mgr = am_army.voice_of_command
    mgr._apply_order_to_unit_and_attached(command_squad, "TAKE_AIM", owner_id=am_player.id, source_id="officer-1")
    game._on_battle_shock_test_resolved_voice_of_command(unit=command_squad, passed=False)
    assert str(command_squad.special_rules.get("voice_of_command_order_key", "") or "") == "TAKE_AIM"

    command_squad.models[0].keywords = ["INFANTRY", "ASTRA MILITARUM"]
    assert _unit_cannot_be_target_of_stratagem(command_squad) is True


def test_servo_scribes_grants_one_additional_order_once_per_battle():
    game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
    command_squad = _make_unit(
        "Krieg Command Squad",
        datasheet_id="krieg-command-squad",
        abilities=[
            {"name": "Voice of Command", "description": "", "type": "Datasheet", "parameter": ""},
            {"name": "Orders", "description": "This model can issue 1 Order to REGIMENT units within 6\".", "type": "Datasheet", "parameter": ""},
            {"name": "Servo-scribes", "description": SERVO_SCRIBES_TEXT, "type": "Datasheet", "parameter": ""},
        ],
        keywords=["INFANTRY", "ASTRA MILITARUM", "OFFICER"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    command_squad.models[0].name = "Lord Commissar"
    command_squad.models[0].keywords = ["OFFICER", "INFANTRY", "ASTRA MILITARUM"]
    target_a = _make_unit(
        "Infantry Squad A",
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    target_b = _make_unit(
        "Infantry Squad B",
        keywords=["INFANTRY", "REGIMENT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    am_army.add_unit(command_squad)
    am_army.add_unit(target_a)
    am_army.add_unit(target_b)
    _deploy(command_squad, 0.0, 0.0)
    _deploy(target_a, 3.0, 0.0)
    _deploy(target_b, 4.0, 0.0)
    _register_units(game, command_squad, target_a, target_b)

    mgr = am_army.voice_of_command
    assert mgr.orders_remaining(command_squad, int(game.turn)) == 2
    assert mgr.issue_order(game, command_squad, target_a, "MOVE_MOVE_MOVE", phase_name="COMMAND_PHASE")
    assert mgr.issue_order(game, command_squad, target_b, "TAKE_AIM", phase_name="COMMAND_PHASE")
    assert mgr.orders_remaining(command_squad, int(game.turn)) == 0
    assert command_squad.has_used_unit_once_per_battle("servo_scribes_additional_order")

    game.turn = 3
    assert mgr.orders_remaining(command_squad, int(game.turn)) == 1


def test_final_duty_grants_named_gunner_shoot_on_death_while_fire_coordinator_lives(monkeypatch):
    _install_rolls(monkeypatch, [3, 6, 6, 1])

    from warhammer40k_ai.battlefield.map import Map

    game_map = Map(width=48, height=72)
    heavy_weapons = _make_unit(
        "Krieg Heavy Weapons Squad",
        datasheet_id="krieg-heavy-weapons-squad",
        abilities=[{"name": "Final Duty", "description": FINAL_DUTY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=2,
        wounds=1,
    )
    heavy_weapons.models[0].name = "Fire Coordinator"
    heavy_weapons.models[1].name = "Heavy Weapons Gunner"
    _add_simple_ranged_weapon(heavy_weapons.models[1])
    target = _make_unit(
        "Enemy Target",
        datasheet_id="enemy-target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=1,
    )
    am_army = Army("Army A", "Detachment A")
    enemy_army = Army("Army B", "Detachment B")
    am_army.add_unit(heavy_weapons)
    enemy_army.add_unit(target)
    game_map.units = [heavy_weapons, target]
    _deploy(heavy_weapons, 10.0, 10.0)
    _deploy(target, 20.0, 10.0)

    gunner = heavy_weapons.models[1]
    rule = heavy_weapons.get_shoot_on_death_after_attacks_rule(model=gunner)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 3

    heavy_weapons.begin_attack_resolution()
    gunner.wounds = 0
    gunner.die(game_map=game_map)
    assert gunner in list(getattr(heavy_weapons, "_shoot_on_death_pending_models", []) or [])
    heavy_weapons.end_attack_resolution(game_map=game_map)

    assert heavy_weapons.is_alive() is True
    assert target.is_alive() is False


def test_final_duty_stops_applying_after_fire_coordinator_is_destroyed():
    from warhammer40k_ai.battlefield.map import Map

    game_map = Map(width=48, height=72)
    heavy_weapons = _make_unit(
        "Krieg Heavy Weapons Squad",
        datasheet_id="krieg-heavy-weapons-squad",
        abilities=[{"name": "Final Duty", "description": FINAL_DUTY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=2,
        wounds=1,
    )
    heavy_weapons.models[0].name = "Fire Coordinator"
    heavy_weapons.models[1].name = "Heavy Weapons Gunner"
    fire_coordinator = heavy_weapons.models[0]
    gunner = heavy_weapons.models[1]
    fire_coordinator.wounds = 0
    fire_coordinator.die(game_map=game_map)

    assert heavy_weapons.get_shoot_on_death_after_attacks_rule(model=gunner) is None


def test_death_befitting_an_officer_shoots_on_death_after_any_destruction(monkeypatch):
    _install_rolls(monkeypatch, [2, 6, 6, 1])

    from warhammer40k_ai.battlefield.map import Map

    game_map = Map(width=48, height=72)
    commander = _make_unit(
        "Leman Russ Commander",
        datasheet_id="leman-russ-commander",
        abilities=[
            {
                "name": "Death Befitting An Officer",
                "description": DEATH_BEFITTING_AN_OFFICER_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=12,
    )
    commander_model = commander.models[0]
    commander_model.name = "Tank Commander"
    _add_simple_ranged_weapon(commander_model)
    commander_model.wounds = 1
    target = _make_unit(
        "Enemy Target",
        datasheet_id="enemy-target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=1,
    )
    am_army = Army("Army A", "Detachment A")
    enemy_army = Army("Army B", "Detachment B")
    am_army.add_unit(commander)
    enemy_army.add_unit(target)
    game_map.units = [commander, target]
    _deploy(commander, 10.0, 10.0)
    _deploy(target, 20.0, 10.0)

    rule = commander.get_shoot_on_death_after_attacks_rule(model=commander_model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 2
    assert str(rule.get("attack_type", "") or "") == "any"
    assert bool(rule.get("full_wounds_remaining")) is True

    commander.begin_attack_resolution()
    commander_model.wounds = 0
    commander_model.die(game_map=game_map)
    assert commander_model in list(getattr(commander, "_shoot_on_death_pending_models", []) or [])
    commander.end_attack_resolution(game_map=game_map)

    assert commander.is_alive() is False
    assert target.is_alive() is False
