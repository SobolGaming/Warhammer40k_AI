from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules import stratagems_adeptus_custodes as custodes_stratagems_module
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        model_count: int = 1,
    ) -> None:
        count = max(1, int(model_count or 1))
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} {name}"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "2",
                "W": "6",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army.with_detachment("Adeptus Custodes", "Solar Spearhead")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    custodes_player = Player("Custodes", control=PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)

    custodes_player.command_points = 5
    enemy_player.command_points = 5
    custodes_army.configure_rule_managers(force=True)
    custodes_player.stratagems.refresh_available()
    game.turn = 1
    game.current_player_index = 0
    return game, custodes_player, enemy_player, custodes_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, *, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_reaction_by_name(player: Player, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _ranged_wargear(name: str) -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "2+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )


def _melee_wargear(name: str) -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "2+",
            "S": "7",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _first_profile(wargear: Wargear):
    return next(iter(wargear.profiles.values()))


def test_solar_spearhead_stratagem_descriptors_registered() -> None:
    expected = {
        "000009754003": ("EMPEROR'S VENGEANCE", "fight_on_death_roll"),
        "000009754002": ("FLAWLESS CONSTRUCTION", "wound_roll_penalty_if_strength_gt_toughness"),
        "000009754007": ("PUNISHMENT INESCAPABLE", "grant_ranged_ignores_cover_and_ignore_ballistic_skill_and_hit_modifiers"),
        "000009754006": ("RELENTLESS PERSECUTION", "shoot_after_advance_and_charge_after_advance_if_walker"),
        "000009754005": ("UNSTOPPABLE", "move_through_terrain"),
        "000009754004": ("WRATHFUL ADVANCE", "pile_in_distance_override"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_emperors_vengeance_queues_and_applies_fight_on_death_thresholds() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-emperors-vengeance",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Assault Unit",
        "enemy-emperors-vengeance",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, enemy, 7.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", current_player_index=1)
    game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=enemy,
        target_units=[custodians],
    )
    assert _pending_reaction_by_name(custodes_player, "EMPEROR'S VENGEANCE") is not None

    ok = custodes_player.stratagems.use(
        "EMPEROR'S VENGEANCE",
        unit=custodians,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert custodians.get_melee_fight_on_death_after_attacks_rule(model=custodians.models[0]) == {
        "threshold": 4,
        "source": "EMPEROR'S VENGEANCE",
    }

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert custodians.get_melee_fight_on_death_after_attacks_rule(model=custodians.models[0]) is None

    walker_game, walker_player, walker_enemy_player, walker_army, walker_enemy_army = _build_game()
    walker = _make_unit(
        "Venerable Contemptor Dreadnought",
        "ac-emperors-vengeance-walker",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    walker_enemy = _make_unit(
        "Enemy Walker Hunter",
        "enemy-emperors-vengeance-walker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    walker_army.add_unit(walker)
    walker_enemy_army.add_unit(walker_enemy)
    _place_unit(walker_game, walker, 5.0, 5.0)
    _place_unit(walker_game, walker_enemy, 7.0, 5.0)
    walker_game.rebuild_entity_registry()

    _set_phase(walker_game, walker_enemy_player, "FIGHT_PHASE", current_player_index=1)
    walker_game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=walker_enemy,
        target_units=[walker],
    )
    assert _pending_reaction_by_name(walker_player, "EMPEROR'S VENGEANCE") is not None

    ok = walker_player.stratagems.use(
        "EMPEROR'S VENGEANCE",
        unit=walker,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert walker.get_melee_fight_on_death_after_attacks_rule(model=walker.models[0]) == {
        "threshold": 3,
        "source": "EMPEROR'S VENGEANCE",
    }


def test_flawless_construction_queues_and_applies_wound_penalty() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Venerable Land Raider",
        "ac-flawless-construction",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "VEHICLE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Gunline",
        "enemy-flawless-construction",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _place_unit(game, vehicle, 5.0, 5.0)
    _place_unit(game, enemy, 11.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=enemy,
        target_units=[vehicle],
    )
    assert _pending_reaction_by_name(custodes_player, "FLAWLESS CONSTRUCTION") is not None

    ok = custodes_player.stratagems.use(
        "FLAWLESS CONSTRUCTION",
        unit=vehicle,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    entries = list(vehicle.special_rules.get("defensive_wound_mods", []) or [])
    assert entries == [
        {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": "FLAWLESS CONSTRUCTION",
            "requires_strength_gt_toughness": True,
        }
    ]

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(vehicle.special_rules.get("defensive_wound_mods", []) or []) == []


def test_punishment_inescapable_grants_ignores_cover_and_ignore_modifiers() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-punishment-inescapable",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        "enemy-punishment-inescapable",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ranged = _ranged_wargear("Guardian Spear")
    custodians.models[0].wargear = [ranged, _melee_wargear("Misericordia")]
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, enemy, 11.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "PUNISHMENT INESCAPABLE",
        unit=custodians,
        phase_name="Shooting phase",
    )
    assert ok is True
    weapon_keywords = custodians.models[0].get_temporary_weapon_keyword_bonuses("Guardian Spear")
    assert len(weapon_keywords) == 1
    assert weapon_keywords[0]["keyword"] == "IGNORES COVER"

    profile = _first_profile(ranged)
    ignore_rule = profile._ignore_hit_modifier_rule(custodians.models[0], target_unit=enemy)
    assert ignore_rule is not None
    assert ignore_rule["attack_type"] == "ranged"
    assert ignore_rule["skill_kinds"] == {"ballistic"}
    assert ignore_rule["allow_hit"] is True
    assert ignore_rule["default_choice"] == "ignore_all"

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert profile._ignore_hit_modifier_rule(custodians.models[0], target_unit=enemy) is None


def test_relentless_persecution_queues_after_advance_and_updates_advance_permissions() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Venerable Land Raider",
        "ac-relentless-persecution",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "VEHICLE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    vehicle_ranged = _ranged_wargear("Twin Arachnus Blaze Cannon")
    vehicle.models[0].wargear = [vehicle_ranged]
    custodes_army.add_unit(vehicle)
    _place_unit(game, vehicle, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    vehicle.round_state.advanced_this_round = True
    game.event_system.publish("unit_move_ended", unit=vehicle, action="advance")
    assert _pending_reaction_by_name(custodes_player, "RELENTLESS PERSECUTION") is not None

    ok = custodes_player.stratagems.use(
        "RELENTLESS PERSECUTION",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert vehicle.can_shoot_after_advance(_first_profile(vehicle_ranged)) is True
    assert vehicle.can_charge_after_advance() is False

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert vehicle.can_shoot_after_advance(_first_profile(vehicle_ranged)) is False

    walker_game, walker_player, _walker_enemy_player, walker_army, _walker_enemy_army = _build_game()
    walker = _make_unit(
        "Venerable Contemptor Dreadnought",
        "ac-relentless-persecution-walker",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    walker_ranged = _ranged_wargear("Kheres Pattern Assault Cannon")
    walker.models[0].wargear = [walker_ranged]
    walker_army.add_unit(walker)
    _place_unit(walker_game, walker, 5.0, 5.0)
    walker_game.rebuild_entity_registry()

    _set_phase(walker_game, walker_player, "MOVEMENT_PHASE", current_player_index=0)
    walker.round_state.advanced_this_round = True
    walker_game.event_system.publish("unit_move_ended", unit=walker, action="advance")
    assert _pending_reaction_by_name(walker_player, "RELENTLESS PERSECUTION") is not None

    ok = walker_player.stratagems.use(
        "RELENTLESS PERSECUTION",
        unit=walker,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert walker.can_shoot_after_advance(_first_profile(walker_ranged)) is True
    assert walker.can_charge_after_advance() is True


def test_unstoppable_grants_phase_move_through_terrain_and_cleans_up() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    mounted = _make_unit(
        "Vertus Praetors",
        "ac-unstoppable",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "MOUNTED"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodes_army.add_unit(mounted)
    _place_unit(game, mounted, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "UNSTOPPABLE",
        unit=mounted,
        phase_name="Movement phase",
    )
    assert ok is True
    assert set(mounted.special_rules.get("bearer_unit_phase_move_terrain_only_types", [])) == {
        "advance",
        "fall_back",
        "move",
    }

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert "bearer_unit_phase_move_terrain_only_types" not in mounted.special_rules

    _set_phase(game, custodes_player, "CHARGE_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "UNSTOPPABLE",
        unit=mounted,
        phase_name="Charge phase",
    )
    assert ok is True
    assert set(mounted.special_rules.get("bearer_unit_phase_move_terrain_only_types", [])) == {"charge"}

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert "bearer_unit_phase_move_terrain_only_types" not in mounted.special_rules


def test_wrathful_advance_sets_pile_in_distance_override(monkeypatch) -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-wrathful-advance",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodes_army.add_unit(custodians)
    _place_unit(game, custodians, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "FIGHT_PHASE", current_player_index=0)
    monkeypatch.setattr(custodes_stratagems_module.dice_module, "get_roll", lambda _expr: 2)

    ok = custodes_player.stratagems.use(
        "WRATHFUL ADVANCE",
        unit=custodians,
        phase_name="Fight phase",
    )
    assert ok is True
    assert custodians.special_rules["stratagem_pile_in_distance_override"] == 5.0
    assert custodians.special_rules["stratagem_pile_in_source"] == "WRATHFUL ADVANCE"

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert "stratagem_pile_in_distance_override" not in custodians.special_rules
