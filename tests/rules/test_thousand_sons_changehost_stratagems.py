from __future__ import annotations

from types import SimpleNamespace
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
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
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
    wounds: str = "3",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ts_army = Army.with_detachment("Thousand Sons", "Changehost of Deceit")
    ts_army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10
    ts_army.configure_rule_managers(force=True)
    ts_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ts_player, enemy_player, ts_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        r for r in list(stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == name_u
    ]


def test_glimmershift_portal_queues_at_end_of_opponent_fight_phase():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster_a = _make_unit(
        "Pink Horrors A",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    non_monster_b = _make_unit(
        "Pink Horrors B",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    monster = _make_unit(
        "Kairos Fateweaver",
        keywords=["MONSTER", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    too_close = _make_unit(
        "Flamers Too Close",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    ts_army.add_unit(non_monster_a)
    ts_army.add_unit(non_monster_b)
    ts_army.add_unit(monster)
    ts_army.add_unit(too_close)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, non_monster_a, 4.0, 4.0)
    _deploy_unit(game, non_monster_b, 8.0, 4.0)
    _deploy_unit(game, monster, 12.0, 4.0)
    _deploy_unit(game, too_close, 25.0, 20.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    pending = _pending_by_name(ts_player.stratagems, "GLIMMERSHIFT PORTAL")
    assert len(pending) == 1
    candidates = list(pending[0].get("candidates") or [])
    assert non_monster_a in candidates
    assert non_monster_b in candidates
    assert monster in candidates
    assert too_close not in candidates
    assert int(pending[0].get("max_units", 0) or 0) == 2


def test_glimmershift_portal_moves_two_non_monster_units_into_strategic_reserves():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster_a = _make_unit(
        "Pink Horrors A",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    non_monster_b = _make_unit(
        "Pink Horrors B",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(non_monster_a)
    ts_army.add_unit(non_monster_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, non_monster_a, 4.0, 4.0)
    _deploy_unit(game, non_monster_b, 10.0, 4.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = ts_player.stratagems.use(
        "GLIMMERSHIFT PORTAL",
        units=[non_monster_a, non_monster_b],
        candidates=[non_monster_a, non_monster_b],
        max_units=2,
        phase_name="Fight phase",
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert non_monster_a.is_in_reserves()
    assert non_monster_b.is_in_reserves()


def test_glimmershift_portal_rejects_mixed_monster_and_non_monster_selection():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    non_monster = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    monster = _make_unit(
        "Kairos Fateweaver",
        keywords=["MONSTER", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(non_monster)
    ts_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, non_monster, 4.0, 4.0)
    _deploy_unit(game, monster, 10.0, 4.0)
    _deploy_unit(game, enemy, 20.0, 20.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    blocked = ts_player.stratagems.use(
        "GLIMMERSHIFT PORTAL",
        units=[non_monster, monster],
        candidates=[non_monster, monster],
        max_units=2,
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(ts_player.command_points or 0) == 10


def test_deceptive_glamour_queues_at_start_of_fight_phase():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    thousand_sons = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    scintillating = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(thousand_sons)
    ts_army.add_unit(scintillating)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, thousand_sons, 10.0, 10.0)
    _deploy_unit(game, scintillating, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)

    pending = _pending_by_name(ts_player.stratagems, "DECEPTIVE GLAMOUR")
    assert len(pending) == 1
    assert thousand_sons in list(pending[0].get("candidates") or [])


def test_deceptive_glamour_prefers_scintillating_legions_fight_targets():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    thousand_sons = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    scintillating = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(thousand_sons)
    ts_army.add_unit(scintillating)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 10.0, 10.0)
    _deploy_unit(game, thousand_sons, 12.0, 10.0)
    _deploy_unit(game, scintillating, 10.0, 12.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = ts_player.stratagems.use(
        "DECEPTIVE GLAMOUR",
        unit=thousand_sons,
        candidates=[thousand_sons],
        phase_name="Fight phase",
    )
    assert ok
    eligible_targets = list(FightPhaseManager(game)._get_eligible_targets(enemy) or [])
    assert scintillating in eligible_targets
    assert thousand_sons not in eligible_targets


def test_chronosorcerous_bleed_queues_and_applies_non_cumulative_charge_penalty():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    psyker_target = _make_unit(
        "Infernal Master",
        keywords=["INFANTRY", "PSYKER", "THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    charger = _make_unit("Enemy Charger", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(psyker_target)
    enemy_army.add_unit(charger)
    _deploy_unit(game, psyker_target, 10.0, 10.0)
    _deploy_unit(game, charger, 18.0, 10.0)
    charger.special_rules["charge_roll_modifiers"] = [{"value": -1, "source": "Other penalty"}]

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("charge_declared", unit=charger, target_units=[psyker_target])

    pending = _pending_by_name(ts_player.stratagems, "CHRONOSORCEROUS BLEED")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "CHRONOSORCEROUS BLEED",
        unit=psyker_target,
        attacking_unit=charger,
        target_units=[psyker_target],
        candidates=[psyker_target],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok
    modifiers = list(game.get_charge_roll_modifiers(charger, target_unit=[psyker_target]) or [])
    negative_modifiers = [entry for entry in modifiers if int(entry[0] or 0) < 0]
    assert len(negative_modifiers) == 1
    assert int(negative_modifiers[0][0] or 0) == -2
    assert "CHRONOSORCEROUS BLEED" in str(negative_modifiers[0][1] or "")


def test_ethereal_phantasm_queues_and_uses_fixed_six_reactive_move():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    thousand_sons = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    scintillating = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    enemy = _make_unit("Enemy Movers", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(thousand_sons)
    ts_army.add_unit(scintillating)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, thousand_sons, 10.0, 10.0)
    _deploy_unit(game, scintillating, 13.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="normal_move")

    pending = _pending_by_name(ts_player.stratagems, "ETHEREAL PHANTASM")
    assert len(pending) == 1

    captured: dict[str, object] = {}

    def _capture_queue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(context={})

    game._queue_reactive_move_movement_decision = _capture_queue
    ok = ts_player.stratagems.use(
        "ETHEREAL PHANTASM",
        unit=scintillating,
        enemy_unit=enemy,
        action="normal_move",
        candidates=[scintillating],
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert int(captured.get("max_distance", 0) or 0) == 6
    assert captured.get("unit") is scintillating


def test_fractal_disjunction_queues_and_applies_ranged_targeting_cap():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    defender = _make_unit(
        "Pink Horrors",
        keywords=["INFANTRY", "SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ts_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 31.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = _pending_by_name(ts_player.stratagems, "FRACTAL DISJUNCTION")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "FRACTAL DISJUNCTION",
        unit=defender,
        attacking_unit=attacker,
        target_units=[defender],
        candidates=[defender],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9

    weapon = Wargear(
        {
            "name": "Ranged Weapon",
            "type": "Ranged",
            "range": "30",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    profile.is_indirect_fire = lambda: True

    can_target_far = attacker._can_model_shoot_weapon_at_target(
        attacker.models[0],
        profile,
        defender,
        game.map,
    )
    assert not can_target_far

    attacker.models[0].set_location(26.0, 10.0, 0.0, 0.0)
    can_target_close = attacker._can_model_shoot_weapon_at_target(
        attacker.models[0],
        profile,
        defender,
        game.map,
    )
    assert can_target_close


def test_changehost_glimmershift_portal_descriptor_registered():
    sulphurous = get_stratagem_tool_descriptor(stratagem_id="000010198002")
    assert sulphurous is not None
    assert sulphurous.name == "Sulphurous Veil"
    assert sulphurous.effect == "hit_roll_penalty"
    assert int(sulphurous.effect_params.get("hit_modifier", 0) or 0) == -1

    glamour = get_stratagem_tool_descriptor(stratagem_id="000010198003")
    assert glamour is not None
    assert glamour.name == "Deceptive Glamour"

    ethereal = get_stratagem_tool_descriptor(stratagem_id="000010198004")
    assert ethereal is not None
    assert ethereal.name == "Ethereal Phantasm"
    assert ethereal.effect == "reactive_normal_move_with_thousand_sons_fixed_six"

    fractal = get_stratagem_tool_descriptor(stratagem_id="000010198005")
    assert fractal is not None
    assert fractal.name == "Fractal Disjunction"
    assert fractal.effect == "ranged_targeting_distance_cap"
    assert int(fractal.effect_params.get("max_targeting_distance", 0) or 0) == 18

    chrono = get_stratagem_tool_descriptor(stratagem_id="000010198006")
    assert chrono is not None
    assert chrono.name == "Chronosorcerous Bleed"
    assert chrono.effect == "enemy_charge_roll_modifier_non_cumulative_negative"
    assert int(chrono.effect_params.get("charge_roll_modifier", 0) or 0) == -2

    by_id = get_stratagem_tool_descriptor(stratagem_id="000010198007")
    assert by_id is not None
    assert by_id.name == "Glimmershift Portal"
    assert by_id.effect == "enter_strategic_reserves"
    assert int(by_id.effect_params.get("max_units", 0) or 0) == 2
    assert float(by_id.effect_params.get("min_enemy_horizontal_distance", 0.0) or 0.0) == 6.0

    by_name = get_stratagem_tool_descriptor(name="GLIMMERSHIFT PORTAL")
    assert by_name is not None
    assert by_name.stratagem_id == "000010198007"
