import unittest
from types import SimpleNamespace

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Drukhari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 50}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "7",
                "T": "3",
                "Sv": "6",
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
        self.transport = ""


def _make_unit(name: str, *, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, keywords=keywords or [])
    return Unit(datasheet)


def _make_army(*, units):
    from warhammer40k_ai.rules.drukhari_detachments import DrukhariDetachmentManager
    from warhammer40k_ai.engine.event.system import EventSystem

    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=None)
    army = SimpleNamespace(
        faction_id="DRU",
        detachment_type="Spectacle of Spite",
        units=list(units),
        player=player,
    )
    attach_detachment_helpers(army)
    game = SimpleNamespace(turn=1, map=None, event_system=EventSystem())
    player.game = game
    mgr = DrukhariDetachmentManager(army)
    army.drukhari_detachments = mgr
    for unit in list(units):
        unit.set_parent_army(army)
    return army, mgr, player, game


def _make_profile(*, weapon_type="melee", skill="4+", strength="4", attacks="1"):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: weapon_type.lower() == "melee",
        is_ranged=lambda: weapon_type.lower() == "ranged",
    )
    data = {
        "range": "Melee" if weapon_type.lower() == "melee" else "24",
        "A": str(attacks),
        "BS_WS": skill,
        "S": strength,
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


class TestDrukhariCombatDrugs(unittest.TestCase):
    def test_manual_selection_tracks_used(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        army, mgr, _player, game = _make_army(units=[unit])
        game.turn = 1

        self.assertTrue(mgr.select_combat_drug("ADRENALIGHT", battle_round=1))
        self.assertEqual(mgr.combat_drug_active_round, 1)
        self.assertIn("ADRENALIGHT", mgr.combat_drug_active_keys)
        self.assertFalse(mgr.select_combat_drug("ADRENALIGHT", battle_round=1))
        available = {d.key for d in mgr.get_available_combat_drugs()}
        self.assertNotIn("ADRENALIGHT", available)

    def test_adrenalight_melee_attacks_bonus(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        target = _make_unit("Target", keywords=[])
        army, mgr, _player, _game = _make_army(units=[unit, target])
        mgr.select_combat_drug("ADRENALIGHT", battle_round=1)

        profile = _make_profile(weapon_type="melee", attacks="1")
        from warhammer40k_ai.units import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 6
        try:
            result = profile.attack(target, unit.models[0], game_map=None)
            self.assertEqual(int(result.attacks_rolled), 2)
            self.assertTrue(any("Adrenalight" in x for x in result.attacks_special_modifiers))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_serpentin_ws_improves_melee_skill(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        target = _make_unit("Target", keywords=[])
        army, mgr, _player, _game = _make_army(units=[unit, target])
        mgr.select_combat_drug("SERPENTIN", battle_round=1)

        melee = _make_profile(weapon_type="melee", skill="4+")
        hit = melee._hit_target_with_tracking(target, unit.models[0], {})
        self.assertEqual(hit.get("base_skill"), 3)
        self.assertIn("Combat Drugs: Serpentin +1 WS", hit.get("special_effects", []))

    def test_splintermind_bs_and_leadership(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        target = _make_unit("Target", keywords=[])
        army, mgr, _player, _game = _make_army(units=[unit, target])
        mgr.select_combat_drug("SPLINTERMIND", battle_round=1)

        ranged = _make_profile(weapon_type="ranged", skill="4+")
        hit = ranged._hit_target_with_tracking(target, unit.models[0], {})
        self.assertEqual(hit.get("base_skill"), 3)
        self.assertIn("Combat Drugs: Splintermind +1 BS", hit.get("special_effects", []))

        model = unit.models[0]
        self.assertEqual(unit.get_effective_model_characteristic(model, "leadership"), 6)

    def test_grave_lotus_strength_bonus(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        target = _make_unit("Target", keywords=[])
        army, mgr, _player, _game = _make_army(units=[unit, target])
        mgr.select_combat_drug("GRAVE_LOTUS", battle_round=1)

        melee = _make_profile(weapon_type="melee", strength="4")
        wound = melee._wound_target_with_tracking(target, unit.models[0], {"_aura_attack_mods": SimpleNamespace()})
        self.assertTrue(any("Grave Lotus" in x for x in wound.get("modifiers", [])))

    def test_hypex_movement_bonus(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        army, mgr, _player, _game = _make_army(units=[unit])
        mgr.select_combat_drug("HYPEX", battle_round=1)

        model = unit.models[0]
        self.assertEqual(unit.get_effective_model_characteristic(model, "movement"), 9)

    def test_painbringer_toughness_bonus(self):
        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        army, mgr, _player, _game = _make_army(units=[unit])
        mgr.select_combat_drug("PAINBRINGER", battle_round=1)

        model = unit.models[0]
        self.assertEqual(unit.get_effective_model_characteristic(model, "toughness"), 4)

    def test_roll_combat_drugs_duplicates_have_no_extra_effect(self):
        from warhammer40k_ai.rules import drukhari_detachments as dd

        unit = _make_unit("Wyches", keywords=["Wych Cult"])
        army, mgr, _player, _game = _make_army(units=[unit])

        old_get_roll = dd.get_roll
        dd.get_roll = lambda _s: 1
        try:
            result = mgr.roll_combat_drugs(battle_round=1)
            self.assertEqual(result.get("rolls"), [1, 1])
            self.assertEqual(len(mgr.combat_drug_active_keys), 1)
        finally:
            dd.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
