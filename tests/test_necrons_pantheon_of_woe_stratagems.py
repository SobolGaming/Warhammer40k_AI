from __future__ import annotations

from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.dice import DiceCollection


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ) -> None:
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "8" if "MONSTER" in set(self.keywords) or "VEHICLE" in set(self.keywords) else "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": str(base_size),
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


def _ability(name: str, description: str, *, type_name: str = "Datasheet") -> dict:
    return {
        "name": str(name),
        "description": str(description),
        "type": str(type_name),
        "parameter": "",
    }


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _weapon(name: str, *, melee: bool, damage: str = "1") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    necron_army = Army("Necrons", "Pantheon of Woe")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)

    necron_player.command_points = 10
    enemy_player.command_points = 10
    return game, necron_player, enemy_player, necron_army, enemy_army


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


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def test_pantheon_of_woe_stratagem_descriptors_registered():
    expected = {
        "000010673002": ("Disharmonisation Cascade", "deadly_demise_on_3_plus"),
        "000010673003": ("Molecular Erosion", "force_battle_shock_then_mortal_wounds_on_fail"),
        "000010673004": ("Mass Transmogrification", "trigger_reanimation_protocols_if_destroyed_enemy_was_unravelling_at_phase_start"),
        "000010673005": ("Entrophasic Aura Targeting", "reroll_hit_ones_and_reroll_wound_ones_vs_unravelling_targets"),
        "000010673006": ("Chronodistortion", "fight_on_death_on_4_plus_add_one_if_attacker_unravelling"),
        "000010673007": ("Phase Melding", "force_desperate_escape_on_falling_back_enemy"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_chronodistortion_queues_and_improves_fight_on_death_against_unravelling_attackers():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    source_monster = _make_unit(
        "Transcendent C'tan",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=8,
    )
    target = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    attacker = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(source_monster)
    necron_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, source_monster, 6.0, 10.0)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.4, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[target])

    pending = _pending_by_name(necron_player.stratagems, "CHRONODISTORTION")
    assert pending is not None
    assert target in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "CHRONODISTORTION",
        unit=target,
        attacking_unit=attacker,
        target_units=[target],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    target._last_destroyed_by_unit = attacker
    rule = target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 3
    assert "CHRONODISTORTION" in str(rule.get("source", "") or "").upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0]) is None


def test_disharmonisation_cascade_queues_and_triggers_deadly_demise_on_three_plus():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    monster = _make_unit(
        "C'tan Shard of the Void Dragon",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=12,
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, monster, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    monster.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    monster._apply_deadly_demise_explosion = Mock()
    destroyed_model = monster.models[0]
    destroyed_model.wounds = 0

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("model_destroyed_before_removal", unit=monster, model=destroyed_model)

    pending = _pending_by_name(necron_player.stratagems, "DISHARMONISATION CASCADE")
    assert pending is not None

    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
        ok = necron_player.stratagems.use(
            "DISHARMONISATION CASCADE",
            unit=monster,
            destroyed_model=destroyed_model,
            phase_name="Shooting phase",
            dequeue=True,
        )

    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    monster._apply_deadly_demise_explosion.assert_called_once()
    assert int(getattr(destroyed_model, "_pantheon_disharmonisation_trigger_threshold_once", 0) or 0) == 0


def test_entrophasic_aura_targeting_queues_and_grants_rerolls_against_unravelling_targets():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    source_monster = _make_unit(
        "Transcendent C'tan",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=8,
    )
    shooters = _make_unit(
        "Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    shooters.models[0].wargear = [_weapon("Gauss Blaster", melee=False)]
    unravelling_enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    normal_enemy = _make_unit(
        "Enemy Rear Guard",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(source_monster)
    necron_army.add_unit(shooters)
    enemy_army.add_unit(unravelling_enemy)
    enemy_army.add_unit(normal_enemy)
    _deploy_unit(game, source_monster, 6.0, 10.0)
    _deploy_unit(game, shooters, 10.0, 10.0)
    _deploy_unit(game, unravelling_enemy, 11.4, 10.0)
    _deploy_unit(game, normal_enemy, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(necron_player.stratagems, "ENTROPHASIC AURA TARGETING")
    assert pending is not None
    assert shooters in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "ENTROPHASIC AURA TARGETING",
        unit=shooters,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    profile = shooters.models[0].wargear[0].profiles["default"]
    hit_unravelling = profile._hit_target_with_tracking(
        unravelling_enemy,
        shooters.models[0],
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_unravelling = profile._wound_target_with_tracking(
        unravelling_enemy,
        shooters.models[0],
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_normal = profile._wound_target_with_tracking(
        normal_enemy,
        shooters.models[0],
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )

    hit_reasons = list(hit_unravelling.get("reroll_value_reasons", []) or [])
    wound_unravelling_reasons = list(wound_unravelling.get("reroll_value_reasons", []) or [])
    wound_normal_reasons = list(wound_normal.get("reroll_value_reasons", []) or [])
    assert any("ENTROPHASIC AURA TARGETING" in str(reason).upper() for reason in hit_reasons)
    assert any("ENTROPHASIC AURA TARGETING" in str(reason).upper() for reason in wound_unravelling_reasons)
    assert all("ENTROPHASIC AURA TARGETING" not in str(reason).upper() for reason in wound_normal_reasons)

    game.event_system.publish("phase_end", player=necron_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    expired = profile._hit_target_with_tracking(
        unravelling_enemy,
        shooters.models[0],
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert all(
        "ENTROPHASIC AURA TARGETING" not in str(reason).upper()
        for reason in list(expired.get("reroll_value_reasons", []) or [])
    )


def test_mass_transmogrification_queues_and_triggers_reanimation_once_per_turn():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    source_monster = _make_unit(
        "C'tan Shard of the Deceiver",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=12,
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        wounds=2,
    )
    enemy_a = _make_unit(
        "Enemy Vanguard",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    enemy_b = _make_unit(
        "Enemy Reserves",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    necron_army.add_unit(source_monster)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, source_monster, 10.0, 10.0)
    _deploy_unit(game, warriors, 14.0, 10.0)
    _deploy_unit(game, enemy_a, 12.0, 10.0)
    _deploy_unit(game, enemy_b, 12.0, 12.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    necron_army.necrons_detachments.snapshot_pantheon_unravelling_phase_state(game=game)
    assert necron_army.necrons_detachments.pantheon_unit_was_unravelling_at_phase_start(enemy_a, game=game) is True

    game.event_system.publish("unit_destroyed", unit=enemy_a, destroyed_by_unit=source_monster)
    pending = _pending_by_name(necron_player.stratagems, "MASS TRANSMOGRIFICATION")
    assert pending is not None
    assert warriors in list(pending.get("candidates") or [])

    warriors.apply_reanimation_protocols = Mock(return_value={"healed": 2, "returned": 0})
    with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=2):
        ok = necron_player.stratagems.use(
            "MASS TRANSMOGRIFICATION",
            unit=warriors,
            source_unit=source_monster,
            destroyed_unit=enemy_a,
            phase_name="Shooting phase",
            dequeue=True,
        )

    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    warriors.apply_reanimation_protocols.assert_called_once()
    args, kwargs = warriors.apply_reanimation_protocols.call_args
    assert int(args[0]) == 2
    assert str(kwargs.get("roll_expr", "") or "") == "D3"

    game.event_system.publish("unit_destroyed", unit=enemy_b, destroyed_by_unit=source_monster)
    assert _pending_by_name(necron_player.stratagems, "MASS TRANSMOGRIFICATION") is None


def test_molecular_erosion_queues_in_command_phase_and_deals_mortals_on_failed_test():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    source_monster = _make_unit(
        "Transcendent C'tan",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=8,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=5,
    )
    source_monster._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True
    necron_army.add_unit(source_monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source_monster, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    calls: list[tuple[int, str]] = []

    def _force_failed_battle_shock(current_turn=1, *, modifier=0, source=""):
        calls.append((int(modifier), str(source)))
        enemy._last_leadership_test_passed = False
        game.event_system.publish("battle_shock_test_resolved", unit=enemy, passed=False)

    enemy.force_battle_shock_test = _force_failed_battle_shock
    original_apply = source_monster._apply_mortal_wounds_to_unit
    source_monster._apply_mortal_wounds_to_unit = Mock(side_effect=original_apply)

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    pending = _pending_by_name(necron_player.stratagems, "MOLECULAR EROSION")
    assert pending is not None
    assert source_monster in list(pending.get("candidates") or [])

    with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=2):
        ok = necron_player.stratagems.use(
            "MOLECULAR EROSION",
            unit=source_monster,
            enemy_unit=enemy,
            phase_name="Command phase",
            dequeue=True,
        )

    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert calls == [(-1, "MOLECULAR EROSION")]
    source_monster._apply_mortal_wounds_to_unit.assert_called_once()
    args, _kwargs = source_monster._apply_mortal_wounds_to_unit.call_args
    assert args[0] is enemy
    assert int(args[1]) == 3


def test_phase_melding_queues_and_forces_desperate_escape_with_battleshock_penalty():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    source_monster = _make_unit(
        "Transcendent C'tan",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
        wounds=8,
    )
    trap_unit = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Runners",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(source_monster)
    necron_army.add_unit(trap_unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source_monster, 6.0, 10.0)
    _deploy_unit(game, trap_unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.6, 10.0)
    enemy.apply_status_effect(BattleShockEffect(1))
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    pending = _pending_by_name(necron_player.stratagems, "PHASE MELDING")
    assert pending is not None
    assert trap_unit in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "PHASE MELDING",
        unit=trap_unit,
        enemy_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    called = {"count": 0, "modifier": None}

    def _fake_desperate_escape(self, game_map=None, *, roll_modifier=0, reason=None):
        called["count"] += 1
        called["modifier"] = int(roll_modifier or 0)
        return 0

    enemy.take_desperate_escape_test = MethodType(_fake_desperate_escape, enemy)
    result = enemy.fall_back((15.0, 10.0, 0.0), [], game.map)
    assert result is True
    assert called["count"] == 1
    assert int(called["modifier"] or 0) == -1

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert not bool(trap_unit.special_rules.get("enemy_fallback_desperate_escape"))
