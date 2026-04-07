import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        move: int = 6,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    move: int = 6,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        move=move,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Vindication Task Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 1

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_ranged_profile(*, strength: int = 6):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(*, strength: int = 4):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Combat Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesVindicationTaskForce(unittest.TestCase):
    def test_litanies_of_purgation_grants_melee_ap_while_near_objective(self):
        game, sm_player, enemy_player, army_sm, army_enemy = _build_game("Vindication Task Force")
        sm_player.command_points = 5
        attacker = _make_unit(
            "Bladeguard Veterans",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        defender = _make_unit(
            "Enemy Infantry",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        attacker.deployed = True
        defender.deployed = True
        attacker.faction = "SM"
        defender.faction = "EN"
        army_sm.add_unit(attacker)
        army_enemy.add_unit(defender)

        objective_loc = SimpleNamespace(id="obj-litanies", x=0.0, y=0.0, z=0.0, removed=False)
        game.map.objectives = [SimpleNamespace(id="obj-litanies", location=objective_loc)]
        attacker.is_within_objective_range = lambda loc: str(getattr(loc, "id", "")) == "obj-litanies"

        game.rebuild_entity_registry()
        sm_player.stratagems.refresh_available()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)

        ok = sm_player.stratagems.use("LITANIES OF PURGATION", unit=attacker, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(sm_player.command_points), 4)

        melee_profile = _make_melee_profile()
        ranged_profile = _make_ranged_profile()
        self.assertEqual(melee_profile.get_effective_ap(attacker.models[0], defender), -1)
        self.assertEqual(ranged_profile.get_effective_ap(attacker.models[0], defender), 0)

        game.event_system.publish("phase_end", player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
        self.assertEqual(melee_profile.get_effective_ap(attacker.models[0], defender), 0)

    def test_purge_and_sanctify_wound_penalty_applies_for_ancient_on_objective(self):
        game, sm_player, enemy_player, army_sm, army_enemy = _build_game("Vindication Task Force")
        defended = _make_unit(
            "Ancient",
            keywords=["INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        defended.deployed = True
        attacker.deployed = True
        defended.faction = "SM"
        attacker.faction = "EN"
        army_sm.add_unit(defended)
        army_enemy.add_unit(attacker)

        objective_loc = SimpleNamespace(id="obj-a", x=0.0, y=0.0, z=0.0, removed=False)
        objective = SimpleNamespace(id="obj-a", location=objective_loc, controlling_player=sm_player)
        game.map.objectives = [objective]
        defended.is_within_objective_range = lambda loc: str(getattr(loc, "id", "")) == "obj-a"

        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        profile = _make_ranged_profile(strength=6)
        result = profile._wound_target_with_tracking(
            defended,
            attacker.models[0],
            {"distance_to_target": 12.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        modifiers = [str(item or "") for item in list(result.get("modifiers", []) or [])]
        self.assertTrue(any("Purge and Sanctify" in value for value in modifiers))

    def test_purge_and_sanctify_wound_penalty_does_not_apply_to_non_ancient(self):
        game, sm_player, enemy_player, army_sm, army_enemy = _build_game("Vindication Task Force")
        defended = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        defended.deployed = True
        attacker.deployed = True
        defended.faction = "SM"
        attacker.faction = "EN"
        army_sm.add_unit(defended)
        army_enemy.add_unit(attacker)

        objective_loc = SimpleNamespace(id="obj-b", x=0.0, y=0.0, z=0.0, removed=False)
        objective = SimpleNamespace(id="obj-b", location=objective_loc, controlling_player=sm_player)
        game.map.objectives = [objective]
        defended.is_within_objective_range = lambda loc: str(getattr(loc, "id", "")) == "obj-b"

        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        profile = _make_ranged_profile(strength=6)
        result = profile._wound_target_with_tracking(
            defended,
            attacker.models[0],
            {"distance_to_target": 12.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        modifiers = [str(item or "") for item in list(result.get("modifiers", []) or [])]
        self.assertFalse(any("Purge and Sanctify" in value for value in modifiers))

    def test_purge_and_sanctify_allows_righteous_zeal_ending_toward_objective(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game("Vindication Task Force")
        crusader = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        crusader.possible_abilities = [Ability("Righteous Zeal", "SM", "", "")]
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        crusader.deployed = True
        enemy.deployed = True
        crusader.faction = "SM"
        enemy.faction = "EN"
        army_sm.add_unit(crusader)
        army_enemy.add_unit(enemy)
        game.map.units = [crusader, enemy]
        game.rebuild_entity_registry()

        crusader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(0.0, 12.0, 0.0, 0.0)
        objective_loc = SimpleNamespace(id="obj-c", x=8.0, y=0.0, z=0.0, removed=False)
        game.map.objectives = [SimpleNamespace(id="obj-c", location=objective_loc)]

        rules = get_validation_rules(MovementType.HORDE_MOVE, moving_unit=crusader)
        self.assertTrue(bool(rules.get("allow_closest_objective_marker_instead_of_closest_enemy_unit", False)))
        rules["blood_surge_max_distance"] = 6.0

        without_override = dict(rules)
        without_override.pop("allow_closest_objective_marker_instead_of_closest_enemy_unit", None)
        without_override.pop("closest_objective_marker_reason", None)
        invalid_result = validate_final_position(
            crusader.models[0],
            (6.0, 0.0, 0.0),
            without_override,
            game.map,
        )
        self.assertFalse(bool(invalid_result.get("valid", False)))

        valid_result = validate_final_position(
            crusader.models[0],
            (6.0, 0.0, 0.0),
            rules,
            game.map,
        )
        self.assertTrue(bool(valid_result.get("valid", False)))
        self.assertIn("Purge and Sanctify", str(valid_result.get("reason", "")))

    def test_righteous_zeal_move_constraints_and_distance(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game("Vindication Task Force")
        crusader = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        crusader.possible_abilities = [Ability("Righteous Zeal", "SM", "", "")]
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        crusader.deployed = True
        enemy.deployed = True
        crusader.faction = "SM"
        enemy.faction = "EN"
        army_sm.add_unit(crusader)
        army_enemy.add_unit(enemy)
        game.map.units = [crusader, enemy]
        game.rebuild_entity_registry()
        crusader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)

        self.assertTrue(crusader.can_horde_move(game=game, game_map=game.map))
        crusader.mark_horde_move_used(game)
        self.assertFalse(crusader.can_horde_move(game=game, game_map=game.map))

        game.phase = BattleRoundPhases.FIGHT_PHASE
        self.assertTrue(crusader.can_horde_move(game=game, game_map=game.map))

        game.map.is_within_engagement_range = lambda _a, _b: True
        self.assertFalse(crusader.can_horde_move(game=game, game_map=game.map))

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            self.assertEqual(game.roll_horde_move_distance(crusader), 5)


if __name__ == "__main__":
    unittest.main()
