import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        transport="",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
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
        self.transport = transport


def _make_unit(name, *, abilities=None, keywords=None, transport=""):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        transport=transport,
    )
    return Unit(datasheet)


class TestTransportDisembarkAbilities(unittest.TestCase):
    def _build_game(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        army1 = Army.with_detachment("Test", "Detachment")
        army1.faction_id = "T1"
        army2 = Army.with_detachment("Enemy", "Detachment")
        army2.faction_id = "T2"

        p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
        game.add_player(p1)
        game.add_player(p2)

        return game, army1, army2

    def _embark(self, transport, passenger):
        transport.transport_passengers = [passenger]
        passenger.embarked_in = transport

    def test_assault_ramp_allows_charge_after_normal_move(self):
        assault_ramp = {
            "name": "Assault Ramp",
            "description": (
                "Each time a unit disembarks from this model after it has made a Normal move, "
                "that unit is still eligible to declare a charge this turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

        game, army1, army2 = self._build_game()
        transport = _make_unit(
            "Transport",
            abilities=[assault_ramp],
            keywords=["Transport"],
            transport="Transport Capacity 10",
        )
        passenger = _make_unit("Passengers")
        enemy = _make_unit("Enemy", keywords=["Infantry"])

        army1.add_unit(transport)
        army1.add_unit(passenger)
        army2.add_unit(enemy)

        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)

        transport.round_state.moved_this_round = True
        transport.round_state.remained_stationary_this_round = False

        self._embark(transport, passenger)
        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
        self.assertTrue(ok)
        self.assertTrue(passenger.round_state.disembarked_from_moved_transport)
        self.assertFalse(passenger.round_state.disembarked_cannot_charge)
        self.assertTrue(passenger.can_declare_charge_against(enemy, game))

    def test_assault_vehicle_allows_disembark_after_advance_but_blocks_charge(self):
        assault_vehicle = {
            "name": "Assault Vehicle",
            "description": (
                "Units can disembark from this TRANSPORT after it has Advanced. "
                "Units that do so count as having made a Normal move that phase, and cannot declare a charge "
                "in the same turn, but can otherwise act normally."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        advance_and_charge = {
            "name": "Swift Pursuit",
            "description": "This unit is eligible to declare a charge in a turn in which it advanced.",
            "type": "Datasheet",
            "parameter": "",
        }

        game, army1, army2 = self._build_game()
        transport = _make_unit(
            "Transport",
            abilities=[assault_vehicle],
            keywords=["Transport"],
            transport="Transport Capacity 10",
        )
        passenger = _make_unit("Passengers", abilities=[advance_and_charge])
        enemy = _make_unit("Enemy", keywords=["Infantry"])

        army1.add_unit(transport)
        army1.add_unit(passenger)
        army2.add_unit(enemy)

        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)

        transport.round_state.moved_this_round = True
        transport.round_state.remained_stationary_this_round = False
        transport.round_state.advanced_this_round = True

        self._embark(transport, passenger)
        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)
        self.assertTrue(ok)
        self.assertTrue(passenger.round_state.disembarked_from_moved_transport)
        self.assertTrue(passenger.round_state.disembarked_cannot_charge)

        # Even if the unit would normally charge after advancing, disembark should block it.
        passenger.round_state.advanced_this_round = True
        self.assertFalse(passenger.can_declare_charge_against(enemy, game))


if __name__ == "__main__":
    unittest.main()
