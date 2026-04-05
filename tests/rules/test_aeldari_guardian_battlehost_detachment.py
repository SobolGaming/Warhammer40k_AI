import unittest
from types import SimpleNamespace


class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id="AE", detachment_type="Guardian Battlehost"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.aeldari_detachments = None


class _DummyObjective:
    def __init__(self):
        self.location = SimpleNamespace(removed=False)


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

    def is_within_objective_range(self, _objective_point) -> bool:
        return bool(self.within_objective)


def _model(name: str, parent_unit, *, keywords=None):
    keyword_set = {str(k).strip().lower() for k in list(keywords or []) if str(k).strip()}

    def _has_any(kw: str) -> bool:
        return str(kw or "").strip().lower() in keyword_set

    return SimpleNamespace(
        name=name,
        parent_unit=parent_unit,
        has_any_keyword=_has_any,
        has_keyword=_has_any,
    )


class TestAeldariGuardianBattlehostDetachment(unittest.TestCase):
    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Shuriken Catapult",
            is_melee=lambda: False,
            is_ranged=lambda: True,
        )
        data = {
            "range": "18",
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

    def _configure_game_maps(self, attacker_army, target_army):
        game_map = SimpleNamespace(objectives=[_DummyObjective()])
        game = SimpleNamespace(map=game_map, turn=1)
        attacker_army.player.game = game
        target_army.player.game = game

    def test_defend_at_all_costs_hit_bonus_when_attacker_unit_within_objective(self):
        from warhammer40k_ai.rules.aeldari_detachments import AeldariDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="AE", detachment_type="Guardian Battlehost")
        army.aeldari_detachments = AeldariDetachmentManager(army)
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_maps(army, target_army)

        attacker_unit = _DummyUnit("Dire Avengers", army, keywords=["AELDARI"], within_objective=True)
        target_unit = _DummyUnit("Target", target_army, keywords=["ENEMY"], within_objective=False)
        attacker = _model("Dire Avenger", attacker_unit, keywords=["DIRE AVENGERS", "AELDARI"])

        profile = self._make_profile()
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            hit = profile._hit_target_with_tracking(target_unit, attacker, {"_aura_attack_mods": self._aura_stub()})
            self.assertEqual(int(hit["final_needed"]), 3)
            self.assertTrue(any("Defend at All Costs" in x for x in hit.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_defend_at_all_costs_hit_bonus_when_target_unit_within_objective(self):
        from warhammer40k_ai.rules.aeldari_detachments import AeldariDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="AE", detachment_type="Guardian Battlehost")
        army.aeldari_detachments = AeldariDetachmentManager(army)
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_maps(army, target_army)

        attacker_unit = _DummyUnit("Dire Avengers", army, keywords=["AELDARI"], within_objective=False)
        target_unit = _DummyUnit("Target", target_army, keywords=["ENEMY"], within_objective=True)
        attacker = _model("Dire Avenger", attacker_unit, keywords=["DIRE AVENGERS", "AELDARI"])

        profile = self._make_profile()
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            hit = profile._hit_target_with_tracking(target_unit, attacker, {"_aura_attack_mods": self._aura_stub()})
            self.assertEqual(int(hit["final_needed"]), 3)
            self.assertTrue(any("Defend at All Costs" in x for x in hit.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_defend_at_all_costs_does_not_apply_to_non_eligible_model(self):
        from warhammer40k_ai.rules.aeldari_detachments import AeldariDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="AE", detachment_type="Guardian Battlehost")
        army.aeldari_detachments = AeldariDetachmentManager(army)
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_maps(army, target_army)

        attacker_unit = _DummyUnit("Guardians", army, keywords=["AELDARI"], within_objective=True)
        target_unit = _DummyUnit("Target", target_army, keywords=["ENEMY"], within_objective=True)
        attacker = _model("Autarch", attacker_unit, keywords=["AELDARI", "CHARACTER"])

        profile = self._make_profile()
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            hit = profile._hit_target_with_tracking(target_unit, attacker, {"_aura_attack_mods": self._aura_stub()})
            self.assertEqual(int(hit["final_needed"]), 4)
            self.assertFalse(any("Defend at All Costs" in x for x in hit.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_defend_at_all_costs_does_not_apply_in_other_detachments(self):
        from warhammer40k_ai.rules.aeldari_detachments import AeldariDetachmentManager
        from warhammer40k_ai.units import wargear as wargear_mod

        army = _DummyArmy(faction_id="AE", detachment_type="Warhost")
        army.aeldari_detachments = AeldariDetachmentManager(army)
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_maps(army, target_army)

        attacker_unit = _DummyUnit("Dire Avengers", army, keywords=["AELDARI"], within_objective=True)
        target_unit = _DummyUnit("Target", target_army, keywords=["ENEMY"], within_objective=True)
        attacker = _model("Dire Avenger", attacker_unit, keywords=["DIRE AVENGERS", "AELDARI"])

        profile = self._make_profile()
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            hit = profile._hit_target_with_tracking(target_unit, attacker, {"_aura_attack_mods": self._aura_stub()})
            self.assertEqual(int(hit["final_needed"]), 4)
            self.assertFalse(any("Defend at All Costs" in x for x in hit.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
