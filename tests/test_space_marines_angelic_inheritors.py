import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
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
        self.transport = ""


def _make_unit(name: str, *, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords or ["ADEPTUS ASTARTES"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    return Unit(datasheet)


def _make_profile(*, weapon_type="ranged", skill="3+"):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(
        name="Boltgun" if weapon_type.lower() == "ranged" else "Chainsword",
        is_melee=lambda: weapon_type.lower() == "melee",
        is_ranged=lambda: weapon_type.lower() == "ranged",
    )
    data = {
        "range": "Melee" if weapon_type.lower() == "melee" else "24",
        "A": "1",
        "BS_WS": skill,
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _make_army(*, detachment_type: str, units):
    from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager

    player = SimpleNamespace(
        name="P1",
        id="P1",
        control=SimpleNamespace(name="LOCAL"),
        has_control=lambda: True,
        game=None,
    )
    game = SimpleNamespace(turn=1, map=None)
    player.game = game
    army = SimpleNamespace(
        faction_id="SM",
        detachment_type=detachment_type,
        units=list(units),
        player=player,
        combat_doctrines=None,
    )
    mgr = SpaceMarinesDetachmentManager(army)
    army.space_marines_detachments = mgr
    for unit in list(units):
        unit.set_parent_army(army)
    return army, mgr, game


class TestSpaceMarinesAngelicInheritors(unittest.TestCase):
    def test_selection_requires_exactly_two_unique_options(self):
        unit = _make_unit("Captain", keywords=["ADEPTUS ASTARTES", "CHARACTER"])
        _army, mgr, _game = _make_army(detachment_type="Angelic Inheritors", units=[unit])

        self.assertTrue(mgr.can_select_angelic_legacy())
        self.assertFalse(mgr.select_angelic_legacy_options(["SANGUINARY_GRACE"]))
        self.assertFalse(mgr.select_angelic_legacy_options(["SANGUINARY_GRACE", "SANGUINARY_GRACE"]))
        self.assertTrue(mgr.select_angelic_legacy_options(["SANGUINARY_GRACE", "CARMINE_WRATH"], battle_round=1))
        self.assertFalse(mgr.can_select_angelic_legacy())

    def test_sanguinary_grace_allows_fall_back_shoot_and_charge_for_character_units(self):
        from warhammer40k_ai.units.unit import Unit

        character_unit = _make_unit("Captain", keywords=["ADEPTUS ASTARTES", "CHARACTER"])
        non_character_unit = _make_unit("Intercessors", keywords=["ADEPTUS ASTARTES", "INFANTRY"])
        _army, mgr, _game = _make_army(
            detachment_type="Angelic Inheritors",
            units=[character_unit, non_character_unit],
        )
        mgr.select_angelic_legacy_options(["SANGUINARY_GRACE", "CARMINE_WRATH"], battle_round=1)

        profile = _make_profile(weapon_type="ranged")
        self.assertTrue(Unit.can_shoot_after_fall_back(character_unit, profile))
        self.assertTrue(Unit.can_charge_after_fall_back(character_unit))
        self.assertFalse(Unit.can_shoot_after_fall_back(non_character_unit, profile))
        self.assertFalse(Unit.can_charge_after_fall_back(non_character_unit))

    def test_their_appointed_hour_enables_advance_and_charge_rerolls_for_character_units(self):
        from warhammer40k_ai.units.unit import Unit

        character_unit = _make_unit("Chaplain", keywords=["ADEPTUS ASTARTES", "CHARACTER"])
        _army, mgr, game = _make_army(detachment_type="Angelic Inheritors", units=[character_unit])
        mgr.select_angelic_legacy_options(["THEIR_APPOINTED_HOUR", "SANGUINARY_GRACE"], battle_round=1)

        self.assertTrue(Unit.can_reroll_advance_roll(character_unit))
        self.assertTrue(Unit.can_reroll_charge_roll(character_unit, target_unit=[], game=game))

    def test_carmine_wrath_adds_hit_and_wound_reroll_ones(self):
        character_unit = _make_unit("Librarian", keywords=["ADEPTUS ASTARTES", "CHARACTER", "PSYKER"])
        _army, mgr, _game = _make_army(detachment_type="Angelic Inheritors", units=[character_unit])
        mgr.select_angelic_legacy_options(["CARMINE_WRATH", "SANGUINARY_GRACE"], battle_round=1)

        hit_mods = character_unit.get_unit_hit_reroll_modifiers("melee")
        wound_mods = character_unit.get_unit_wound_reroll_modifiers("melee")
        self.assertIn(1, set(hit_mods.get("reroll_hit_values", ()) or ()))
        self.assertIn(1, set(wound_mods.get("reroll_wound_values", ()) or ()))
        self.assertTrue(any("Carmine Wrath" in r for r in list(hit_mods.get("reroll_hit_reasons", ()) or ())))
        self.assertTrue(any("Carmine Wrath" in r for r in list(wound_mods.get("reroll_wound_reasons", ()) or ())))


if __name__ == "__main__":
    unittest.main()
