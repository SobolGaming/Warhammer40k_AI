import unittest
from types import SimpleNamespace


class _DummyPlayer:
    def __init__(self, name="Player", *, is_human=True):
        self.name = name
        self.type = SimpleNamespace(name="HUMAN" if is_human else "AI")
        self.game = None


class _DummyArmy:
    def __init__(self, units, *, faction_id="AdM"):
        self.units = list(units or [])
        self.faction_id = faction_id
        self.player = _DummyPlayer()
        self.player.game = None


class _DummyUnit:
    def __init__(self, name="Unit", *, keywords=None, abilities=None, army=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = ["ADEPTUS MECHANICUS"] if army and army.faction_id == "AdM" else []
        self.possible_abilities = list(abilities or [])
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army
        try:
            self.faction_keywords = ["ADEPTUS MECHANICUS"] if army and army.faction_id == "AdM" else []
        except Exception:
            self.faction_keywords = []

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        return kw in [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def _find_ability_with_patterns(self, patterns):
        haystack = " ".join([str(a or "") for a in (self.possible_abilities or [])]).lower()
        for pat in patterns or []:
            if str(pat or "").lower() in haystack:
                return True, None
        return False, None

    def is_alive(self):
        return True

    @property
    def is_battleline(self) -> bool:
        return "Battleline" in self.keywords

    def has_stealth(self):
        return False

    def has_first_prince_tzeentch_defense(self):
        return False

    def has_advance_and_shoot(self):
        return False


class _MapStub:
    def __init__(self, friendlies=None, *, distance=3.0):
        self._friendlies = list(friendlies or [])
        self._distance = float(distance)

    def get_friendly_units(self, _unit):
        return list(self._friendlies)

    def get_distance_between_units(self, _unit1, _unit2):
        return float(self._distance)


class TestDoctrinaImperatives(unittest.TestCase):
    def _make_profile(self, *, weapon_type="Ranged", skill="4+"):
        from warhammer40k_ai.classes.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Test Weapon",
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

    def test_protector_improves_bs_and_grants_heavy_bonus(self):
        from warhammer40k_ai.classes.doctrina_imperatives import (
            DoctrinaImperativesManager,
            PROTECTOR_IMPERATIVE,
        )

        unit = _DummyUnit("Skitarii", abilities=["Doctrina Imperatives"])
        army = _DummyArmy([unit])
        unit.set_parent_army(army)
        mgr = DoctrinaImperativesManager(army)
        army.doctrina_imperatives = mgr

        game = SimpleNamespace(turn=1, map=_MapStub())
        army.player.game = game

        mgr.select_imperative(PROTECTOR_IMPERATIVE, battle_round=1)

        unit.round_state.remained_stationary_this_round = True
        attacker = SimpleNamespace(name="Attacker", parent_unit=unit)
        target = _DummyUnit("Target", army=_DummyArmy([], faction_id="SM"))
        target.set_parent_army(target.get_parent_army())

        profile = self._make_profile(weapon_type="Ranged", skill="4+")
        hit = profile._hit_target_with_tracking(target, attacker, {})

        self.assertEqual(hit.get("base_skill"), 3)
        self.assertIn("+1 from Protector Imperative (counts as Heavy)", hit.get("modifiers", []))

    def test_protector_melee_penalty_near_battleline(self):
        from warhammer40k_ai.classes.doctrina_imperatives import (
            DoctrinaImperativesManager,
            PROTECTOR_IMPERATIVE,
        )

        target = _DummyUnit("Rangers", abilities=["Doctrina Imperatives"])
        battleline = _DummyUnit("Battleline", keywords=["Battleline"], abilities=["Doctrina Imperatives"])
        army = _DummyArmy([target, battleline])
        target.set_parent_army(army)
        battleline.set_parent_army(army)

        mgr = DoctrinaImperativesManager(army)
        army.doctrina_imperatives = mgr
        game = SimpleNamespace(turn=1, map=_MapStub([target, battleline], distance=5.0))
        army.player.game = game

        mgr.select_imperative(PROTECTOR_IMPERATIVE, battle_round=1)

        attacker_unit = _DummyUnit("Enemy", army=_DummyArmy([], faction_id="SM"))
        attacker = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
        profile = self._make_profile(weapon_type="Melee", skill="4+")

        hit = profile._hit_target_with_tracking(target, attacker, {})
        self.assertIn("-1 from Protector Imperative (battleline screen)", hit.get("modifiers", []))

    def test_conqueror_ws_and_assault(self):
        from warhammer40k_ai.classes.doctrina_imperatives import (
            DoctrinaImperativesManager,
            CONQUEROR_IMPERATIVE,
        )

        unit = _DummyUnit("Skitarii", abilities=["Doctrina Imperatives"])
        army = _DummyArmy([unit])
        unit.set_parent_army(army)
        mgr = DoctrinaImperativesManager(army)
        army.doctrina_imperatives = mgr
        game = SimpleNamespace(turn=1, map=_MapStub())
        army.player.game = game

        mgr.select_imperative(CONQUEROR_IMPERATIVE, battle_round=1)

        attacker = SimpleNamespace(name="Attacker", parent_unit=unit)
        target = _DummyUnit("Target", army=_DummyArmy([], faction_id="SM"))
        profile = self._make_profile(weapon_type="Melee", skill="4+")
        hit = profile._hit_target_with_tracking(target, attacker, {})
        self.assertEqual(hit.get("base_skill"), 3)

        ranged_profile = self._make_profile(weapon_type="Ranged", skill="4+")
        from warhammer40k_ai.classes.unit import Unit
        self.assertTrue(Unit.can_shoot_after_advance(unit, ranged_profile))

    def test_conqueror_ap_bonus_for_battleline(self):
        from warhammer40k_ai.classes.doctrina_imperatives import (
            DoctrinaImperativesManager,
            CONQUEROR_IMPERATIVE,
        )

        unit = _DummyUnit("Skitarii", keywords=["Battleline"], abilities=["Doctrina Imperatives"])
        army = _DummyArmy([unit])
        unit.set_parent_army(army)
        mgr = DoctrinaImperativesManager(army)
        army.doctrina_imperatives = mgr
        game = SimpleNamespace(turn=1, map=_MapStub())
        army.player.game = game

        mgr.select_imperative(CONQUEROR_IMPERATIVE, battle_round=1)

        attacker = SimpleNamespace(name="Attacker", parent_unit=unit)
        target = _DummyUnit("Target", army=_DummyArmy([], faction_id="SM"))
        profile = self._make_profile(weapon_type="Ranged", skill="4+")
        self.assertEqual(profile.get_effective_ap(attacker, target), -1)


if __name__ == "__main__":
    unittest.main()
