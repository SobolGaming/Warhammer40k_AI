import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestMaleficSurge(unittest.TestCase):
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
        unit.embarked_in = None
        unit.is_alive = lambda: True
        unit.is_in_reserves = lambda: False
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.has_any_keyword = lambda kw: str(kw or "").strip().upper() == "CHAOS KNIGHTS"
        unit.faction_keywords = ["CHAOS KNIGHTS"]
        return unit

    def _make_model(self, name, unit):
        model = Model(
            name=name,
            movement=10,
            toughness=10,
            save=3,
            wounds=10,
            leadership=6,
            objective_control=3,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _setup_game(self):
        army = Army.with_detachment("Chaos Knights", detachment_type="Infernal Lance")
        army.faction_id = "QT"
        player = Player("CK", PlayerControl.REMOTE, army=army)
        game = SimpleNamespace(turn=1, get_current_player=lambda: player, map=None, is_authoritative=True)
        player.game = game
        army.player = player
        return army, player, game

    def test_malefic_surge_empowers_and_can_damage(self):
        army, _player, game = self._setup_game()
        unit = self._make_unit("Knight", army)
        army.units = [unit]
        mgr = army.chaos_knights_detachments

        wounds = []

        def _apply_mw(_target, amount, **_kwargs):
            wounds.append(int(amount))
            return 0

        unit._apply_mortal_wounds_to_unit = _apply_mw
        unit.pass_leadership_check = lambda **_kwargs: False

        result = mgr.apply_malefic_surge(unit, game=game)
        self.assertTrue(result.get("ok", False))
        self.assertTrue(unit.special_rules.get("malefic_surge_empowered"))
        self.assertEqual(unit.special_rules.get("malefic_surge_empowered_turn"), 1)
        self.assertTrue(wounds and wounds[0] > 0)

    def test_unholy_hunger_adds_movement_bonus(self):
        army, _player, game = self._setup_game()
        unit = self._make_unit("War Dog", army)
        model = self._make_model("War Dog", unit)
        unit.models = [model]
        army.units = [unit]
        mgr = army.chaos_knights_detachments

        unit.special_rules["malefic_surge_empowered"] = True
        unit.special_rules["malefic_surge_empowered_turn"] = 1
        unit.special_rules["malefic_surge_empowered_owner"] = army.player.id

        applied = mgr.apply_malefic_surge_choice(unit, trigger="movement", choice="UNHOLY_HUNGER", game=game)
        self.assertTrue(applied)
        self.assertEqual(model.get_temporary_movement_bonus(), 3)
        self.assertFalse(unit.special_rules.get("malefic_surge_empowered"))

    def test_diabolic_power_sets_special_rules(self):
        army, _player, game = self._setup_game()
        unit = self._make_unit("Knight", army)
        army.units = [unit]
        mgr = army.chaos_knights_detachments

        unit.special_rules["malefic_surge_empowered"] = True
        unit.special_rules["malefic_surge_empowered_turn"] = 1
        unit.special_rules["malefic_surge_empowered_owner"] = army.player.id

        applied = mgr.apply_malefic_surge_choice(unit, trigger="shooting", choice="SUSTAINED_HITS_1", game=game)
        self.assertTrue(applied)
        self.assertTrue(unit.special_rules.get("malefic_surge_diabolic_active"))
        self.assertEqual(unit.special_rules.get("malefic_surge_diabolic_choice"), "SUSTAINED_HITS_1")
        self.assertEqual(unit.special_rules.get("malefic_surge_diabolic_attack_type"), "ranged")
        self.assertFalse(unit.special_rules.get("malefic_surge_empowered"))

    def test_unnatural_fortitude_applies_invulnerable_save(self):
        army, _player, game = self._setup_game()
        unit = self._make_unit("Knight", army)
        model = self._make_model("Knight", unit)
        unit.models = [model]
        army.units = [unit]
        mgr = army.chaos_knights_detachments

        unit.special_rules["malefic_surge_empowered"] = True
        unit.special_rules["malefic_surge_empowered_turn"] = 1
        unit.special_rules["malefic_surge_empowered_owner"] = army.player.id

        applied = mgr.apply_malefic_surge_choice(unit, trigger="targeted_shooting", choice="INVULN_5", game=game)
        self.assertTrue(applied)
        inv_val, _src = model.get_temporary_invulnerable_save()
        self.assertEqual(inv_val, 5)
        self.assertFalse(unit.special_rules.get("malefic_surge_empowered"))


if __name__ == "__main__":
    unittest.main()
