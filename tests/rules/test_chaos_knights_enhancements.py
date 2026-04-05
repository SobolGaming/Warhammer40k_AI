import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp, compute_save_roll_modifier
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestChaosKnightsEnhancements(unittest.TestCase):
    def _setup_game(self, phase_name: str = "COMMAND_PHASE", detachment_type: str = "Infernal Lance"):
        army = Army("Chaos Knights", detachment_type=detachment_type)
        army.faction_id = "QT"
        player = Player("CK", PlayerControl.REMOTE, army=army)
        phase = SimpleNamespace(name=phase_name)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player, map=None, is_authoritative=True, phase=phase)
        player.game = game
        army.player = player
        return army, player, game

    def _make_unit(self, name, army):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = "QT"
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.special_rules = {}
        unit.keywords = []
        unit.embarked_in = None
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.has_any_keyword = lambda kw: str(kw or "").strip().upper() == "CHAOS KNIGHTS"
        unit.faction_keywords = ["CHAOS KNIGHTS"]
        unit._characteristic_modifiers = {}
        unit.round_state = SimpleNamespace(
            move_modifier_choice=None,
            move_modifier_choice_pending=False,
            advance_modifier_choice=None,
            advance_modifier_choice_pending=False,
            advance_roll_unmodified=None,
            advance_roll=None,
            moved_this_round=False,
            remained_stationary_this_round=False,
            advanced_this_round=False,
            fell_back_this_round=False,
        )
        return unit

    def _make_model(self, name, unit, *, movement=10, toughness=10):
        model = Model(
            name=name,
            movement=movement,
            toughness=toughness,
            save=3,
            wounds=10,
            leadership=6,
            objective_control=3,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model._id = name
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_blasphemous_engine_reroll_source(self):
        army, _player, game = self._setup_game()
        unit = self._make_unit("Knight", army)
        unit.special_rules["enhancement_blasphemous_engine"] = True
        army.units = [unit]
        captured = {}

        def _pass_leadership_check(**kwargs):
            captured.update(kwargs)
            return True

        unit.pass_leadership_check = _pass_leadership_check
        mgr = army.chaos_knights_detachments
        mgr.apply_malefic_surge(unit, game=game)
        self.assertIn("Blasphemous Engine", captured.get("extra_reroll_sources", []))

    def test_blasphemous_engine_adds_wounds(self):
        army, _player, _game = self._setup_game()
        unit = self._make_unit("Knight", army)
        model = self._make_model("Knight", unit)
        unit.models = [model]
        army.units = [unit]
        unit._get_enhancement_bearer_model = lambda: model
        base_wounds = int(getattr(model, "_base_wounds", getattr(model, "_wounds", 0)) or 0)

        waha = WahaHelper()
        enh = waha.get_enhancement_by_name("Blasphemous Engine")
        self.assertIsNotNone(enh)
        enh.apply_to_unit(unit)
        self.assertEqual(int(getattr(model, "_base_wounds", 0) or 0), base_wounds + 2)

    def test_knight_diabolus_ws_and_lance(self):
        army, _player, game = self._setup_game(phase_name="FIGHT_PHASE")
        unit = self._make_unit("Knight", army)
        model = self._make_model("Knight", unit)
        unit.models = [model]
        army.units = [unit]
        unit.special_rules["enhancement_knight_diabolus"] = True
        unit.special_rules["enhancement_bearer_model_id"] = model._id
        unit.special_rules["malefic_surge_diabolic_active"] = True
        unit.special_rules["malefic_surge_diabolic_choice"] = "LETHAL_HITS"
        unit.special_rules["malefic_surge_diabolic_attack_type"] = "melee"
        unit.special_rules["malefic_surge_diabolic_expires_phase"] = "FIGHT_PHASE"

        weapon = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = next(iter(weapon.profiles.values()))
        attack_instance = {}
        target = self._make_unit("Target", army)
        target_model = self._make_model("Target", target)
        target.models = [target_model]
        hit_result = profile._hit_target_with_tracking(
            target,
            model,
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(hit_result.get("base_skill"), 3)
        self.assertTrue(attack_instance.get("bonus_lance"))
        self.assertIn("Knight Diabolus", attack_instance.get("bonus_lance_source", ""))

    def test_fleshmetal_fusion_toughness_and_save_bonus(self):
        army, _player, _game = self._setup_game()
        unit = self._make_unit("Knight", army)
        model = self._make_model("Knight", unit, toughness=10)
        unit.models = [model]
        army.units = [unit]
        unit._get_enhancement_bearer_model = lambda: model
        enh = Enhancement(
            id="000010304004",
            name="Fleshmetal Fusion",
            faction_id="QT",
            detachment="Infernal Lance",
            description="",
        )
        enh.apply_to_unit(unit)
        self.assertEqual(getattr(model, "_toughness", 0), 11)

        unit.special_rules["fleshmetal_fusion_fortitude_active"] = True
        unit.special_rules["fleshmetal_fusion_fortitude_expires_phase"] = "SHOOTING_PHASE"
        unit.special_rules["enhancement_bearer_model_id"] = model._id
        attack_instance = {"damage_characteristic": 1}
        mod, _effects = compute_save_roll_modifier(
            model,
            attack_instance=attack_instance,
            ap=0,
            save_type="armor",
            weapon_profile=None,
        )
        self.assertEqual(mod, 1)

        other = self._make_model("Other", unit, toughness=10)
        other._id = "Other"
        unit.models.append(other)
        mod_other, _ = compute_save_roll_modifier(
            other,
            attack_instance=attack_instance,
            ap=0,
            save_type="armor",
            weapon_profile=None,
        )
        self.assertEqual(mod_other, 0)

    def test_bestial_aspect_assault_and_ignore_modifiers(self):
        army, _player, _game = self._setup_game(phase_name="MOVEMENT_PHASE")
        unit = self._make_unit("War Dog", army)
        model = self._make_model("War Dog", unit, movement=10)
        unit.models = [model]
        army.units = [unit]
        unit._get_enhancement_bearer_model = lambda: model
        enh = Enhancement(
            id="000010304005",
            name="Bestial Aspect",
            faction_id="QT",
            detachment="Infernal Lance",
            description="",
        )
        enh.apply_to_unit(unit)

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = next(iter(weapon.profiles.values()))
        self.assertTrue(unit.can_shoot_after_advance(profile))

        unit.special_rules["malefic_surge_unholy_hunger_active"] = True
        unit.special_rules["malefic_surge_unholy_hunger_expires_phase"] = "MOVEMENT_PHASE"
        unit.round_state.move_modifier_choice = "ignore_negative"
        unit.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:slow"))
        mv = unit.get_effective_model_characteristic(model, "movement")
        self.assertEqual(mv, 10)

    def test_diabolical_resilience_fnp_and_modifier_ignores(self):
        army, _player, _game = self._setup_game(phase_name="MOVEMENT_PHASE", detachment_type="Iconoclast Fiefdom")
        unit = self._make_unit("Knight", army)
        model = self._make_model("Knight", unit, movement=10)
        unit.models = [model]
        army.units = [unit]
        unit._get_enhancement_bearer_model = lambda: model
        enh = Enhancement(
            id="000009765005",
            name="Diabolical Resilience",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        )
        enh.apply_to_unit(unit)
        self.assertTrue(bool(unit.special_rules.get("enhancement_iconoclast_diabolical_resilience")))
        fnp_entries = list(unit.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
        self.assertTrue(any(int(entry.get("value", 0) or 0) == 6 for entry in fnp_entries if isinstance(entry, dict)))

        unit.round_state.move_modifier_choice = "ignore_negative"
        unit.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:slow"))
        self.assertEqual(unit.get_effective_model_characteristic(model, "movement"), 10)

        unit.special_rules["advance_roll_modifiers"] = [(-2, "test:slow")]
        unit.round_state.advance_modifier_choice = "ignore_negative"
        self.assertEqual(unit._apply_advance_roll_modifiers(4), 4)

        unit.round_state.charge_modifier_choice = "ignore_negative"
        filtered = unit._filter_diabolical_resilience_roll_modifiers(
            [(-2, "test:slow"), (1, "test:boost")],
            kind="charge",
        )
        self.assertEqual(filtered, [(1, "test:boost")])


if __name__ == "__main__":
    unittest.main()
