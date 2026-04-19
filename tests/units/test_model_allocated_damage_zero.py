import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, wounds=3):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, wounds=3):
    return Unit(_MockDatasheet(name, abilities=abilities, wounds=wounds))


def _make_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestModelAllocatedDamageZero(unittest.TestCase):
    def test_chaos_familiar_sets_damage_zero_once_per_battle(self):
        ability = {
            "name": "Chaos Familiar",
            "description": "Once per battle, when an attack is allocated to the bearer, you can change the Damage characteristic to 0.",
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Sorcerer", abilities=[ability], wounds=3)
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "DEF"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.REMOTE, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]

        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)

        profile = _make_profile()
        rolls = iter([6, 6, 1])

        def _roll(_expr):
            try:
                return next(rolls)
            except StopIteration:
                return 1

        with patch("warhammer40k_ai.units.wargear.get_roll", _roll):
            result = profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)

        self.assertIsNotNone(result)
        self.assertEqual(target_unit.models[0].wounds, 3)

        specs = target_unit.model_allocated_damage_zero_specs(target_unit.models[0])
        key = specs[0]["key"]
        self.assertTrue(target_unit.models[0].has_used_once_per_battle(key))

        # Second attack should apply damage (ability already spent).
        rolls = iter([6, 6, 1])

        with patch("warhammer40k_ai.units.wargear.get_roll", _roll):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)

        self.assertEqual(target_unit.models[0].wounds, 1)

    def test_surgeon_acolyte_sets_damage_zero_once_per_turn(self):
        ability = {
            "name": "Surgeon Acolyte",
            "description": (
                "Once per turn, when an attack is allocated to a model in this unit, if this unit contains "
                "FABIUS BILE, you can change the Damage characteristic of that attack to 0."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Fabius Bile", abilities=[ability], wounds=5)
        target_unit.models[0].name = "Fabius Bile"
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "CSM"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.REMOTE, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]
        game.turn = 1

        profile = _make_profile()

        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 5)

        # Same turn: ability already consumed, so damage is applied.
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 3)

        # Next turn: ability can be used again.
        game.turn = int(getattr(game, "turn", 0) or 0) + 1
        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 3)

    def test_ablative_plating_is_mandatory_and_auto_applies(self):
        ability = {
            "name": "Ablative Plating",
            "description": "Once per battle, when an attack is allocated to this model, you change the Damage characteristic of that attack to 0.",
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Rogal Dorn", abilities=[ability], wounds=3)
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "AM"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.REMOTE, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]

        profile = _make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 3)

        specs = list(target_unit.model_allocated_damage_zero_specs(target_unit.models[0]) or [])
        self.assertTrue(specs)
        self.assertEqual(specs[0].get("usage"), "battle")
        self.assertFalse(bool(specs[0].get("optional", True)))
        self.assertTrue(target_unit.models[0].has_used_once_per_battle(specs[0]["key"]))

        # Second attack applies damage because mandatory once-per-battle usage is spent.
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 1)

    def test_inviolable_transport_sets_damage_zero_once_per_battle_round(self):
        ability = {
            "name": "Inviolable Transport",
            "description": (
                "Once per battle round, when an attack is allocated to this model, you can change the Damage characteristic "
                "of that attack to 0."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Transport", abilities=[ability], wounds=5)
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "TAU"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.REMOTE, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]

        profile = _make_profile()

        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 5)

        specs = list(target_unit.model_allocated_damage_zero_specs(target_unit.models[0]) or [])
        self.assertTrue(specs)
        self.assertEqual(specs[0].get("usage"), "battle_round")
        self.assertTrue(bool(specs[0].get("optional", False)))
        self.assertTrue(target_unit.models[0].has_used_once_per_battle_round(specs[0]["key"]))

        # Same battle round: effect cannot be used again.
        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 3)

        # Next battle round: effect is available again.
        game.turn = int(getattr(game, "turn", 0) or 0) + 1
        defender.set_next_optional_decision("MODEL_ALLOCATED_DAMAGE_ZERO", True)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)
        self.assertEqual(target_unit.models[0].wounds, 3)

    def test_local_provider_consumes_queued_damage_zero_confirmation(self):
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        ability = {
            "name": "Chaos Familiar",
            "description": "Once per battle, when an attack is allocated to the bearer, you can change the Damage characteristic to 0.",
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Sorcerer", abilities=[ability], wounds=3)
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "DEF"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.LOCAL, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]

        seen = {"pending": 0}

        def _provider(**_kwargs):
            pending = [
                req
                for req in list(game.decision_queue.list() or [])
                if str(getattr(req, "context", {}).get("ability", "") or "") == "model_allocated_damage_zero"
            ]
            self.assertTrue(pending)
            req = pending[0]
            seen["pending"] = len(pending)
            option_id = next(
                opt.option_id
                for opt in list(getattr(req, "options", []) or [])
                if bool(getattr(opt, "payload", {}).get("choice", False))
            )
            _, apply_result = resolve_decision_value(game, req, option_id, player_id=getattr(defender, "id", None))
            self.assertIsNotNone(apply_result)
            self.assertTrue(getattr(apply_result, "ok", False))
            return "use"

        game.map.model_allocated_damage_zero_provider = _provider

        profile = _make_profile()
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            result = profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)

        self.assertIsNotNone(result)
        self.assertEqual(target_unit.models[0].wounds, 3)
        self.assertEqual(seen["pending"], 1)
        self.assertEqual(list(game.decision_queue.list() or []), [])

    def test_local_damage_zero_without_sync_owner_raises_and_leaves_request_pending(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO

        ability = {
            "name": "Chaos Familiar",
            "description": "Once per battle, when an attack is allocated to the bearer, you can change the Damage characteristic to 0.",
            "type": "Datasheet",
            "parameter": "",
        }
        target_unit = _make_unit("Sorcerer", abilities=[ability], wounds=3)
        attacker_unit = _make_unit("Attacker", wounds=3)

        attacker_army = Army.with_detachment("Attacker", detachment_type="Other")
        attacker_army.faction_id = "ATK"
        defender_army = Army.with_detachment("Defender", detachment_type="Other")
        defender_army.faction_id = "DEF"
        attacker = Player("Attacker", PlayerControl.REMOTE, army=attacker_army)
        defender = Player("Defender", PlayerControl.LOCAL, army=defender_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[attacker, defender])
        attacker_army.add_unit(attacker_unit)
        defender_army.add_unit(target_unit)
        game.map.units = [attacker_unit, target_unit]

        profile = _make_profile()
        with self.assertRaisesRegex(
            RuntimeError,
            "MODEL_ALLOCATED_DAMAGE_ZERO' remained pending without a synchronous decision owner",
        ):
            with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
                profile.attack(target_unit, attacker_unit.models[0], game_map=game.map)

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].decision_type, DECISION_CONFIRM_YES_NO)
        self.assertEqual(str((pending[0].context or {}).get("ability", "") or ""), "model_allocated_damage_zero")


if __name__ == "__main__":
    unittest.main()
