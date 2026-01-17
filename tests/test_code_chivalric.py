import unittest
from types import SimpleNamespace


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, cost=100, abilities=None):
        self.name = name
        self.faction_data = {"name": "Imperial Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": "10", "T": "10", "Sv": "2", "W": "12",
            "Ld": "7", "OC": "5",
            "base_size": "100mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [{"name": a, "description": "", "type": "Abilities", "parameter": None} for a in (abilities or [])]
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


class _PlayerStub:
    def __init__(self):
        self.name = "P1"
        self.control = SimpleNamespace(name="REMOTE")
        self.has_control = lambda: False
        self.game = None
        self.gain_calls = []

    def gain_command_points(self, amount, **kwargs):
        self.gain_calls.append((amount, kwargs))


class TestCodeChivalric(unittest.TestCase):
    def test_eager_quality_applies_movement_and_bonuses(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.code_chivalric import CodeChivalricManager, QUALITY_EAGER

        unit = make_unit(
            "Knight",
            keywords=["IMPERIAL KNIGHTS"],
            faction_keywords=["IMPERIUM"],
            abilities=["Code Chivalric"],
        )
        army = Army("Imperial Knights", "Detachment", points_limit=2000)
        army.faction_id = "QI"
        army.add_unit(unit)
        army.player = _PlayerStub()

        mgr = CodeChivalricManager(army)
        army.code_chivalric = mgr

        base_move = unit.movement
        mgr.select_quality(QUALITY_EAGER)

        self.assertEqual(unit.movement, base_move + 2)
        self.assertEqual(unit.special_rules.get("code_chivalric_advance_bonus"), 1)
        self.assertEqual(unit.special_rules.get("code_chivalric_charge_bonus"), 1)

    def test_valour_rerolls_hit_and_wound(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.code_chivalric import CodeChivalricManager, QUALITY_VALOUR
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = Army("Imperial Knights", "Detachment", points_limit=2000)
        army.faction_id = "QI"
        game = SimpleNamespace(event_system=EventSystem(), map=None, turn=1)
        player = SimpleNamespace(name="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False, game=game)
        army.player = player

        attacker_unit = make_unit(
            "Knight",
            keywords=["IMPERIAL KNIGHTS"],
            faction_keywords=["IMPERIUM"],
            abilities=["Code Chivalric"],
        )
        target_unit = make_unit(
            "Target",
            keywords=["IMPERIAL KNIGHTS"],
            faction_keywords=["IMPERIUM"],
            abilities=[],
        )
        army.add_unit(attacker_unit)
        attacker_unit.set_parent_army(army)
        target_unit.set_parent_army(army)

        mgr = CodeChivalricManager(army)
        army.code_chivalric = mgr
        mgr.select_quality(QUALITY_VALOUR)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit
        attacker_unit.models = [attacker_model]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=5,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        mgr.grant_rerolls_for_unit(attacker_unit)

        melee_parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: True,
            is_ranged=lambda: False,
        )
        prof = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

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

        from warhammer40k_ai.units import wargear as wargear_mod
        seq = iter([
            2, 5,  # hit roll fail, then reroll success
            2, 5,  # wound roll fail, then reroll success
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Code Chivalric" in x for x in hit_res.get("special_effects", [])))

            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Code Chivalric" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_deed_completion_grants_honour_and_cp(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.code_chivalric import CodeChivalricManager, DEED_TALLY

        army = Army("Imperial Knights", "Detachment", points_limit=2000)
        army.faction_id = "QI"
        army.player = _PlayerStub()

        mgr = CodeChivalricManager(army)
        army.code_chivalric = mgr
        mgr.selected_deed_key = DEED_TALLY.key
        mgr.selected_deed_random = False
        mgr.selected_quality_random = False
        mgr.enemy_units_destroyed_this_round = 3

        mgr.check_end_of_battle_round(battle_round=2)

        self.assertTrue(mgr.honoured)
        self.assertTrue(mgr.deed_completed)
        self.assertEqual(army.player.gain_calls[0][0], 2)
        self.assertTrue(army.player.gain_calls[0][1].get("exempt_from_guardrail"))


if __name__ == "__main__":
    unittest.main()
