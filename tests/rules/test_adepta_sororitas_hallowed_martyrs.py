import unittest
from types import SimpleNamespace

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


class _DummyPlayer:
    def __init__(self, name: str = "Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id: str = "AS", detachment_type: str = "Hallowed Martyrs"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.adepta_sororitas_detachments = None
        attach_detachment_helpers(self)


class _DummyModel:
    def __init__(self, unit, *, keywords=None, faction_keywords=None, name: str = "Model"):
        self.name = name
        self.parent_unit = unit
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.wounds = 1
        self.is_alive = True

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool


class _DummyUnit:
    def __init__(
        self,
        name: str,
        army: _DummyArmy,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        starting_model_count: int = 1,
        current_model_count: int | None = None,
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
        self.parent_army = army
        self.toughness = int(toughness)
        self.starting_model_count = int(starting_model_count)
        self.starting_total_wounds = int(starting_model_count)

        current = int(current_model_count if current_model_count is not None else starting_model_count)
        for i in range(max(current, 0)):
            model = _DummyModel(
                self,
                name=f"{name} #{i + 1}",
                keywords=self.keywords,
                faction_keywords=self.faction_keywords,
            )
            self.models.append(model)

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

    def get_attached_unit_members(self):
        return [self]

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

    def is_below_starting_strength(self) -> bool:
        alive = [m for m in (self.models or []) if getattr(m, "is_alive", True)]
        return len(alive) < int(self.starting_model_count)

    def is_below_half_strength(self) -> bool:
        alive = [m for m in (self.models or []) if getattr(m, "is_alive", True)]
        return len(alive) < (int(self.starting_model_count) / 2.0)


class TestHallowedMartyrsBloodOfMartyrs(unittest.TestCase):
    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Boltgun",
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

    def test_blood_of_martyrs_hit_bonus_below_starting_strength(self):
        from warhammer40k_ai.rules.adepta_sororitas_detachments import AdeptaSororitasDetachmentManager

        army = _DummyArmy(faction_id="AS", detachment_type="Hallowed Martyrs")
        army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Battle Sisters",
            army,
            keywords=["ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
            starting_model_count=10,
            current_model_count=9,
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=4)

        attacker_model = attacker_unit.models[0]
        profile = self._make_profile()
        attack_ctx = {"_aura_attack_mods": self._aura_stub()}

        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(any("The Blood of Martyrs" in m for m in hit.get("modifiers", [])))

        wound = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(wound["wound"])
        self.assertFalse(any("The Blood of Martyrs" in m for m in wound.get("modifiers", [])))

    def test_blood_of_martyrs_wound_bonus_below_half_strength(self):
        from warhammer40k_ai.rules.adepta_sororitas_detachments import AdeptaSororitasDetachmentManager

        army = _DummyArmy(faction_id="AS", detachment_type="Hallowed Martyrs")
        army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Battle Sisters",
            army,
            keywords=["ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
            starting_model_count=10,
            current_model_count=4,
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=4)

        attacker_model = attacker_unit.models[0]
        profile = self._make_profile()
        attack_ctx = {"_aura_attack_mods": self._aura_stub()}

        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(any("The Blood of Martyrs" in m for m in hit.get("modifiers", [])))

        wound = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(wound["wound"])
        self.assertTrue(any("The Blood of Martyrs" in m for m in wound.get("modifiers", [])))


if __name__ == "__main__":
    unittest.main()
