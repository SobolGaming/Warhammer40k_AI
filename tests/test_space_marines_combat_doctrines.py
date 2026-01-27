import unittest
from types import SimpleNamespace


class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id="SM", detachment_type="Gladius Task Force"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.space_marines_detachments = None
        self.combat_doctrines = None


class _DummyUnit:
    def __init__(
        self,
        name,
        army,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 0,
        reserve_status: str = "battlefield",
    ):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army
        self.reserve_status = reserve_status
        for i in range(max(int(model_count), 0)):
            self.models.append(SimpleNamespace(name=f"{name} #{i + 1}", parent_unit=self))

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool

    def has_fell_back_and_shoot(self):
        return False

    def has_advance_and_shoot(self):
        return False

    def has_advance_and_charge(self):
        return False

    def has_thrill_seekers(self):
        return False

    def _has_simple_eligibility_rule(self, _patterns):
        return False


class TestSpaceMarinesCombatDoctrines(unittest.TestCase):
    def _make_profile(self, *, weapon_type="Ranged", skill="3+"):
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

    def test_combat_doctrines_once_per_battle(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, DEVASTATOR_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager

        army = _DummyArmy()
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr

        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        self.assertFalse(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        available = [d.key for d in mgr.get_available_doctrines()]
        self.assertNotIn(DEVASTATOR_DOCTRINE.key, available)

    def test_devastator_allows_shoot_after_advance(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, DEVASTATOR_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy()
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr
        army.player.game = SimpleNamespace(turn=1)

        unit = _DummyUnit("Intercessors", army, keywords=["ADEPTUS ASTARTES"])
        profile = self._make_profile(weapon_type="Ranged")

        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        self.assertTrue(Unit.can_shoot_after_advance(unit, profile))
        army.player.game.turn = 2
        self.assertFalse(Unit.can_shoot_after_advance(unit, profile))

    def test_tactical_allows_fall_back_shoot_and_charge(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, TACTICAL_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy()
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr
        army.player.game = SimpleNamespace(turn=2)

        unit = _DummyUnit("Intercessors", army, keywords=["ADEPTUS ASTARTES"])
        profile = self._make_profile(weapon_type="Ranged")

        self.assertTrue(mgr.select_doctrine(TACTICAL_DOCTRINE, battle_round=2))
        self.assertTrue(Unit.can_shoot_after_fall_back(unit, profile))
        self.assertTrue(Unit.can_charge_after_fall_back(unit))

    def test_assault_allows_charge_after_advance(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, ASSAULT_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy()
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr
        army.player.game = SimpleNamespace(turn=3)

        unit = _DummyUnit("Intercessors", army, keywords=["ADEPTUS ASTARTES"])

        self.assertTrue(mgr.select_doctrine(ASSAULT_DOCTRINE, battle_round=3))
        self.assertTrue(Unit.can_charge_after_advance(unit))

    def test_mastered_doctrines_disallow_reuse_without_calgar(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, DEVASTATOR_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager

        army = _DummyArmy(detachment_type="Blade of Ultramar")
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr
        army.player.game = SimpleNamespace(turn=1)

        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        army.player.game.turn = 2
        self.assertFalse(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=2))
        available = [d.key for d in mgr.get_available_doctrines()]
        self.assertNotIn(DEVASTATOR_DOCTRINE.key, available)

    def test_mastered_doctrines_allow_reuse_with_calgar_and_limit_three_selections(self):
        from warhammer40k_ai.rules.combat_doctrines import (
            CombatDoctrinesManager,
            ASSAULT_DOCTRINE,
            DEVASTATOR_DOCTRINE,
            TACTICAL_DOCTRINE,
        )
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager

        army = _DummyArmy(detachment_type="Blade of Ultramar")
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        calgar = _DummyUnit("Marneus Calgar", army, keywords=["ADEPTUS ASTARTES"], model_count=1)
        army.units = [calgar]

        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr

        army.player.game = SimpleNamespace(turn=1)
        self.assertTrue(mgr.can_select_now(game=army.player.game))
        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))

        army.player.game.turn = 2
        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=2))

        army.player.game.turn = 3
        self.assertTrue(mgr.select_doctrine(TACTICAL_DOCTRINE, battle_round=3))

        army.player.game.turn = 4
        self.assertFalse(mgr.can_select_now(game=army.player.game))
        self.assertFalse(mgr.select_doctrine(ASSAULT_DOCTRINE, battle_round=4))

    def test_mastered_doctrines_effects_apply_in_blade_of_ultramar(self):
        from warhammer40k_ai.rules.combat_doctrines import CombatDoctrinesManager, DEVASTATOR_DOCTRINE
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(detachment_type="Blade of Ultramar")
        army.space_marines_detachments = SpaceMarinesDetachmentManager(army)
        mgr = CombatDoctrinesManager(army)
        army.combat_doctrines = mgr
        army.player.game = SimpleNamespace(turn=1)

        unit = _DummyUnit("Intercessors", army, keywords=["ADEPTUS ASTARTES"])
        profile = self._make_profile(weapon_type="Ranged")

        self.assertTrue(mgr.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        self.assertTrue(Unit.can_shoot_after_advance(unit, profile))


if __name__ == "__main__":
    unittest.main()
