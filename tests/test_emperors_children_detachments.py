import unittest
from types import SimpleNamespace


class _StubUnit:
    def __init__(self, name, army, *, toughness=5, keywords=None, faction_keywords=None, is_transport=False, is_character=False):
        self.name = name
        self._id = name
        self.toughness = toughness
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(
            remained_stationary_this_round=False,
            charged_this_round=False,
            disembarked_this_round=False,
            engaged_enemies_at_turn_start=set(),
        )
        self.parent_army = army
        self.is_transport = is_transport
        self.is_character = is_character
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_alive(self):
        return True

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        for k in (self.keywords or []) + (self.faction_keywords or []):
            if kw == str(k).strip().lower():
                return True
        return False


def _make_game(turn: int = 1, phase_name: str = "FIGHT_PHASE"):
    from warhammer40k_ai.classes.event_system import EventSystem
    return SimpleNamespace(
        turn=turn,
        phase=SimpleNamespace(name=phase_name),
        event_system=EventSystem(),
        map=None,
    )


def _make_melee_profile():
    from warhammer40k_ai.classes.wargear import WargearProfile
    parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestEmperorsChildrenDetachments(unittest.TestCase):
    def test_quicksilver_grace_allows_advance_reroll(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.unit import Unit

        army = Army("Emperor's Children", detachment_type="Mercurial Host")
        army.faction_id = "EC"
        unit = _StubUnit("EC Unit", army, faction_keywords=["EMPEROR'S CHILDREN"])

        self.assertTrue(Unit.can_reroll_advance_roll(unit))

        army.detachment_type = "Other"
        self.assertFalse(Unit.can_reroll_advance_roll(unit))

    def test_pact_points_reroll_hit_and_wound(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", game=_make_game())
        army.emperors_children.pact_points = 3

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit
        attacker_unit.models = [attacker_model]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        profile = _make_melee_profile()
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

        seq = iter([1, 4, 1, 5])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 4)
            self.assertTrue(any("Pledges to the Dark Prince" in x for x in hit_res.get("special_effects", [])))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res["roll"]), 5)
            self.assertTrue(any("Pledges to the Dark Prince" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_pact_points_critical_on_five(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", game=_make_game())
        army.emperors_children.pact_points = 7

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
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
        wargear_mod.get_roll = lambda _s: 5
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(attack_instance.get("crit_hit", False))
            self.assertTrue(any("Critical hit (5+)" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_pact_points_melee_lethal_and_sustained(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", game=_make_game())
        army.emperors_children.pact_points = 5

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
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
        wargear_mod.get_roll = lambda _s: 6
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(attack_instance.get("lethal_hit", False))
            self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_mechanised_murder_rerolls(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("Emperor's Children", detachment_type="Rapid Evisceration")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", game=_make_game())
        army.emperors_children.pact_points = 0

        attacker_unit = _StubUnit("Attacker", army, is_transport=True)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit
        attacker_unit.models = [attacker_model]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        profile = _make_melee_profile()
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

        seq = iter([1, 5, 1, 4])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Mechanised Murder" in x for x in hit_res.get("special_effects", [])))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Mechanised Murder" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_internal_rivalries_filters_negative_roll_modifiers(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.unit import Unit

        army = Army("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1")

        unit = _StubUnit("Champion", army, is_character=True)
        mods = [(-2, "Debuff"), (1, "Buff")]
        filtered = Unit._filter_internal_rivalries_roll_modifiers(unit, mods, kind="advance")
        self.assertEqual(filtered, [(1, "Buff")])

    def test_sensational_performance_restriction_only_attack_targets(self):
        from warhammer40k_ai.classes.unit import Unit

        army = SimpleNamespace()
        attacker = _StubUnit("Attacker", army)
        attacker.special_rules = {
            "sensational_performance_active": True,
            "sensational_performance_expires_phase": "FIGHT_PHASE",
        }
        attacker.round_state.engaged_enemies_at_turn_start = set()

        target = _StubUnit("Target", army)
        game = SimpleNamespace(
            phase=SimpleNamespace(name="FIGHT_PHASE"),
            phase_targeted_units={target._id: {"other"}},
            phase_charge_targets={target._id: {"other"}},
        )
        reason = Unit._sensational_performance_restriction_reason(attacker, target, game)
        self.assertTrue(reason and "Sensational Performance" in reason)

        game.phase_targeted_units = {}
        reason = Unit._sensational_performance_restriction_reason(attacker, target, game)
        self.assertIsNone(reason)

    def test_sensational_performance_bonuses(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("Emperor's Children", detachment_type="Court of the Phoenician")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", game=_make_game())

        attacker_unit = _StubUnit("Attacker", army)
        attacker_unit.special_rules = {
            "sensational_performance_active": True,
            "sensational_performance_expires_phase": "FIGHT_PHASE",
            "sensational_performance_strength_bonus": 1,
            "sensational_performance_ap_bonus": 1,
        }
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
        ap_val = profile.get_effective_ap(attacker_model, target_unit)
        self.assertEqual(int(ap_val), -1)

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
            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertTrue(any("Sensational Performance" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_master_of_the_pageant_discount_and_usage(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.stratagems import Stratagem

        army = Army("Emperor's Children", detachment_type="Court of the Phoenician")
        army.faction_id = "EC"
        player = Player("P1", PlayerType.HUMAN, army=army)
        player.game = SimpleNamespace(turn=1)

        fulgrim_unit = _StubUnit("Fulgrim", army, keywords=["FULGRIM"])
        strat = Stratagem(
            id="sinuous",
            name="Sinuous Breach",
            type="Stratagem",
            description="",
            cp_cost=1,
            turn="Your turn",
            phase="Movement phase",
            detachment="Court of the Phoenician",
            faction_id="EC",
        )

        prev = player.preview_stratagem_cp_cost(strat, target_unit=fulgrim_unit, assume_optional_discounts=True)
        self.assertEqual(int(prev.get("discount", 0)), 1)

        player.set_next_optional_decision("MASTER_OF_THE_PAGEANT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=fulgrim_unit)
        self.assertEqual(int(applied.get("cost", 1)), 0)
        self.assertEqual(int(army.emperors_children.master_of_pageant_used_round or 0), 1)

        prev2 = player.preview_stratagem_cp_cost(strat, target_unit=fulgrim_unit, assume_optional_discounts=True)
        self.assertEqual(int(prev2.get("discount", 0)), 0)

    def test_unbound_arrogance_increases_pledge(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType

        army = Army("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        player = Player("P1", PlayerType.HUMAN, army=army)

        game = SimpleNamespace(
            turn=1,
            event_system=SimpleNamespace(subscribe=lambda *args, **kwargs: None),
        )
        player.set_game(game)
        player.command_points = 1

        unit = _StubUnit("EC Unit", army, faction_keywords=["EMPEROR'S CHILDREN"])
        manager = player.stratagems
        manager._current_phase_name = "Shooting phase"

        ok = manager.use("UNBOUND ARROGANCE", unit=unit, target_unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(army.emperors_children.pledge_target or 0), 1)
        self.assertEqual(int(army.emperors_children.unbound_arrogance_used_round or 0), 1)


if __name__ == "__main__":
    unittest.main()
