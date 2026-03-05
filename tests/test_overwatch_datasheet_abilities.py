import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class TestOverwatchDatasheetAbilities(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.models_lost = []
        unit.attached_leaders = []
        unit.attached_to = None
        unit.embarked_in = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.has_any_keyword = lambda kw: False
        return unit

    def test_inescapable_death_detected_with_threshold_and_army_turn_limit(self):
        ability_desc = (
            "Once per turn, one unit from your army with this ability can be targeted with the Fire Overwatch "
            "Stratagem for 0CP, even if you have already used that Stratagem on a different unit this phase. "
            "In addition, each time you target this unit with the Fire Overwatch Stratagem, while resolving that "
            "Stratagem, hits are scored on unmodified Hit rolls of 2+."
        )
        ability = Ability("Inescapable Death", "NEC", ability_desc, "Datasheet", "")

        army = Army("Necrons", detachment_type="Other")
        army.faction_id = "NEC"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Necron", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(
            turn=2,
            current_player_index=0,
            get_current_player=lambda: player,
            players=[player],
        )
        player.game = game

        unit_a = self._make_unit("Hexmark A", army, abilities=[ability])
        unit_b = self._make_unit("Hexmark B", army, abilities=[ability])
        enemy = self._make_unit("Enemy", enemy_army)

        rule = unit_a.get_datasheet_overwatch_stratagem_discount_rule()
        self.assertIsNotNone(rule)
        self.assertTrue(bool(rule.get("repeat_bypass", False)))
        self.assertEqual(str(rule.get("limit", "")), "army_turn")
        self.assertEqual(
            unit_a.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game),
            2,
        )

        self.assertTrue(unit_a.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))
        self.assertTrue(unit_b.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))
        unit_a.mark_datasheet_overwatch_discount_used(
            game,
            source="Inescapable Death",
            stratagem_name="Fire Overwatch",
        )
        self.assertFalse(unit_a.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))
        self.assertFalse(unit_b.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))

    def test_apply_stratagem_cp_cost_inescapable_death_overwatch(self):
        ability_desc = (
            "Once per turn, one unit from your army with this ability can be targeted with the Fire Overwatch "
            "Stratagem for 0CP, even if you have already used that Stratagem on a different unit this phase. "
            "In addition, each time you target this unit with the Fire Overwatch Stratagem, while resolving that "
            "Stratagem, hits are scored on unmodified Hit rolls of 2+."
        )
        ability = Ability("Inescapable Death", "NEC", ability_desc, "Datasheet", "")

        army = Army("Necrons", detachment_type="Other")
        army.faction_id = "NEC"
        unit = self._make_unit("Hexmark Destroyer", army, abilities=[ability])

        player = Player("Necron", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=1, current_player_index=0, get_current_player=lambda: player, players=[player])
        player.game = game
        player.stratagems = SimpleNamespace(_used_this_turn={})

        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
        player.set_next_optional_decision("DATASHEET_OVERWATCH_DISCOUNT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(bool(applied.get("datasheet_overwatch_discount_use", False)))

        player.stratagems._used_this_turn = {"OVERWATCH": True}
        player.set_next_optional_decision("DATASHEET_OVERWATCH_DISCOUNT", False)
        denied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertTrue(bool(denied.get("denied", False)))

    def test_defensive_stance_overwatch_threshold_improves_on_objective(self):
        ability_desc = (
            "Each time you target this unit with the Fire Overwatch Stratagem, while resolving that Stratagem, "
            "hits are scored on unmodified Hit rolls of 5+, or unmodified Hit rolls of 4+ instead if this unit "
            "is within range of an objective marker."
        )
        ability = Ability("Defensive Stance", "TYR", ability_desc, "Datasheet", "")

        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Tyranid", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(
            turn=2,
            current_player_index=0,
            get_current_player=lambda: player,
            players=[player],
            map=None,
        )
        player.game = game

        unit = self._make_unit("Hive Guard", army, abilities=[ability])
        enemy = self._make_unit("Enemy", enemy_army)

        unit.is_within_any_objective_range = lambda game_map=None: False
        self.assertEqual(
            unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game),
            5,
        )
        unit.is_within_any_objective_range = lambda game_map=None: True
        self.assertEqual(
            unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game),
            4,
        )

    def test_hive_defences_allows_repeat_overwatch_for_zero_cp_once_per_turn_per_model(self):
        ability_desc = (
            "You can target this model with the Fire Overwatch Stratagem for 0CP, and can do so even if you have "
            "already targeted a different unit with that Stratagem this turn. This model can only be targeted with "
            "that Stratagem once per turn."
        )
        ability = Ability("Hive Defences", "TYR", ability_desc, "Datasheet", "")

        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        unit = self._make_unit("Sporocyst", army, abilities=[ability])

        player = Player("Tyranid", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=3, current_player_index=0, get_current_player=lambda: player, players=[player])
        player.game = game
        player.stratagems = SimpleNamespace(_used_this_turn={"OVERWATCH": True})

        rule = unit.get_datasheet_overwatch_stratagem_discount_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(str(rule.get("limit", "")), "unit_turn")
        self.assertTrue(bool(rule.get("repeat_bypass", False)))
        self.assertTrue(unit.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))

        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
        player.set_next_optional_decision("DATASHEET_OVERWATCH_DISCOUNT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(bool(applied.get("datasheet_overwatch_discount_use", False)))

        unit.mark_datasheet_overwatch_discount_used(
            game,
            source="Hive Defences",
            stratagem_name="Fire Overwatch",
        )
        self.assertFalse(unit.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))

    def test_defensive_array_allows_repeat_overwatch_for_zero_cp_once_per_turn_per_fortification(self):
        ability_desc = (
            "You can target this FORTIFICATION with the Fire Overwatch Stratagem for 0CP, and can do so even if "
            "you have already targeted another unit with that Stratagem this turn. This FORTIFICATION can only be "
            "targeted with that Stratagem once per turn."
        )
        ability = Ability("Defensive Array", "SM", ability_desc, "Datasheet", "")

        army = Army("Space Marines", detachment_type="Other")
        army.faction_id = "SM"
        unit = self._make_unit("Hammerfall Bunker", army, abilities=[ability])

        player = Player("Astartes", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=1, current_player_index=0, get_current_player=lambda: player, players=[player])
        player.game = game
        player.stratagems = SimpleNamespace(_used_this_turn={"OVERWATCH": True})

        rule = unit.get_datasheet_overwatch_stratagem_discount_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(str(rule.get("limit", "")), "unit_turn")
        self.assertTrue(bool(rule.get("repeat_bypass", False)))
        self.assertTrue(unit.can_use_datasheet_overwatch_stratagem_discount(game, stratagem_name="OVERWATCH"))

        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
        player.set_next_optional_decision("DATASHEET_OVERWATCH_DISCOUNT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(bool(applied.get("datasheet_overwatch_discount_use", False)))

    def test_sentinel_protocols_overwatch_threshold_select_wording(self):
        ability_desc = (
            "Each time you select this unit for the Fire Overwatch Stratagem, hits are scored on unmodified Hit rolls "
            "of 4+ when resolving that Stratagem."
        )
        ability = Ability("Sentinel Protocols", "SM", ability_desc, "Datasheet", "")

        army = Army("Space Marines", detachment_type="Other")
        army.faction_id = "SM"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Astartes", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(
            turn=1,
            current_player_index=0,
            get_current_player=lambda: player,
            players=[player],
            map=None,
        )
        player.game = game

        unit = self._make_unit("Firestrike Servo-turrets", army, abilities=[ability])
        enemy = self._make_unit("Enemy", enemy_army)
        self.assertEqual(
            unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game),
            4,
        )

    def test_sentinel_protocols_overwatch_threshold_fortification_select_wording(self):
        ability_desc = (
            "Each time you select this FORTIFICATION for the Fire Overwatch Stratagem, hits are scored on unmodified "
            "Hit rolls of 5+ when resolving that Stratagem."
        )
        ability = Ability("Sentinel Protocols", "TAU", ability_desc, "Datasheet", "")

        army = Army("Tau Empire", detachment_type="Other")
        army.faction_id = "TAU"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        player = Player("Tau", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(
            turn=1,
            current_player_index=0,
            get_current_player=lambda: player,
            players=[player],
            map=None,
        )
        player.game = game

        unit = self._make_unit("Drone Sentry Turret", army, abilities=[ability])
        enemy = self._make_unit("Enemy", enemy_army)
        self.assertEqual(
            unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game),
            5,
        )


if __name__ == "__main__":
    unittest.main()
