import unittest
from types import SimpleNamespace


class TestTyranidsEnhancements(unittest.TestCase):
    class _MockDatasheet:
        def __init__(
            self,
            name,
            *,
            faction_name="Tyranids",
            keywords=None,
            faction_keywords=None,
            cost=100,
            wounds="6",
            abilities=None,
        ):
            self.name = name
            self.faction_data = {"name": faction_name}
            self.keywords = list(keywords or [])
            self.faction_keywords = list(faction_keywords or [])
            self.datasheets_unit_composition = [{"description": "1 Test Model"}]
            self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
            self.datasheets_models = [
                {
                    "M": "6",
                    "T": "5",
                    "Sv": "3",
                    "W": str(wounds),
                    "Ld": "6",
                    "OC": "1",
                    "base_size": "32mm",
                    "inv_sv": "7",
                    "inv_sv_descr": "none",
                }
            ]
            self.datasheets_wargear = []
            self.datasheets_options = [{"description": "none"}]
            self.datasheets_abilities = list(abilities or [])
            self.loadout = "This model is equipped with: nothing"
            self.attached_to = []

    def _make_unit(
        self,
        name="Adaptive Beast",
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        from warhammer40k_ai.units.unit import Unit

        datasheet = self._MockDatasheet(
            name,
            faction_name="Tyranids",
            keywords=list(keywords or ["TYRANIDS"]),
            faction_keywords=list(faction_keywords or ["TYRANIDS"]),
            abilities=list(abilities or []),
        )
        return Unit(datasheet)

    def _build_game(self, detachment_type: str = "Assimilation Swarm"):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        tyr_army = Army("Tyranids", detachment_type)
        tyr_army.faction_id = "TYR"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
        enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
        game.add_player(tyr_player)
        game.add_player(enemy_player)
        game.turn = 1
        return game, tyr_army, enemy_army, tyr_player, enemy_player

    def _set_unit_position(self, unit, x: float, y: float):
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.embarked_in = None
        for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
            model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)

    def test_adaptive_biology_fnp_upgrades_after_damage(self):
        from warhammer40k_ai.rules.enhancement import Enhancement, maybe_upgrade_adaptive_biology

        unit = self._make_unit()
        Enhancement(
            id="000008348005",
            name="Adaptive Biology",
            faction_id="TYR",
            detachment="Invasion Fleet",
            points=25,
            description="",
        ).apply_to_unit(unit)

        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(5, fnp_values)
        self.assertNotIn(4, fnp_values)

        unit.models[0].wounds = max(0, int(unit.models[0].wounds) - 1)
        upgraded = maybe_upgrade_adaptive_biology(unit)
        self.assertTrue(upgraded)

        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(4, fnp_values)
        self.assertTrue(unit.special_rules.get("enhancement_adaptive_biology_upgraded"))

    def test_adaptive_biology_turn_start_checks_all_players(self):
        from warhammer40k_ai.engine.game import Battlefield, Game
        from warhammer40k_ai.rules.enhancement import Enhancement

        unit = self._make_unit("Opposing Leader")
        Enhancement(
            id="000008348005",
            name="Adaptive Biology",
            faction_id="TYR",
            detachment="Invasion Fleet",
            points=25,
            description="",
        ).apply_to_unit(unit)

        unit.models[0].wounds = max(0, int(unit.models[0].wounds) - 1)

        army = SimpleNamespace(units=[unit])
        player = SimpleNamespace(get_army=lambda: army)

        game = Game(Battlefield(width=44, height=30), players=[])
        game.players = [player]

        game._apply_adaptive_biology_turn_start()
        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(4, fnp_values)

    def test_instinctive_defence_grants_fights_first_and_heroic_intervention_zero_cp_near_harvester(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        game, tyr_army, _enemy_army, tyr_player, _enemy_player = self._build_game("Assimilation Swarm")
        bearer_unit = self._make_unit(
            "Assimilator Prime",
            keywords=["TYRANIDS", "INFANTRY", "CHARACTER"],
            faction_keywords=["TYRANIDS"],
        )
        harvester = self._make_unit(
            "Haruspex",
            keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
            faction_keywords=["TYRANIDS"],
        )
        tyr_army.add_unit(bearer_unit)
        tyr_army.add_unit(harvester)
        self._set_unit_position(bearer_unit, 10.0, 10.0)
        self._set_unit_position(harvester, 14.0, 10.0)

        Enhancement(
            id="000008412003",
            name="Instinctive Defence",
            faction_id="TYR",
            detachment="Assimilation Swarm",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
        preview = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=bearer_unit,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(bool(bearer_unit.has_instinctive_defence_fight_first(game=game)))
        self.assertTrue(bool(bearer_unit.has_fight_first()))

        tyr_player.set_next_optional_decision("INSTINCTIVE_DEFENCE_HEROIC_INTERVENTION", True)
        first = tyr_player.apply_stratagem_cp_cost(strat, target_unit=bearer_unit)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("instinctive_defence_heroic_intervention_use", False)))

        self._set_unit_position(harvester, 30.0, 30.0)
        bearer_unit._ability_cache = {}
        self.assertFalse(bool(bearer_unit.has_instinctive_defence_fight_first(game=game)))
        fallback_preview = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=bearer_unit,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(fallback_preview.get("cost", -1)), 1)

    def test_pheromone_trail_allows_rapid_ingress_zero_cp_once_per_battle_round(self):
        game, tyr_army, _enemy_army, tyr_player, _enemy_player = self._build_game("Invasion Fleet")
        ability = {
            "name": "Pheromone Trail",
            "description": (
                "Once per battle round, you can target this unit with the Rapid Ingress Stratagem for 0CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = self._make_unit(
            "Lictor",
            keywords=["TYRANIDS", "INFANTRY"],
            faction_keywords=["TYRANIDS"],
            abilities=[ability],
        )
        tyr_army.add_unit(unit)
        unit.deployed = False
        unit.reserve_status = "reserves"

        strat = SimpleNamespace(name="Rapid Ingress", cp_cost=1)
        preview = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=unit,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", -1)), 0)

        tyr_player.set_next_optional_decision("PHEROMONE_TRAIL_RAPID_INGRESS", True)
        first = tyr_player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("pheromone_trail_rapid_ingress_use", False)))
        self.assertTrue(bool(unit.pheromone_trail_used_this_battle_round(game)))

        tyr_player.set_next_optional_decision("PHEROMONE_TRAIL_RAPID_INGRESS", True)
        second = tyr_player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("pheromone_trail_rapid_ingress_use", False)))

        game.turn = 2
        preview_next_round = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=unit,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview_next_round.get("cost", -1)), 0)


if __name__ == "__main__":
    unittest.main()
