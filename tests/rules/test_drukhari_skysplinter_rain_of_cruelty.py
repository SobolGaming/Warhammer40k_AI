from __future__ import annotations

import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name,
        keywords=None,
        faction_keywords=None,
        transport="",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
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
        self.transport = str(transport or "")


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None, transport=""):
    from warhammer40k_ai.units.unit import Unit

    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            transport=transport,
        )
    )


class TestDrukhariSkysplinterRainOfCruelty(unittest.TestCase):
    def _build_game(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        drukhari_army = Army("Drukhari", "Skysplinter Assault")
        drukhari_army.faction_id = "DRU"
        enemy_army = Army("Enemy", "Detachment")
        enemy_army.faction_id = "EN"

        p1 = Player("P1", control=PlayerControl.REMOTE, army=drukhari_army)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
        game.add_player(p1)
        game.add_player(p2)
        game.turn = 1
        game.current_player_index = 0
        return game, drukhari_army, enemy_army

    def _setup_disembark_units(self):
        game, drukhari_army, enemy_army = self._build_game()
        transport = _make_unit(
            "Raider",
            faction_name="Drukhari",
            keywords=["TRANSPORT", "VEHICLE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        passenger = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(passenger)
        enemy_army.add_unit(enemy)

        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)

        transport.add_passenger(passenger, game_map=game.map)
        passenger.round_state.embarked_this_round = False
        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(ok)
        return game, drukhari_army, passenger, enemy

    def test_rain_of_cruelty_grants_ranged_ignores_cover_on_disembark_until_turn_end(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, drukhari_army, passenger, enemy = self._setup_disembark_units()
        self.assertTrue(bool(passenger.special_rules.get("rain_of_cruelty_active")))
        self.assertEqual(int(passenger.special_rules.get("rain_of_cruelty_turn", 0) or 0), 1)
        self.assertEqual(
            str(passenger.special_rules.get("rain_of_cruelty_turn_owner", "") or ""),
            str(getattr(game.players[0], "id", "") or ""),
        )

        ranged_parent = SimpleNamespace(name="Splinter Rifle", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "3",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        attack_instance = {"damage_characteristic": 1}
        profile._hit_target_with_tracking(
            enemy,
            passenger.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("ignores_cover", False)))

        game.current_player_index = 1
        enemy_turn_attack = {"damage_characteristic": 1}
        profile._hit_target_with_tracking(
            enemy,
            passenger.models[0],
            enemy_turn_attack,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(enemy_turn_attack.get("ignores_cover", False)))

        game.current_player_index = 0
        game.turn = 2
        next_turn_attack = {"damage_characteristic": 1}
        profile._hit_target_with_tracking(
            enemy,
            passenger.models[0],
            next_turn_attack,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(next_turn_attack.get("ignores_cover", False)))

        self.assertTrue(bool(drukhari_army.drukhari_detachments.is_skysplinter_assault()))

    def test_rain_of_cruelty_grants_melee_lance_bonus_when_charging(self):
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.units.wargear import WargearProfile

        _game, _drukhari_army, passenger, enemy = self._setup_disembark_units()
        passenger.round_state.charged_this_round = True

        melee_parent = SimpleNamespace(name="Agoniser", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "3",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
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
            wound_result = profile._wound_target_with_tracking(
                enemy,
                passenger.models[0],
                {"_aura_attack_mods": aura_stub},
            )
        finally:
            wargear_mod.get_roll = old_get_roll
        self.assertTrue(any("Rain Of Cruelty" in str(mod or "") for mod in list(wound_result.get("modifiers", []) or [])))

    def test_rain_of_cruelty_only_applies_to_drukhari_units(self):
        game, drukhari_army, _enemy_army = self._build_game()
        harlequin = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
        )
        drukhari_army.add_unit(harlequin)

        applied = drukhari_army.drukhari_detachments.apply_rain_of_cruelty_on_disembark(
            harlequin,
            game=game,
            current_turn=game.turn,
        )
        self.assertFalse(applied)
        self.assertFalse(bool(harlequin.special_rules.get("rain_of_cruelty_active")))


if __name__ == "__main__":
    unittest.main()
