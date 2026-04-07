from __future__ import annotations

import unittest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, faction_name, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "7",
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
        self.transport = ""


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


class TestDrukhariReapersWagerCallousCompetition(unittest.TestCase):
    def _setup_armies(self):
        drukhari_army = Army.with_detachment("Drukhari", detachment_type="Reaper's Wager")
        drukhari_army.faction_id = "DRU"
        drukhari_player = Player("DRU", control=PlayerControl.REMOTE, army=drukhari_army)
        drukhari_army.player = drukhari_player

        enemy_army = Army.with_detachment("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        return drukhari_army, drukhari_player, enemy_army, enemy_player

    def test_callous_competition_initial_state_applies_correct_reroll_profiles(self):
        drukhari_army, drukhari_player, enemy_army, _enemy_player = self._setup_armies()
        drukhari_unit = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "KABAL", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        harlequins_unit = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["HARLEQUINS", "INFANTRY"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy_unit = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(drukhari_unit)
        drukhari_army.add_unit(harlequins_unit)
        enemy_army.add_unit(enemy_unit)

        mgr = drukhari_army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, player=drukhari_player)
        self.assertTrue(bool(mgr.callous_competition_initialized))
        self.assertEqual(str(mgr.callous_competition_winning_side), "DRUKHARI")

        drukhari_hit = drukhari_unit.get_model_hit_reroll_modifiers(
            drukhari_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        drukhari_wound = drukhari_unit.get_model_wound_reroll_modifiers(
            drukhari_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        self.assertIn(1, set(drukhari_hit.get("reroll_hit_values", ()) or ()))
        self.assertNotIn(1, set(drukhari_wound.get("reroll_wound_values", ()) or ()))

        harlequins_hit = harlequins_unit.get_model_hit_reroll_modifiers(
            harlequins_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        harlequins_wound = harlequins_unit.get_model_wound_reroll_modifiers(
            harlequins_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        self.assertIn(1, set(harlequins_hit.get("reroll_hit_values", ()) or ()))
        self.assertIn(1, set(harlequins_wound.get("reroll_wound_values", ()) or ()))

    def test_callous_competition_switches_winner_on_harlequins_kill(self):
        drukhari_army, drukhari_player, enemy_army, _enemy_player = self._setup_armies()
        drukhari_unit = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "KABAL", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        harlequins_unit = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["HARLEQUINS", "INFANTRY"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy_unit = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(drukhari_unit)
        drukhari_army.add_unit(harlequins_unit)
        enemy_army.add_unit(enemy_unit)

        mgr = drukhari_army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, player=drukhari_player)
        self.assertEqual(str(mgr.callous_competition_winning_side), "DRUKHARI")

        mgr.on_enemy_unit_destroyed(enemy_unit, destroyed_by_unit=harlequins_unit)
        self.assertEqual(str(mgr.callous_competition_winning_side), "HARLEQUINS")

        drukhari_wound = drukhari_unit.get_model_wound_reroll_modifiers(
            drukhari_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        harlequins_wound = harlequins_unit.get_model_wound_reroll_modifiers(
            harlequins_unit.models[0],
            attack_type="ranged",
            target=enemy_unit,
        )
        self.assertIn(1, set(drukhari_wound.get("reroll_wound_values", ()) or ()))
        self.assertNotIn(1, set(harlequins_wound.get("reroll_wound_values", ()) or ()))

    def test_callous_competition_ignores_enemy_destroyer(self):
        drukhari_army, drukhari_player, enemy_army, _enemy_player = self._setup_armies()
        drukhari_unit = _make_unit(
            "Kabalite Warriors",
            faction_name="Drukhari",
            keywords=["DRUKHARI", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_unit = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(drukhari_unit)
        enemy_army.add_unit(enemy_unit)

        mgr = drukhari_army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, player=drukhari_player)
        self.assertEqual(str(mgr.callous_competition_winning_side), "DRUKHARI")

        mgr.on_enemy_unit_destroyed(drukhari_unit, destroyed_by_unit=enemy_unit)
        self.assertEqual(str(mgr.callous_competition_winning_side), "DRUKHARI")


if __name__ == "__main__":
    unittest.main()
