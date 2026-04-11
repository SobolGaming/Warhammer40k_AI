import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.battlefield.objective_sites import Objective, ObjectiveCategory
from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
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
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        model_count=1,
        movement=6,
        toughness=4,
        wounds=3,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{str(name).lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name,
    *,
    faction_name="Imperial Agents",
    keywords=None,
    faction_keywords=None,
    model_count=1,
    movement=6,
    toughness=4,
    wounds=3,
):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    ia_army = Army.with_detachment("Imperial Agents", "Ordo Malleus Daemon Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    ia_player.command_points = 10
    enemy_player.command_points = 10
    return game, ia_player, enemy_player, ia_army, enemy_army


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    for player in players:
        player.stratagems.refresh_available()


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    expected = str(name or "").strip().upper()
    for pending in list(getattr(stratagems, "_pending_reactions", []) or []):
        if str(pending.get("stratagem", "") or "").strip().upper() == expected:
            return pending
    return None


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _make_ranged_profile(unit: Unit, *, name: str = "Test Rifle", description: str = ""):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [weapon]
    return weapon.profiles["default"]


def _make_melee_profile(unit: Unit, *, name: str = "Test Blade", description: str = ""):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [weapon]
    return weapon.profiles["default"]


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


class TestImperialAgentsOrdoMalleusStratagems(unittest.TestCase):
    def test_ordo_malleus_stratagem_descriptors_registered(self):
        expected = {
            "000009135002": ("Ritual of Warding", "sticky_objective_with_daemon_reserves_denial"),
            "000009135003": ("Rites of Exorcism", "force_battleshock_then_agents_gain_devastating_wounds_against_target"),
            "000009135004": ("Steel Heart", "shoot_and_charge_after_fall_back"),
            "000009135005": ("Truesilver Armour", "defensive_ap_worsen"),
            "000009135006": ("Hexagrammic Wards", "enemy_psychic_weapons_become_hazardous"),
            "000009135007": ("Psybolt Ammunition", "grant_ranged_lethal_hits_and_psychic"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(getattr(by_id, "name", "") or ""), expected_name)
            self.assertEqual(str(getattr(by_id, "effect", "") or ""), expected_effect)
            self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), stratagem_id)

    def test_psybolt_ammunition_grants_lethal_hits_and_psychic_until_phase_end(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(terminators)
        enemy_army.add_unit(enemy)
        _place_unit(game, terminators, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)
        profile = _make_ranged_profile(terminators)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("PSYBOLT AMMUNITION", unit=terminators, phase_name="Shooting phase")
        self.assertTrue(ok)

        bonuses = terminators.get_attack_keyword_bonuses(
            target=enemy,
            attack_type="ranged",
            model=terminators.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits")))
        self.assertTrue(profile._is_psychic_attack(terminators.models[0]))
        self.assertTrue(any("PSYBOLT AMMUNITION" in str(source).upper() for source in list(bonuses.get("sources", []) or [])))

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        bonuses_after = terminators.get_attack_keyword_bonuses(
            target=enemy,
            attack_type="ranged",
            model=terminators.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertFalse(bool(bonuses_after.get("lethal_hits")))
        self.assertFalse(profile._is_psychic_attack(terminators.models[0]))

    def test_steel_heart_queues_after_fall_back_and_allows_shoot_and_charge_until_turn_end(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        terminators = _make_unit(
            "Grey Knights Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(terminators)
        _place_unit(game, terminators, 10.0, 10.0)
        profile = _make_ranged_profile(terminators)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        self.assertFalse(terminators.can_shoot_after_fall_back(profile))
        self.assertFalse(terminators.can_charge_after_fall_back())

        terminators.round_state.fell_back_this_round = True
        game.event_system.publish("unit_move_ended", unit=terminators, action="fall_back")
        pending = _pending_by_name(ia_player.stratagems, "STEEL HEART")
        self.assertIsNotNone(pending)
        self.assertIn(terminators, list(pending.get("candidates") or []))

        ok = ia_player.stratagems.use(
            "STEEL HEART",
            unit=terminators,
            phase_name="Movement phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertTrue(terminators.can_shoot_after_fall_back(profile))
        self.assertTrue(terminators.can_charge_after_fall_back())

        game.turn += 1
        self.assertFalse(terminators.can_shoot_after_fall_back(profile))
        self.assertFalse(terminators.can_charge_after_fall_back())

    def test_hexagrammic_wards_queues_for_targeted_unit_and_forces_psychic_hazardous(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        defender = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        attacker = _make_unit(
            "Enemy Psykers",
            faction_name="Enemy",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, attacker, 16.0, 10.0)
        profile = _make_ranged_profile(attacker, description="Psychic")
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        ia_player.stratagems._on_shooting_targets_selected(attacking_unit=attacker, target_units=[defender])
        pending = _pending_by_name(ia_player.stratagems, "HEXAGRAMMIC WARDS")
        self.assertIsNotNone(pending)
        self.assertIn(defender, list(pending.get("candidates") or []))

        ok = ia_player.stratagems.use(
            "HEXAGRAMMIC WARDS",
            unit=defender,
            attacking_unit=attacker,
            target_units=[defender],
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        with patch("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 1):
            result = profile.attack(defender, attacker.models[0], game_map=game.map)

        self.assertIsNotNone(result)
        self.assertEqual(int(result.hazardous_roll or 0), 1)
        self.assertEqual(int(result.hazardous_damage or 0), 3)
        self.assertTrue(
            any("HEXAGRAMMIC WARDS" in str(note).upper() for note in list(result.attacks_special_modifiers or []))
        )

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        active_after, _source_after = attacker.imperial_agents_hexagrammic_wards_hazardous(
            is_psychic_attack=True,
            game=game,
        )
        self.assertFalse(active_after)

    def test_rites_of_exorcism_applies_in_opponent_fight_phase_after_failed_battleshock(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        source = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        allied_attackers = _make_unit(
            "Imperial Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        daemon = _make_unit(
            "Daemon Pack",
            faction_name="Enemy",
            keywords=["INFANTRY", "DAEMON"],
            faction_keywords=["CHAOS", "DAEMON", "ENEMY"],
        )
        ia_army.add_unit(source)
        ia_army.add_unit(allied_attackers)
        enemy_army.add_unit(daemon)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, allied_attackers, 12.0, 10.0)
        _place_unit(game, daemon, 16.0, 10.0)
        profile = _make_melee_profile(allied_attackers)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        battle_shock_turns = []

        def _force_failed_battle_shock(current_turn=0, source=""):
            battle_shock_turns.append((int(current_turn or 0), str(source or "")))
            game.event_system.publish("battle_shock_test_resolved", unit=daemon, passed=False)

        daemon.force_battle_shock_test = _force_failed_battle_shock

        _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
        ok = ia_player.stratagems.use(
            "RITES OF EXORCISM",
            unit=source,
            enemy_unit=daemon,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(battle_shock_turns, [(2, "RITES OF EXORCISM")])

        bonuses = allied_attackers.get_attack_keyword_bonuses(
            target=daemon,
            attack_type="melee",
            model=allied_attackers.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertTrue(bool(bonuses.get("devastating_wounds")))
        self.assertTrue(any("RITES OF EXORCISM" in str(source).upper() for source in list(bonuses.get("sources", []) or [])))

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        bonuses_after = allied_attackers.get_attack_keyword_bonuses(
            target=daemon,
            attack_type="melee",
            model=allied_attackers.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertFalse(bool(bonuses_after.get("devastating_wounds")))

    def test_ritual_of_warding_queues_in_opponent_command_phase_denies_daemon_reserves_and_breaks_on_turn_boundary(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        warding_unit = _make_unit(
            "Ordo Malleus Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR", "ORDO MALLEUS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_controller = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        arriving_daemon = _make_unit(
            "Daemon Reinforcements",
            faction_name="Enemy",
            keywords=["INFANTRY", "DAEMON"],
            faction_keywords=["CHAOS", "DAEMON", "ENEMY"],
        )
        objective = _make_objective("Central Objective", 10.0, 10.0)
        objective.location.controlling_player = ia_player
        ia_army.add_unit(warding_unit)
        enemy_army.add_unit(enemy_controller)
        enemy_army.add_unit(arriving_daemon)
        _place_unit(game, warding_unit, 10.0, 10.0)
        _place_unit(game, enemy_controller, 10.0, 14.0)
        game.map.objectives = [objective]
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
        pending = _pending_by_name(ia_player.stratagems, "RITUAL OF WARDING")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            "RITUAL OF WARDING",
            unit=warding_unit,
            objective=objective,
            phase_name="Command phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, ia_player)
        self.assertEqual(str(objective.location.sticky_source or ""), "imperial_agents_ritual_of_warding")

        for model in list(warding_unit.models or []):
            model.set_location(40.0, 40.0, 0.0, 0.0)
        for model in list(enemy_controller.models or []):
            model.set_location(10.0, 10.0, 0.0, 0.0)
        objective.location.update_control(game)
        self.assertIs(objective.location.controlling_player, ia_player)

        arriving_daemon.deployed = False
        arriving_daemon.reserve_status = "reserves"
        arriving_daemon._started_in_reserves = True
        arriving_daemon.special_rules["bearer_unit_deep_strike"] = True

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1
        denied_position = (15.5, 10.0, 0.0)
        denied = _evaluate_reserves_arrival_positions(
            game,
            arriving_daemon,
            _model_positions_for(arriving_daemon, denied_position),
        )
        self.assertTrue(bool(list(denied.get("errors") or [])))

        game._evaluate_corrupt_realspace_turn_boundary(timing="start", player=enemy_player)
        self.assertIsNone(objective.location.sticky_controller)
        self.assertIs(objective.location.controlling_player, enemy_player)

        allowed = _evaluate_reserves_arrival_positions(
            game,
            arriving_daemon,
            _model_positions_for(arriving_daemon, denied_position),
        )
        self.assertEqual(list(allowed.get("errors") or []), [])


if __name__ == "__main__":
    unittest.main()
