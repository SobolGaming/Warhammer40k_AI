import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="World Eaters",
        keywords=None,
        faction_keywords=None,
        cost=100,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "6",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, faction_name="World Eaters", keywords=None, faction_keywords=None, cost=100):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
    )
    return Unit(datasheet)


class TestBloodTithe(unittest.TestCase):
    def _make_game(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        we_army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        we_army.faction_id = "WE"
        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"

        p1 = Player("P1", control=PlayerControl.LOCAL, army=we_army)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
        game.add_player(p1)
        game.add_player(p2)

        return game, we_army, enemy_army, p1, p2

    def test_blood_tithe_points_gain_on_kill(self):
        game, we_army, enemy_army, _p1, _p2 = self._make_game()
        attacker = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])

        we_army.add_unit(attacker)
        enemy_army.add_unit(enemy)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=attacker)

        self.assertEqual(we_army.world_eaters_detachments.blood_tithe_points, 1)

    def test_blood_tithe_points_not_gained_on_low_roll(self):
        game, we_army, enemy_army, _p1, _p2 = self._make_game()
        attacker = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])

        we_army.add_unit(attacker)
        enemy_army.add_unit(enemy)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=attacker)

        self.assertEqual(we_army.world_eaters_detachments.blood_tithe_points, 0)

    def test_blood_tithe_enraged_abjuration_adds_fnp(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        mgr = army.world_eaters_detachments
        mgr.blood_tithe_active.add("ENRAGED_ABJURATION")

        fnps = unit.has_feel_no_pain()
        self.assertIn((5, "against psychic attacks and mortal wounds"), fnps)

    def test_blood_tithe_daemonic_rage_adds_lance_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.wargear import WargearProfile

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        target = _make_unit("Target", faction_name="Enemy", faction_keywords=["ENEMY"])
        army.add_unit(unit)
        unit.set_parent_army(army)

        mgr = army.world_eaters_detachments
        mgr.blood_tithe_active.add("DAEMONIC_RAGE")

        try:
            unit.round_state.charged_this_round = True
        except Exception:
            pass

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        attacker = unit.models[0]
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
        self.assertTrue(res.get("wound", False))
        self.assertIn("+1 to wound from Lance (Blood Tithe)", res.get("modifiers", []))

    def test_blood_tithe_boon_of_blood_sets_invulnerable(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.wargear import WargearProfile

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)
        unit.set_parent_army(army)

        mgr = army.world_eaters_detachments
        mgr.blood_tithe_active.add("BOON_OF_BLOOD")

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        target_model = unit.models[0]
        save_res = profile._save_with_tracking(target_model, {}, ap=0)
        self.assertEqual(int(save_res.get("final_save", 0)), 4)

    def test_blood_tithe_might_of_khorne_grants_blessings(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(unit)

        mgr = army.world_eaters_detachments
        mgr.blood_tithe_active.add("MIGHT_OF_KHORNE")

        self.assertTrue(unit.attached_unit_has_blessings_of_khorne())

    def test_blood_tithe_decision_uses_khorne_daemonkin_manager(self):
        from warhammer40k_ai.engine.decision_handlers.abilities import (
            _apply_choose_blood_tithe,
            _validate_choose_blood_tithe,
        )
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BLOOD_TITHE
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        game, we_army, _enemy_army, p1, _p2 = self._make_game()
        mgr = we_army.world_eaters_detachments
        mgr.blood_tithe_points = 2
        army_id = get_entity_id(we_army)
        option = DecisionOption.create(
            "Enraged Abjuration",
            payload={
                "army_id": army_id,
                "ability_key": "ENRAGED_ABJURATION",
                "timing": "command_phase",
            },
        )
        request = DecisionRequest.create(
            DECISION_CHOOSE_BLOOD_TITHE,
            "Select a Blood Tithe ability.",
            player_id=p1.id,
            options=[option],
            context={"army_id": army_id, "timing": "command_phase"},
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=p1.id,
            option_id=option.option_id,
            payload={},
        )

        self.assertEqual(_validate_choose_blood_tithe(game, request, result), ())
        self.assertTrue(_apply_choose_blood_tithe(game, request, result))
        self.assertEqual(mgr.blood_tithe_points, 0)
        self.assertIn("ENRAGED_ABJURATION", mgr.blood_tithe_active)

    def test_a_worthy_skull_grants_btp(self):
        game, we_army, enemy_army, p1, _p2 = self._make_game()
        we_unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy_unit = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Character"],
        )

        we_army.add_unit(we_unit)
        enemy_army.add_unit(enemy_unit)
        p1.command_points = 1

        game.event_system.publish("phase_start", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        manager = p1.stratagems

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            ok = manager.use(
                "A WORTHY SKULL",
                unit=we_unit,
                target_unit=enemy_unit,
                phase_name="Fight phase",
            )

        self.assertTrue(ok)
        self.assertEqual(we_army.world_eaters_detachments.blood_tithe_points, 3)

    def test_khorne_daemonkin_points_cap_enforced(self):
        from warhammer40k_ai.roster.army import Army, ArmyValidationError

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin", points_limit=2000)
        army.faction_id = "WE"
        unit1 = _make_unit(
            "Bloodletters 1",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
            cost=600,
        )
        unit2 = _make_unit(
            "Bloodletters 2",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
            cost=600,
        )
        army.add_unit(unit1)
        army.add_unit(unit2)

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_blood_legions_cannot_be_warlord(self):
        from warhammer40k_ai.roster.army import Army, ArmyValidationError

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Bloodletters",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
            cost=100,
        )
        unit.is_warlord = True
        army.warlord = unit
        army.add_unit(unit)

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_disciple_of_khorne_cannot_be_warlord(self):
        from warhammer40k_ai.roster.army import Army, ArmyValidationError

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _make_unit(
            "Champion",
            keywords=["WORLD EATERS"],
            faction_keywords=["WORLD EATERS"],
            cost=100,
        )
        unit.is_warlord = True
        unit.enhancement = SimpleNamespace(id="000010078004")
        army.warlord = unit
        army.add_unit(unit)

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()


if __name__ == "__main__":
    unittest.main()
