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
    def __init__(self, *, faction_id="AS", detachment_type="Bringers of Flame"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.adepta_sororitas_detachments = None
        attach_detachment_helpers(self)


class _DummyUnit:
    def __init__(self, name, army, *, keywords=None, faction_keywords=None, toughness=4):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army
        self.parent_army = army
        self.toughness = int(toughness)

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army
        self.parent_army = army

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


class TestBringersOfFlameFerventPurgation(unittest.TestCase):
    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Bolter",
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

    def test_fervent_purgation_counts_ranged_weapons_as_assault(self):
        from warhammer40k_ai.rules.adepta_sororitas_detachments import AdeptaSororitasDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        profile = self._make_profile()

        bringers_army = _DummyArmy(faction_id="AS", detachment_type="Bringers of Flame")
        bringers_army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(bringers_army)
        bringers_unit = _DummyUnit(
            "Battle Sisters",
            bringers_army,
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        self.assertTrue(Unit.can_shoot_after_advance(bringers_unit, profile))

        other_army = _DummyArmy(faction_id="AS", detachment_type="Hallowed Martyrs")
        other_army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(other_army)
        other_unit = _DummyUnit(
            "Battle Sisters",
            other_army,
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        self.assertFalse(Unit.can_shoot_after_advance(other_unit, profile))

    def test_fervent_purgation_strength_bonus_within_6_inches_only(self):
        from warhammer40k_ai.rules.adepta_sororitas_detachments import AdeptaSororitasDetachmentManager

        army = _DummyArmy(faction_id="AS", detachment_type="Bringers of Flame")
        army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Battle Sisters",
            army,
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=5)

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit, is_alive=True, wounds=1)
        attacker_unit.models = [attacker_model]
        target_unit.models = [SimpleNamespace(name="Target Model", parent_unit=target_unit, is_alive=True, wounds=1)]
        profile = self._make_profile()

        within = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            {"distance_to_target": 6.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(within.get("wound", False))
        self.assertTrue(any("Fervent Purgation" in m for m in list(within.get("modifiers", []) or [])))

        outside = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            {"distance_to_target": 6.1},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(outside.get("wound", True))
        self.assertFalse(any("Fervent Purgation" in m for m in list(outside.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
