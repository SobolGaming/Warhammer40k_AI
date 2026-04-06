import unittest
from types import SimpleNamespace

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id="NEC", detachment_type="Starshatter Arsenal"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.necrons_detachments = None
        attach_detachment_helpers(self)


class _DummyUnit:
    def __init__(self, name, army, *, keywords=None, faction_keywords=None, within_objective=False):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army
        self.within_objective = within_objective

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

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_collision(self):
        return list(self.models)

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_battle_shocked(self):
        return False

    def is_in_reserves(self):
        return False

    def is_alive(self):
        return True

    def has_stealth(self):
        return False

    def has_first_prince_tzeentch_defense(self):
        return False

    def has_advance_and_shoot(self):
        return False

    def _target_within_objective_range(self, target_unit, _game_map=None) -> bool:
        return bool(getattr(target_unit, "within_objective", False))


class TestRelentlessOnslaught(unittest.TestCase):
    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Gauss",
            is_melee=lambda: False,
            is_ranged=lambda: True,
        )
        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def test_relentless_onslaught_hit_bonus_vs_objectives(self):
        from warhammer40k_ai.rules.necrons_detachments import NecronsDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="NEC", detachment_type="Starshatter Arsenal")
        army.necrons_detachments = NecronsDetachmentManager(army)

        attacker_unit = _DummyUnit("Necron", army, keywords=["NECRONS"])
        monster_attacker_unit = _DummyUnit("Monster", army, keywords=["NECRONS", "MONSTER"])
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, within_objective=True)

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
        monster_attacker_model = SimpleNamespace(name="Monster Attacker", parent_unit=monster_attacker_unit)
        profile = self._make_profile()

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
            hit = profile._hit_target_with_tracking(target_unit, attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertTrue(any("Relentless Onslaught" in x for x in hit.get("modifiers", [])))

            target_unit.within_objective = False
            hit = profile._hit_target_with_tracking(target_unit, attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertFalse(any("Relentless Onslaught" in x for x in hit.get("modifiers", [])))

            target_unit.within_objective = True
            hit = profile._hit_target_with_tracking(target_unit, monster_attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertFalse(any("Relentless Onslaught" in x for x in hit.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_relentless_onslaught_assault_for_vehicle_or_mounted(self):
        from warhammer40k_ai.rules.necrons_detachments import NecronsDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="NEC", detachment_type="Starshatter Arsenal")
        army.necrons_detachments = NecronsDetachmentManager(army)

        profile = self._make_profile()

        vehicle = _DummyUnit("Vehicle", army, keywords=["NECRONS", "VEHICLE"])
        mounted = _DummyUnit("Mounted", army, keywords=["NECRONS", "MOUNTED"])
        titanic = _DummyUnit("Titanic", army, keywords=["NECRONS", "VEHICLE", "TITANIC"])
        infantry = _DummyUnit("Infantry", army, keywords=["NECRONS", "INFANTRY"])

        self.assertTrue(Unit.can_shoot_after_advance(vehicle, profile))
        self.assertTrue(Unit.can_shoot_after_advance(mounted, profile))
        self.assertFalse(Unit.can_shoot_after_advance(titanic, profile))
        self.assertFalse(Unit.can_shoot_after_advance(infantry, profile))


if __name__ == "__main__":
    unittest.main()
