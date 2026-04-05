import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport


def _make_unit(name, *, keywords=None, faction_keywords=None, transport=""):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        transport=transport,
    )
    return Unit(datasheet)


class TestRushToTheFray(unittest.TestCase):
    def _build_game(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        we_army = Army("World Eaters", "Goretrack Onslaught")
        we_army.faction_id = "WE"
        enemy_army = Army("Enemy", "Detachment")
        enemy_army.faction_id = "EN"

        p1 = Player("P1", control=PlayerControl.LOCAL, army=we_army)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
        game.add_player(p1)
        game.add_player(p2)
        game.turn = 1

        return game, we_army, enemy_army

    def _embark(self, transport, passenger):
        transport.transport_passengers = [passenger]
        passenger.embarked_in = transport

    def test_disembark_grants_charge_bonus_and_lance(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.utility.model_base import Base, BaseType

        game, we_army, enemy_army = self._build_game()

        transport = _make_unit(
            "Transport",
            keywords=["Transport"],
            transport="Transport Capacity 6",
        )
        passenger = _make_unit("Passengers", faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", keywords=["Infantry"])

        we_army.add_unit(transport)
        we_army.add_unit(passenger)
        enemy_army.add_unit(enemy)

        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)

        self._embark(transport, passenger)
        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(ok)
        self.assertTrue(passenger.special_rules.get("goretrack_onslaught_active"))

        mods = game.get_charge_roll_modifiers(passenger, target_unit=enemy)
        self.assertIn((1, "Goretrack Onslaught"), mods)

        attacker = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker.parent_unit = passenger
        passenger.models = [attacker]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = enemy
        enemy.models = [target_model]

        passenger.round_state.charged_this_round = True

        parent_wargear = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent_wargear,
        )

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            wound_res = profile._wound_target_with_tracking(enemy, attacker, {"_aura_attack_mods": aura_stub})
        finally:
            wargear_mod.get_roll = old_get_roll

        self.assertTrue(any("Goretrack Onslaught" in mod for mod in wound_res.get("modifiers", [])))


if __name__ == "__main__":
    unittest.main()
