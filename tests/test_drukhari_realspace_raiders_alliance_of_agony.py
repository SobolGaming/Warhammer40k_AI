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


class TestDrukhariRealspaceRaidersAllianceOfAgony(unittest.TestCase):
    def _setup_realspace_army(self):
        army = Army("Drukhari", detachment_type="Realspace Raiders")
        army.faction_id = "DRU"
        player = Player("DRU", control=PlayerControl.REMOTE, army=army)
        army.player = player
        return army, player

    def test_alliance_of_agony_grants_six_tokens_when_all_combinations_present(self):
        army, player = self._setup_realspace_army()
        army.add_unit(
            _make_unit(
                "Archon",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "ARCHON", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Kabalite Warriors",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "KABAL", "KABALITE WARRIORS", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Succubus",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "SUCCUBUS", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Wyches",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "WYCH CULT", "WYCHES", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Haemonculus",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "HAEMONCULUS", "HAEMONCULUS COVENS", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Wracks",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "HAEMONCULUS COVENS", "WRACKS", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )

        mgr = army.drukhari_detachments
        self.assertEqual(int(army.power_from_pain.tokens), 0)
        mgr.on_battle_round_start(battle_round=1, player=player)
        self.assertEqual(int(army.power_from_pain.tokens), 6)
        self.assertTrue(bool(mgr.alliance_of_agony_applied))
        self.assertEqual(int(mgr.alliance_of_agony_tokens_awarded), 6)

    def test_alliance_of_agony_grants_two_tokens_for_one_combination(self):
        army, player = self._setup_realspace_army()
        army.add_unit(
            _make_unit(
                "Archon",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "ARCHON", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Kabalite Warriors",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "KABAL", "KABALITE WARRIORS", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Succubus",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "SUCCUBUS", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )

        mgr = army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, player=player)
        self.assertEqual(int(army.power_from_pain.tokens), 2)
        self.assertEqual(int(mgr.alliance_of_agony_tokens_awarded), 2)

    def test_alliance_of_agony_applies_only_once(self):
        army, player = self._setup_realspace_army()
        army.add_unit(
            _make_unit(
                "Archon",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "ARCHON", "CHARACTER", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )
        army.add_unit(
            _make_unit(
                "Kabalite Warriors",
                faction_name="Drukhari",
                keywords=["DRUKHARI", "KABAL", "KABALITE WARRIORS", "INFANTRY"],
                faction_keywords=["DRUKHARI"],
            )
        )

        mgr = army.drukhari_detachments
        mgr.on_battle_round_start(battle_round=1, player=player)
        self.assertEqual(int(army.power_from_pain.tokens), 2)
        mgr.on_battle_round_start(battle_round=1, player=player)
        mgr.on_battle_round_start(battle_round=2, player=player)
        self.assertEqual(int(army.power_from_pain.tokens), 2)
        self.assertEqual(int(mgr.alliance_of_agony_tokens_awarded), 2)


if __name__ == "__main__":
    unittest.main()
