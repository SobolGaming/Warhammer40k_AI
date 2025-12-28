import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestBlessingsOfKhorne(unittest.TestCase):
    def test_double_requires_matching(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager, BlessingsRollContext, BlessingsTiming

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)

        # Dice include a 5 and a 6 but not a pair (5,5) or (6,6); Warp Blades needs double 5+ OR triple 2+
        ctx = BlessingsRollContext(
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            battle_round=1,
            dice=[5, 6, 1, 1, 1, 1, 1, 1],
            rerolls_allowed=0,
            rerolled_indices=[],
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=False,
        )
        preview = mgr.preview_choice(ctx, selected_blessing_keys=["WARP_BLADES"])
        self.assertFalse(preview["ok"])

    def test_activate_two_blessings_with_disjoint_pairs(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager, BlessingsRollContext, BlessingsTiming

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)

        # Double 6+ (Decapitating) and double 5+ (Warp Blades)
        ctx = BlessingsRollContext(
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            battle_round=1,
            dice=[6, 6, 5, 5, 2, 2, 1, 1],
            rerolls_allowed=0,
            rerolled_indices=[],
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=False,
        )
        res = mgr.apply_choice(ctx, selected_blessing_keys=["DECAPITATING_STRIKES", "WARP_BLADES"])
        self.assertEqual(set(res["activated"]), {"DECAPITATING_STRIKES", "WARP_BLADES"})
        self.assertTrue(mgr.is_blessing_active("DECAPITATING_STRIKES", battle_round=1))
        self.assertTrue(mgr.is_blessing_active("WARP_BLADES", battle_round=1))

    def test_favoured_rerolls_up_to_two_indices(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager, BlessingsTiming

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)

        # Build ctx with deterministic dice
        seq = iter([1, 1, 2, 2, 3, 3, 4, 4])
        ctx = mgr.create_roll_context(
            battle_round=1,
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            rerolls_allowed=2,
            max_activations=2,
            counts_toward_baseline_limit=True,
            roll_d6=lambda: next(seq),
        )
        self.assertEqual(ctx.dice, [1, 1, 2, 2, 3, 3, 4, 4])
        # Reroll indices 0 and 7 into 6 and 5
        rr_seq = iter([6, 5])
        mgr.reroll_indices(ctx, [0, 7], roll_d6=lambda: next(rr_seq))
        self.assertEqual(ctx.dice[0], 6)
        self.assertEqual(ctx.dice[7], 5)

    def test_reborn_in_blood_consumes_triple_six_and_activates_no_blessings(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager, BlessingsRollContext, BlessingsTiming

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)

        ctx = BlessingsRollContext(
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            battle_round=1,
            dice=[6, 6, 6, 1, 1, 1, 2, 2],
            rerolls_allowed=0,
            rerolled_indices=[],
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=True,
        )
        res = mgr.apply_choice(ctx, selected_blessing_keys=[], use_reborn_in_blood=True)
        self.assertTrue(res["reborn_used"])
        self.assertEqual(res["activated"], [])

    def test_total_carnage_queue_resolves_after_attacks(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)
        mgr.active_blessing_keys.add("TOTAL_CARNAGE")

        calls = {"n": 0}

        class _Unit:
            def _try_fight_on_death(self, model, game_map):
                calls["n"] += 1
                return True

        dummy_unit = _Unit()
        mgr.queue_total_carnage_model(object())

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            mgr.resolve_total_carnage_queue(owning_unit=dummy_unit, game_map=object())
        self.assertEqual(calls["n"], 1)


class TestBlessingsCombatInjection(unittest.TestCase):
    def _make_melee_profile(self, keywords: str = ""):
        from warhammer40k_ai.classes.wargear import Wargear
        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee", **data})
        return parent.profiles["default"]

    def _mk_attacker_stack(self, *, active_keys: set[str]):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager

        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)
        mgr.active_blessing_keys |= set(active_keys)

        class _ES:
            def publish(self, *_args, **_kwargs):
                return None

        game = SimpleNamespace(turn=1, event_system=_ES())
        player = SimpleNamespace(game=game, name="P1")
        army = SimpleNamespace(player=player, blessings_of_khorne=mgr)

        class _Unit:
            def __init__(self):
                self.round_state = SimpleNamespace(charged_this_round=False, fought_this_phase=False)
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            def attached_unit_has_blessings_of_khorne(self):
                return True

        unit = _Unit()
        attacker = SimpleNamespace(name="Attacker", parent_unit=unit)
        return attacker

    def test_warp_blades_grants_lethal_hits_on_melee_crit(self):
        profile = self._make_melee_profile("")
        attacker = self._mk_attacker_stack(active_keys={"WARP_BLADES"})
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        # Hit roll 6 to trigger crit-hit branch
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("lethal_hit", False))

    def test_martial_excellence_grants_sustained_hits_1_on_melee_crit(self):
        profile = self._make_melee_profile("")
        attacker = self._mk_attacker_stack(active_keys={"MARTIAL_EXCELLENCE"})
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

    def test_decapitating_strikes_grants_dev_wounds_vs_infantry_on_crit_wound(self):
        profile = self._make_melee_profile("")
        attacker = self._mk_attacker_stack(active_keys={"DECAPITATING_STRIKES"})

        class _Target:
            toughness = 4
            models = [SimpleNamespace(is_alive=True)]

            def has_keyword(self, k: str) -> bool:
                return str(k).strip().lower() == "infantry"

        target = _Target()
        attack_instance = {}
        # Wound roll 6 => critical wound branch; should apply mortal_wound due to blessings
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["wound"])
        self.assertTrue(attack_instance.get("mortal_wound", False))


if __name__ == "__main__":
    unittest.main()


