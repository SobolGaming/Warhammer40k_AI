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
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
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


class _Map:
    def __init__(self, units):
        self._units = list(units)

    def get_enemy_units(self, unit):
        army = unit.get_parent_army()
        return [u for u in self._units if u.get_parent_army() is not army]

    def is_within_engagement_range(self, _unit_a, _unit_b):
        return True


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
    p1.command_points = 1
    p2.command_points = 1
    game = SimpleNamespace(turn=turn, current_player_index=0, players=[p1, p2])
    game.get_current_player = lambda: p1
    p1.set_game(game)
    p2.set_game(game)
    game.map = _Map(list(army1.units) + list(army2.units))
    return p1, p2, game


class TestCsmVoiceEater(unittest.TestCase):
    def _voice_eater_ability(self):
        return {
            "name": "Voice Eater",
            "description": (
                "Enemy units (excluding MONSTERS and VEHICLES) cannot be targeted with Stratagems "
                "while they are within Engagement Range of the bearer's unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

    def _stratagem(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        return Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

    def test_voice_eater_blocks_stratagem_targeting_for_non_vehicle_non_monster(self):
        target = _make_unit("Target", keywords=["INFANTRY"])
        source = _make_unit("Nemesis Claw", abilities=[self._voice_eater_ability()], keywords=["INFANTRY"])

        player, opponent, game = _make_players(target, source, turn=1)
        strat = self._stratagem()

        self.assertFalse(strat.can_use(player, game, target_unit=target))

    def test_voice_eater_does_not_block_vehicle_targets(self):
        target = _make_unit("Target Vehicle", keywords=["VEHICLE"])
        source = _make_unit("Nemesis Claw", abilities=[self._voice_eater_ability()], keywords=["INFANTRY"])

        player, opponent, game = _make_players(target, source, turn=1)
        strat = self._stratagem()

        self.assertTrue(strat.can_use(player, game, target_unit=target))


if __name__ == "__main__":
    unittest.main()
