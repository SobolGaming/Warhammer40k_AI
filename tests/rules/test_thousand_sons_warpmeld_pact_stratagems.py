from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        toughness: str = "4",
        wounds: str = "3",
        save: str = "4",
        base_size: str = "32mm",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count))
        model_label = "Test Model" if count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{count} {model_label}"}]
        self.datasheets_models_cost = [{"description": f"{count} model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": str(base_size),
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Thousand Sons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    toughness: str = "4",
    wounds: str = "3",
    save: str = "4",
    base_size: str = "32mm",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            toughness=toughness,
            wounds=wounds,
            save=save,
            base_size=base_size,
            model_count=quantity,
        ),
        quantity=int(quantity),
    )


def _make_profile(*, name: str = "Warpbow", range_val: str = "24", strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    ts_army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    ts_army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10

    ts_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    _refresh(game, ts_player, enemy_player)
    return game, ts_player, enemy_player, ts_army, enemy_army


def _refresh(game: Game, *players: Player) -> None:
    for player in players:
        player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    game.refresh_rule_subscribers()


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    boundary_repulsors = list(getattr(game.map, "get_battlefield_edge_repulsors", lambda: [])() or [])
    positions = unit.calculate_model_positions(
        float(x),
        float(y),
        game.map,
        avoid_friendly_units=True,
        boundary_repulsors=boundary_repulsors,
    )
    if not positions:
        raise AssertionError(f"Failed to calculate model positions for {getattr(unit, 'name', 'Unit')}")
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_reserves_unit(unit: Unit, reserve_status: str = "strategic_reserves") -> None:
    unit.deployed = False
    unit.reserve_status = str(reserve_status)
    unit.embarked_in = None


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = getattr(BattleRoundPhases, str(phase_name or "").strip().upper())
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        reaction
        for reaction in list(stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "") or "").strip().upper() == name_u
    ]


def test_warpmeld_pact_stratagem_descriptors_registered():
    expected = {
        "000010202002": ("Gift of Change", "spawn_chaos_spawn_unit_at_end_of_phase"),
        "000010202004": ("Deranged Ferocity", "fight_within_3_and_extend_pile_in_and_consolidate_to_six"),
        "000010202005": ("Blessed Transmutations", "return_destroyed_models"),
        "000010202006": ("Touched by Tzeentch", "shoot_and_charge_after_advance"),
        "000010202007": ("Twisted Mirage", "deep_strike_min_distance_override_with_no_charge"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_blessed_transmutations_queues_and_returns_destroyed_tzaangors():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        quantity=4,
    )
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(tzaangors)
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, tzaangors, 12.0, 12.0)
    _deploy_unit(game, psyker, 17.0, 12.0)

    destroyed_models = list(tzaangors.models[:2])
    for model in destroyed_models:
        model.wounds = 0
        tzaangors.models_lost.append(model)

    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(ts_player.stratagems, "BLESSED TRANSMUTATIONS")
    assert len(pending) == 1

    with patch("warhammer40k_ai.rules.stratagems_thousand_sons.dice_module.get_roll", return_value=2):
        ok = ts_player.stratagems.use(
            "BLESSED TRANSMUTATIONS",
            unit=tzaangors,
            phase_name="Command phase",
            dequeue=True,
        )

        assert ok is True
        assert int(ts_player.command_points or 0) == 9
        assert len(list(getattr(tzaangors, "models_lost", []) or [])) == 0
        assert all(bool(getattr(model, "is_alive", False)) for model in destroyed_models)


def test_touched_by_tzeentch_queues_and_cleans_at_fight_phase_end():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    mutants = _make_unit(
        "Tzaangor Enlightened",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "MOUNTED"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(mutants)
    _refresh(game, ts_player)
    _deploy_unit(game, mutants, 12.0, 12.0)

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(ts_player.stratagems, "TOUCHED BY TZEENTCH")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "TOUCHED BY TZEENTCH",
        unit=mutants,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert mutants.can_shoot_after_advance(_make_profile()) is True
    assert mutants.can_charge_after_advance() is True

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.event_system.publish("phase_end", player=ts_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert bool(mutants.special_rules.get("thousand_sons_touched_by_tzeentch_active")) is False


def test_deranged_ferocity_queues_on_fight_selection_and_cleans_up():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    mutants = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        quantity=2,
    )
    ts_army.add_unit(mutants)
    _refresh(game, ts_player)
    _deploy_unit(game, mutants, 12.0, 12.0)

    _set_phase(game, ts_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_unit_selected", unit=mutants, selecting_player=ts_player)
    pending = _pending_by_name(ts_player.stratagems, "DERANGED FEROCITY")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "DERANGED FEROCITY",
        unit=mutants,
        phase_name="Fight phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert float(mutants.special_rules.get("stratagem_pile_in_distance_override", 0.0) or 0.0) == 6.0
    assert float(mutants.special_rules.get("stratagem_consolidate_distance_override", 0.0) or 0.0) == 6.0
    assert bool(mutants.special_rules.get("fight_within_3_active")) is True

    game.event_system.publish("phase_end", player=ts_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert "stratagem_pile_in_distance_override" not in mutants.special_rules
    assert "stratagem_consolidate_distance_override" not in mutants.special_rules
    assert "fight_within_3_active" not in mutants.special_rules
    assert "fight_within_3" not in mutants.special_rules


def test_twisted_mirage_queues_during_reinforcements_step_and_blocks_charge_after_arrival():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    mutants = _make_unit(
        "Tzaangor Enlightened",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "MOUNTED"],
        faction_keywords=["THOUSAND SONS"],
    )
    enemy = _make_unit(
        "Enemy Screen",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(mutants)
    enemy_army.add_unit(enemy)
    _set_reserves_unit(mutants, "strategic_reserves")
    _refresh(game, ts_player, _enemy_player)
    _deploy_unit(game, enemy, 22.0, 12.0)

    game.turn = 2
    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    game.handle_reserves_arrival_phase()
    pending = _pending_by_name(ts_player.stratagems, "TWISTED MIRAGE")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "TWISTED MIRAGE",
        unit=mutants,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert mutants.has_deep_strike() is True
    assert float(mutants.get_deep_strike_min_distance_override() or 0.0) == 6.0

    for model in list(mutants.models or []):
        model.set_location(12.0, 12.0, 0.0, 0.0)
    mutants._finalize_reserves_arrival(turn=2, game_map=game.map)

    assert mutants.has_deep_strike() is False
    assert mutants.can_declare_charge_against(enemy, game) is False


def test_twisted_mirage_monster_uses_nine_inch_distance():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Mutalith Vortex Beast",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "MONSTER"],
        faction_keywords=["THOUSAND SONS"],
        base_size="100mm",
    )
    ts_army.add_unit(monster)
    _set_reserves_unit(monster, "strategic_reserves")
    _refresh(game, ts_player)

    game.turn = 2
    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    ok = ts_player.stratagems.use("TWISTED MIRAGE", unit=monster, phase_name="Movement phase")

    assert ok is True
    assert float(monster.get_deep_strike_min_distance_override() or 0.0) == 9.0


def test_twisted_mirage_does_not_allow_turn_one_arrival_after_ambushing_hunters():
    game, ts_player, enemy_player, ts_army, _enemy_army = _build_game()
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        quantity=2,
    )
    ts_army.add_unit(tzaangors)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, tzaangors, 12.0, 12.0)

    game.turn = 1
    game.current_player_index = 1
    moved_to_reserves = tzaangors.enter_strategic_reserves_midgame(
        game=game,
        game_map=game.map,
        reason="Ambushing Hunters",
    )

    assert moved_to_reserves is True
    assert str(getattr(tzaangors, "reserve_status", "") or "") == "strategic_reserves"
    assert bool(getattr(tzaangors, "_entered_reserves_midgame", False)) is True
    assert bool(getattr(tzaangors, "_started_in_reserves", False)) is False

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)

    assert tzaangors.can_arrive_from_reserves(1) is False
    assert tzaangors not in list(game.get_units_that_can_arrive_from_reserves(ts_player) or [])

    game.handle_reserves_arrival_phase()
    pending = _pending_by_name(ts_player.stratagems, "TWISTED MIRAGE")
    assert pending == []
    assert ts_player.stratagems.use("TWISTED MIRAGE", unit=tzaangors, phase_name="Movement phase") is False
    assert int(ts_player.command_points or 0) == 10


def test_gift_of_change_queues_on_destroyed_character_and_spawns_chaos_spawn_at_phase_end():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    character = _make_unit(
        "Exalted Sorcerer",
        keywords=["THOUSAND SONS", "PSYKER", "CHARACTER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(character)
    _refresh(game, ts_player)
    _deploy_unit(game, character, 12.0, 12.0)

    destroyed_model = character.models[0]
    destroyed_model.wounds = 0
    character.models_lost.append(destroyed_model)

    _set_phase(game, ts_player, "FIGHT_PHASE", 0)
    game.event_system.publish("model_destroyed_before_removal", unit=character, model=destroyed_model)
    pending = _pending_by_name(ts_player.stratagems, "GIFT OF CHANGE")
    assert len(pending) == 1

    spawn_datasheet = _MockDatasheet(
        "Chaos Spawn",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "BEAST"],
        faction_keywords=["THOUSAND SONS"],
        base_size="50mm",
    )

    with patch.object(ts_player.stratagems._waha, "get_full_datasheet_info_by_name", return_value=spawn_datasheet), patch.object(
        ts_player.stratagems._waha,
        "get_datasheet",
        return_value=spawn_datasheet,
    ):
        ok = ts_player.stratagems.use(
            "GIFT OF CHANGE",
            destroyed_model=destroyed_model,
            phase_name="Fight phase",
            dequeue=True,
        )

        assert ok is True
        assert int(ts_player.command_points or 0) == 9

        if character in list(getattr(game.map, "units", []) or []):
            game.map.units.remove(character)
        character.deployed = False

        game.event_system.publish("phase_end", player=ts_player, phase=BattleRoundPhases.FIGHT_PHASE)

    spawned = [unit for unit in list(ts_army.units or []) if unit is not character and getattr(unit, "name", "") == "Chaos Spawn"]
    assert len(spawned) == 1
    assert int(getattr(spawned[0], "starting_model_count", 0) or 0) == 1
