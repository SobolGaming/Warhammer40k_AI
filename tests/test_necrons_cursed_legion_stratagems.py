from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        movement: int = 6,
    ):
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
                "M": str(int(movement)),
                "T": "5",
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
        normalized_abilities = []
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized_abilities.append(entry)
        self.datasheets_abilities = normalized_abilities
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    movement: int = 6,
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
            movement=movement,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    necron_army = Army("Necrons", "Cursed Legion")
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


def _reanimation_ability():
    return [{"name": "Reanimation Protocols", "description": "", "type": "Datasheet", "parameter": ""}]


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
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


def _equip_weapon(
    unit: Unit,
    *,
    name: str,
    melee: bool = False,
    range_value: str = "24",
):
    profile = None
    for model in list(getattr(unit, "models", []) or []):
        weapon = Wargear(
            {
                "name": name,
                "type": "Melee" if melee else "Ranged",
                "range": "Melee" if melee else str(range_value),
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        model.wargear = [weapon]
        if profile is None:
            profile = weapon.profiles["default"]
    return profile


def test_cursed_legion_stratagem_descriptors_registered():
    expected = {
        "000010669003": ("Image of Death", "defensive_hit_penalty"),
        "000010669005": ("Driven to Butchery", "shoot_and_charge_after_advance"),
        "000010669002": ("Methodical Murder", "grant_sustained_hits_all_weapons"),
        "000010669004": ("Mortis Protocols", "trigger_reanimation_protocols"),
        "000010669006": ("Spreading Madness", "conditional_charge_roll_bonus_if_charge_target_engaged"),
        "000010669007": ("Unnatural Aggression", "out_of_turn_charge_without_charge_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_driven_to_butchery_grants_advance_shoot_and_charge_until_charge_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _equip_weapon(destroyers, name="Hyperphase Threshers")
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    destroyers.round_state.advanced_this_round = True
    _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok = necron_player.stratagems.use("DRIVEN TO BUTCHERY", unit=destroyers, phase_name="Shooting phase")
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert destroyers.can_shoot_after_advance(profile) is True
    assert destroyers.can_charge_after_advance() is True

    charge_phase = SimpleNamespace(name="CHARGE_PHASE")
    game.event_system.publish("phase_end", player=necron_player, phase=charge_phase)
    assert destroyers.can_shoot_after_advance(profile) is False
    assert destroyers.can_charge_after_advance() is False


def test_methodical_murder_grants_sustained_hits_and_cleans_up():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok = necron_player.stratagems.use("METHODICAL MURDER", unit=warriors, phase_name="Shooting phase")
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    bonus = warriors.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=warriors.models[0],
        game_map=game.map,
    )
    assert int(bonus.get("sustained_hits_value", 0) or 0) == 1

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared = warriors.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=warriors.models[0],
        game_map=game.map,
    )
    assert int(cleared.get("sustained_hits_value", 0) or 0) == 0


def test_mortis_protocols_queues_on_first_destroyer_cult_kill_and_reanimates():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    immortals = _make_unit(
        "Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy_one = _make_unit(
        "Enemy One",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_two = _make_unit(
        "Enemy Two",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    necron_army.add_unit(warriors)
    necron_army.add_unit(immortals)
    enemy_army.add_unit(enemy_one)
    enemy_army.add_unit(enemy_two)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, warriors, 17.5, 10.0)
    _deploy_unit(game, immortals, 30.0, 10.0)
    _deploy_unit(game, enemy_one, 22.0, 10.0)
    _deploy_unit(game, enemy_two, 24.0, 14.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=enemy_one, destroyed_by_unit=destroyers)

    pending = _pending_by_name(necron_player.stratagems, "MORTIS PROTOCOLS")
    assert pending is not None
    candidates = list(pending.get("candidates") or [])
    assert warriors in candidates
    assert immortals not in candidates

    with patch.object(warriors, "apply_reanimation_protocols") as mocked_reanimation:
        with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=2):
            ok = necron_player.stratagems.use(
                "MORTIS PROTOCOLS",
                unit=warriors,
                phase_name="Shooting phase",
                dequeue=True,
            )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    mocked_reanimation.assert_called_once()
    assert int(mocked_reanimation.call_args.args[0]) == 2
    assert str(mocked_reanimation.call_args.kwargs.get("roll_expr", "") or "") == "D3"

    game.event_system.publish("unit_destroyed", unit=enemy_two, destroyed_by_unit=destroyers)
    assert _pending_by_name(necron_player.stratagems, "MORTIS PROTOCOLS") is None


def test_spreading_madness_adds_charge_bonus_only_when_target_is_engaged_with_friendly_unit():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    charger = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    ally = _make_unit(
        "Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy_engaged = _make_unit(
        "Enemy Engaged",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_other = _make_unit(
        "Enemy Other",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(charger)
    necron_army.add_unit(ally)
    enemy_army.add_unit(enemy_engaged)
    enemy_army.add_unit(enemy_other)
    _deploy_unit(game, charger, 10.0, 10.0)
    _deploy_unit(game, ally, 20.0, 20.0)
    _deploy_unit(game, enemy_engaged, 21.5, 20.0)
    _deploy_unit(game, enemy_other, 32.0, 20.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, necron_player, "CHARGE_PHASE", 0)
    ok = necron_player.stratagems.use("SPREADING MADNESS", unit=charger, phase_name="Charge phase")
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    mods_vs_engaged = list(game.get_charge_roll_modifiers(charger, target_unit=[enemy_engaged]) or [])
    mods_vs_other = list(game.get_charge_roll_modifiers(charger, target_unit=[enemy_other]) or [])
    assert any(int(val or 0) == 2 and "SPREADING MADNESS" in str(source).upper() for val, source in mods_vs_engaged)
    assert not any(int(val or 0) == 2 and "SPREADING MADNESS" in str(source).upper() for val, source in mods_vs_other)

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    mods_after = list(game.get_charge_roll_modifiers(charger, target_unit=[enemy_engaged]) or [])
    assert not any(int(val or 0) == 2 and "SPREADING MADNESS" in str(source).upper() for val, source in mods_after)


def test_unnatural_aggression_queues_at_opponent_charge_phase_end_and_attempts_out_of_turn_charge():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.5, 10.0)
    _deploy_unit(game, enemy_far, 30.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    warriors.can_declare_charge_against = lambda target, _game, out_of_turn=False: bool(out_of_turn) and target is enemy
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    phase = _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    pending = _pending_by_name(necron_player.stratagems, "UNNATURAL AGGRESSION")
    assert pending is not None
    enemy_map = dict(pending.get("enemy_candidates_by_unit") or {})
    assert enemy in list(enemy_map.get(str(get_entity_id(warriors) or "")) or [])

    with patch.object(game, "attempt_charge", return_value=True) as charge_mock:
        ok = necron_player.stratagems.use(
            "UNNATURAL AGGRESSION",
            unit=warriors,
            enemy_unit=enemy,
            phase_name="Charge phase",
            dequeue=True,
        )
    assert ok is True
    assert int(necron_player.command_points or 0) == 8
    charge_mock.assert_called_once_with(warriors, enemy, out_of_turn=True, count_as_charged=False)
