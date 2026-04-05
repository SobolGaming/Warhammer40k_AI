import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "10",
                "Sv": "3",
                "W": "14",
                "Ld": "6",
                "OC": "3",
                "base_size": "120mm x 92mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    ds = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(ds)


def _make_players(active_units, opponent_units, *, turn=1):
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army1 = Army("Active", "Test")
    army2 = Army("Opponent", "Test")
    army1.units = list(active_units if isinstance(active_units, (list, tuple)) else [active_units])
    army2.units = list(opponent_units if isinstance(opponent_units, (list, tuple)) else [opponent_units])

    for unit in army1.units:
        unit.set_parent_army(army1)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in army2.units:
        unit.set_parent_army(army2)
        unit.deployed = True
        unit.reserve_status = "deployed"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game = SimpleNamespace(turn=turn, current_player_index=0, players=[p1, p2])
    game.get_current_player = lambda: p1
    p1.set_game(game)
    p2.set_game(game)
    return p1, p2, game


class TestCsmDaemonforge(unittest.TestCase):
    def _daemonforge_ability(self):
        return {
            "name": "Daemonforge",
            "description": (
                "Once per Fight phase, one unit from your army with this ability can be targeted "
                "with the Counter-offensive Stratagem for 0CP, even if you have already targeted "
                "a different unit with that Stratagem this phase."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

    def _counter_offensive(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        return Stratagem(
            id="counter-offensive",
            name="Counter-offensive",
            type="Core",
            description="",
            cp_cost=2,
            turn="Either",
            phase="Fight phase",
            detachment="",
            faction_id="",
        )

    def test_daemonforge_allows_one_extra_counter_offensive_for_zero_cp(self):
        class _FightManager:
            def __init__(self):
                self.fought_units = set()
                self._current_player = None
                self._opponent_player = None
                self._forced_next_unit = None
                self._forced_next_player = None

            def _canonical_unit_for_fight(self, unit):
                return unit

            def force_next_unit(self, unit, player):
                self._forced_next_unit = unit
                self._forced_next_player = player
                return True

        defiler = _make_unit(
            "Defiler",
            abilities=[self._daemonforge_ability()],
            keywords=["VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"])
        player, opponent, game = _make_players(defiler, enemy, turn=2)
        player.command_points = 0
        player.stratagems._used_stratagems_this_phase.add("COUNTER-OFFENSIVE")
        player.stratagems._current_phase_name = "Fight phase"
        game.map = SimpleNamespace()
        game.fight_phase_manager = _FightManager()
        defiler.is_eligible_to_fight = lambda _map: True

        strat = self._counter_offensive()
        player.stratagems.available = [strat]

        player.set_next_optional_decision("DAEMONFORGE_COUNTER_OFFENSIVE", True)
        self.assertTrue(player.stratagems.can_use("Counter-offensive", target_unit=defiler, phase_name="Fight phase"))

        used = player.stratagems.use("Counter-offensive", target_unit=defiler, phase_name="Fight phase")
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)
        self.assertTrue(player.stratagems._daemonforge_used_this_phase())

        player.set_next_optional_decision("DAEMONFORGE_COUNTER_OFFENSIVE", True)
        self.assertFalse(player.stratagems.use("Counter-offensive", target_unit=defiler, phase_name="Fight phase"))


if __name__ == "__main__":
    unittest.main()
