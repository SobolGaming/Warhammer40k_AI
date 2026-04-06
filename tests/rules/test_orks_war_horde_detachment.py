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
    def __init__(self, *, faction_id="ORK", detachment_type="War Horde"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.orks_detachments = None
        attach_detachment_helpers(self)


class _DummyUnit:
    def __init__(self, name, army, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army

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


class TestOrksWarHordeDetachment(unittest.TestCase):
    def _aura_stub(self):
        return SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

    def _make_profile(self, *, weapon_type="Melee", skill="3+"):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Choppa" if weapon_type.lower() == "melee" else "Slugga",
            is_melee=lambda: weapon_type.lower() == "melee",
            is_ranged=lambda: weapon_type.lower() == "ranged",
        )
        data = {
            "range": "Melee" if weapon_type.lower() == "melee" else "18",
            "A": "1",
            "BS_WS": skill,
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def test_war_horde_grants_melee_sustained_hits(self):
        from warhammer40k_ai.rules.orks_detachments import OrksDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="ORK", detachment_type="War Horde")
        army.orks_detachments = OrksDetachmentManager(army)

        attacker_unit = _DummyUnit("Boy", army, keywords=["ORKS"])
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, keywords=["INFANTRY"])

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
        profile = self._make_profile(weapon_type="Melee", skill="3+")

        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 6
        try:
            profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
        finally:
            wargear_mod.get_roll = old_get_roll

        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

    def test_war_horde_does_not_apply_to_ranged_or_non_orks(self):
        from warhammer40k_ai.rules.orks_detachments import OrksDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="ORK", detachment_type="War Horde")
        army.orks_detachments = OrksDetachmentManager(army)

        attacker_unit = _DummyUnit("Boy", army, keywords=["ORKS"])
        non_orks_unit = _DummyUnit("Ally", army, keywords=["HUMAN"])
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, keywords=["INFANTRY"])

        ranged_profile = self._make_profile(weapon_type="Ranged", skill="3+")
        melee_profile = self._make_profile(weapon_type="Melee", skill="3+")

        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 6
        try:
            attack_instance = {"_aura_attack_mods": self._aura_stub()}
            ranged_profile._hit_target_with_tracking(
                target_unit,
                SimpleNamespace(name="Shooter", parent_unit=attacker_unit),
                attack_instance,
            )
            self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 0)

            attack_instance = {"_aura_attack_mods": self._aura_stub()}
            melee_profile._hit_target_with_tracking(
                target_unit,
                SimpleNamespace(name="Ally", parent_unit=non_orks_unit),
                attack_instance,
            )
            self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 0)
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
