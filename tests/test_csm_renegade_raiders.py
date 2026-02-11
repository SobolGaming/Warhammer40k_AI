import unittest
from types import SimpleNamespace


class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id="CSM", detachment_type="Renegade Raiders"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.chaos_space_marines_detachments = None


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
        self.within_objective = bool(within_objective)
        self.deployed = True
        self.reserve_status = "deployed"
        self.is_embarked = False

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


def _model(name: str, parent_unit, *, keywords=None, faction_keywords=None):
    pool = [str(k or "").strip().lower() for k in (list(keywords or []) + list(faction_keywords or [])) if str(k or "").strip()]

    def _has_keyword(value: str) -> bool:
        return str(value or "").strip().lower() in pool

    return SimpleNamespace(
        name=name,
        parent_unit=parent_unit,
        has_any_keyword=_has_keyword,
        has_keyword=_has_keyword,
    )


class TestChaosSpaceMarinesRenegadeRaiders(unittest.TestCase):
    def _make_profile(self, *, melee=False, ap="0"):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: bool(melee),
            is_ranged=lambda: not bool(melee),
        )
        data = {
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": str(ap),
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def _configure_game_map(self, attacker_army, target_army):
        game_map = SimpleNamespace(objectives=[])
        game = SimpleNamespace(map=game_map, turn=1)
        attacker_army.player.game = game
        target_army.player.game = game

    def test_raiders_and_reavers_grants_assault_to_heretic_astartes_ranged_weapons(self):
        from warhammer40k_ai.rules.chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="CSM", detachment_type="Renegade Raiders")
        army.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(army)

        unit = _DummyUnit("Legionaries", army, keywords=["HERETIC ASTARTES"])
        profile = self._make_profile(melee=False, ap="0")

        self.assertTrue(Unit.can_shoot_after_advance(unit, profile))

    def test_raiders_and_reavers_assault_does_not_apply_to_non_heretic_astartes(self):
        from warhammer40k_ai.rules.chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="CSM", detachment_type="Renegade Raiders")
        army.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(army)

        unit = _DummyUnit("Traitor Militia", army, keywords=["INFANTRY"])
        profile = self._make_profile(melee=False, ap="0")

        self.assertFalse(Unit.can_shoot_after_advance(unit, profile))

    def test_raiders_and_reavers_improves_ap_against_target_within_objective_range(self):
        from warhammer40k_ai.rules.chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager

        army = _DummyArmy(faction_id="CSM", detachment_type="Renegade Raiders")
        army.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(army)
        enemy_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_map(army, enemy_army)

        attacker_unit = _DummyUnit("Legionaries", army, keywords=["HERETIC ASTARTES"])
        target_unit = _DummyUnit("Target", enemy_army, within_objective=True)
        attacker_model = _model("Legionary", attacker_unit, keywords=["HERETIC ASTARTES"])

        profile = self._make_profile(melee=False, ap="0")
        self.assertEqual(profile.get_effective_ap(attacker_model, target_unit), -1)

    def test_raiders_and_reavers_ap_bonus_not_applied_without_objective_or_detachment(self):
        from warhammer40k_ai.rules.chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager

        army = _DummyArmy(faction_id="CSM", detachment_type="Renegade Raiders")
        army.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(army)
        enemy_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        self._configure_game_map(army, enemy_army)

        attacker_unit = _DummyUnit("Legionaries", army, keywords=["HERETIC ASTARTES"])
        attacker_model = _model("Legionary", attacker_unit, keywords=["HERETIC ASTARTES"])
        target_outside_objective = _DummyUnit("Target", enemy_army, within_objective=False)
        profile = self._make_profile(melee=True, ap="0")

        self.assertEqual(profile.get_effective_ap(attacker_model, target_outside_objective), 0)

        other_army = _DummyArmy(faction_id="CSM", detachment_type="Cabal of Chaos")
        other_army.chaos_space_marines_detachments = ChaosSpaceMarinesDetachmentManager(other_army)
        self._configure_game_map(other_army, enemy_army)
        other_attacker = _DummyUnit("Legionaries", other_army, keywords=["HERETIC ASTARTES"])
        other_model = _model("Legionary", other_attacker, keywords=["HERETIC ASTARTES"])
        target_on_objective = _DummyUnit("Target", enemy_army, within_objective=True)

        self.assertEqual(profile.get_effective_ap(other_model, target_on_objective), 0)


if __name__ == "__main__":
    unittest.main()
