from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
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

    necron_army = Army("Necrons", "Awakened Dynasty")
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


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _detach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [
        candidate
        for candidate in list(getattr(bodyguard, "attached_leaders", []) or [])
        if candidate is not leader
    ]
    leader.attached_to = None


def _equip_weapon(
    unit: Unit,
    *,
    name: str,
    melee: bool = False,
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
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
                "S": str(strength),
                "AP": str(ap),
                "D": str(damage),
                "description": "",
            }
        )
        model.wargear = [weapon]
        if profile is None:
            profile = weapon.profiles["default"]
    return profile


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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == decision_type:
            return request
    return None


def test_awakened_dynasty_stratagem_descriptors_registered():
    expected = {
        "000008371006": ("PROTOCOL OF THE CONQUERING TYRANT", "ranged_hit_reroll_ones_or_full_within_half_range"),
        "000008371002": ("PROTOCOL OF THE ETERNAL REVENANT", "return_destroyed_model_at_half_wounds_as_close_as_possible_not_in_engagement"),
        "000008371004": ("PROTOCOL OF THE HUNGRY VOID", "melee_strength_bonus_and_conditional_ap_bonus"),
        "000008371005": ("PROTOCOL OF THE SUDDEN STORM", "grant_assault_and_conditional_advance_reroll"),
        "000008371003": ("PROTOCOL OF THE UNDYING LEGIONS", "trigger_reanimation_protocols_with_conditional_bonus"),
        "000008371007": ("PROTOCOL OF THE VENGEFUL STARS", "reactive_shooting_restricted_to_attacker"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_conquering_tyrant_snapshots_led_full_rerolls_within_half_range_and_cleans_up():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _equip_weapon(bodyguard, name="Gauss Flayer", range_value="24")
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok = necron_player.stratagems.use(
        "PROTOCOL OF THE CONQUERING TYRANT",
        unit=bodyguard,
        phase_name="Shooting phase",
    )

    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    _detach_leader(bodyguard, leader)

    close_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=bodyguard.models[0],
        weapon_profile=profile,
        closest_dist=10.0,
    )
    far_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=bodyguard.models[0],
        weapon_profile=profile,
        closest_dist=13.0,
    )
    assert bool(close_mods.get("reroll_hit_full")) is True
    assert bool(far_mods.get("reroll_hit_full")) is False

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=bodyguard.models[0],
        weapon_profile=profile,
        closest_dist=10.0,
    )
    assert bool(cleared_mods.get("reroll_hit_full")) is False
    assert 1 not in set(cleared_mods.get("reroll_hit_values", ()) or ())


def test_sudden_storm_snapshots_led_bonuses_and_cleans_by_phase():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Royal Warden",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _equip_weapon(bodyguard, name="Gauss Blaster", range_value="24")
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    movement_phase = _set_phase(game, necron_player, "MOVEMENT_PHASE", 0)
    ok = necron_player.stratagems.use(
        "PROTOCOL OF THE SUDDEN STORM",
        unit=bodyguard,
        phase_name="Movement phase",
    )

    assert ok is True
    _detach_leader(bodyguard, leader)
    assert bodyguard.can_reroll_advance_roll() is True

    game.event_system.publish("phase_end", player=necron_player, phase=movement_phase)
    shooting_phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    assert bodyguard.can_reroll_advance_roll() is False
    assert bodyguard.can_shoot_after_advance(profile) is True

    game.event_system.publish("phase_end", player=necron_player, phase=shooting_phase)
    assert bodyguard.can_shoot_after_advance(profile) is False


def test_hungry_void_snapshots_led_ap_bonus_and_cleans_up():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Lychguard",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    phase = _set_phase(game, necron_player, "FIGHT_PHASE", 0)
    ok = necron_player.stratagems.use(
        "PROTOCOL OF THE HUNGRY VOID",
        unit=bodyguard,
        phase_name="Fight phase",
    )

    assert ok is True
    _detach_leader(bodyguard, leader)
    strength_bonus, reasons = bodyguard.models[0].get_temporary_melee_strength_bonus()
    assert int(strength_bonus) == 1
    assert bodyguard.models[0].get_temporary_melee_ap_bonus() == 1
    assert any("HUNGRY VOID" in str(reason or "").upper() for reason in list(reasons or []))

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared_strength, _ = bodyguard.models[0].get_temporary_melee_strength_bonus()
    assert int(cleared_strength) == 0
    assert bodyguard.models[0].get_temporary_melee_ap_bonus() == 0


def test_eternal_revenant_returns_destroyed_attached_character_as_separate_unit_once():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
        wounds=5,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    phase = _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    leader_model = leader.models[0]
    leader_model.wounds = 0
    leader_model._wounds = 0
    leader.models_lost = [leader_model]
    game.event_system.publish("model_destroyed_before_removal", unit=bodyguard, model=leader_model)

    pending = _pending_by_name(necron_player.stratagems, "PROTOCOL OF THE ETERNAL REVENANT")
    assert pending is not None
    assert pending.get("destroyed_unit") is leader

    ok = necron_player.stratagems.use(
        "PROTOCOL OF THE ETERNAL REVENANT",
        destroyed_unit=leader,
        destroyed_model=leader_model,
        dequeue=True,
    )

    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    assert leader.attached_to is None
    assert leader not in list(getattr(bodyguard, "attached_leaders", []) or [])
    assert leader in list(getattr(game.map, "units", []) or [])
    assert int(getattr(leader_model, "wounds", 0) or 0) == 3
    assert int(getattr(leader_model, "_wounds", 0) or 0) == 3

    leader_model.wounds = 0
    leader_model._wounds = 0
    game.event_system.publish("model_destroyed_before_removal", unit=leader, model=leader_model)
    assert _pending_by_name(necron_player.stratagems, "PROTOCOL OF THE ETERNAL REVENANT") is None


def test_undying_legions_queues_after_enemy_shooting_and_uses_snapshotted_bonus():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy,
        killing_models_by_target={bodyguard: [object()]},
    )

    pending = _pending_by_name(necron_player.stratagems, "PROTOCOL OF THE UNDYING LEGIONS")
    assert pending is not None
    assert bodyguard in list(pending.get("candidates") or [])

    _detach_leader(bodyguard, leader)

    with patch.object(bodyguard, "apply_reanimation_protocols") as mocked_reanimation:
        with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=2):
            ok = necron_player.stratagems.use(
                "PROTOCOL OF THE UNDYING LEGIONS",
                unit=bodyguard,
                dequeue=True,
            )

    assert ok is True
    mocked_reanimation.assert_called_once()
    assert int(mocked_reanimation.call_args.args[0]) == 3
    assert str(mocked_reanimation.call_args.kwargs.get("roll_expr", "") or "") == "D3"


def test_undying_legions_does_not_queue_when_attached_bodyguard_models_are_all_destroyed():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    leader = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _set_unit_location(leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    for model in list(bodyguard.models or []):
        model.wounds = 0
        model._wounds = 0

    assert bodyguard.attached_unit_has_reanimation_protocols() is False

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy,
        killing_models_by_target={bodyguard: [object()]},
    )

    assert _pending_by_name(necron_player.stratagems, "PROTOCOL OF THE UNDYING LEGIONS") is None


def test_vengeful_stars_queues_after_unit_destroyed_and_restricts_reactive_target():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyed_unit = _make_unit(
        "Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    character = _make_unit(
        "Hexmark Destroyer",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _equip_weapon(character, name="Enmitic Disintegrator", range_value="24")
    necron_army.add_unit(destroyed_unit)
    necron_army.add_unit(character)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyed_unit, 9.0, 10.0)
    _deploy_unit(game, character, 4.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    with patch.object(game, "_setup_reactive_can_shoot_target", return_value=True):
        game.event_system.publish(
            "unit_destroyed",
            unit=destroyed_unit,
            destroyed_by_unit=enemy,
            last_model=destroyed_unit.models[0],
        )

        pending = _pending_by_name(necron_player.stratagems, "PROTOCOL OF THE VENGEFUL STARS")
        assert pending is not None
        assert character in list(pending.get("candidates") or [])

        ok = necron_player.stratagems.use(
            "PROTOCOL OF THE VENGEFUL STARS",
            unit=character,
            dequeue=True,
        )

    assert ok is True
    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("unit_id", "") or "") == str(get_entity_id(character) or "")
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
