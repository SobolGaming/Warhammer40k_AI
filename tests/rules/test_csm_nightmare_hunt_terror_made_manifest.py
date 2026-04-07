from __future__ import annotations

import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    wounds: str = "3",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _place(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_profile(*, weapon_type: str, strength: str = "4"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    target_army = Army.with_detachment("Enemy", "Other")
    target_army.faction_id = "EN"
    nightmare_army = Army.with_detachment("Chaos Space Marines", "Nightmare Hunt")
    nightmare_army.faction_id = "CSM"
    target_player = Player("Target", control=PlayerControl.REMOTE, army=target_army)
    nightmare_player = Player("Nightmare", control=PlayerControl.REMOTE, army=nightmare_army)
    game.add_player(target_player)
    game.add_player(nightmare_player)
    game.current_player_index = 0
    game.turn = 1
    return game, target_player, nightmare_player, target_army, nightmare_army


class TestCsmNightmareHuntTerrorMadeManifest(unittest.TestCase):
    def test_forced_command_phase_test_applies_minus_one_and_suppression(self):
        game, target_player, _nightmare_player, target_army, nightmare_army = _build_game()
        source = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        target = _make_unit(
            "Target Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        target.models[0].wounds = 1
        _place(source, 10.0, 10.0)
        _place(target, 14.0, 10.0)
        nightmare_army.add_unit(source)
        target_army.add_unit(target)
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        captured = {"modifier": None, "reasons": []}
        original_take = target.take_battle_shock_test

        def _capture_take(*args, **kwargs):
            sr = dict(getattr(target, "special_rules", {}) or {})
            captured["modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0)
            captured["reasons"] = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            return original_take(*args, **kwargs)

        target.take_battle_shock_test = _capture_take
        tested_ids: set[str] = set()
        Game._apply_csm_dread_talons_terror_descends_forced_tests(game, target_player, tested_ids)

        self.assertEqual(captured["modifier"], -1)
        self.assertTrue(any("Terror Made Manifest" in str(r) for r in list(captured["reasons"] or [])))
        self.assertIn(str(get_entity_id(target) or ""), tested_ids)
        sr = dict(getattr(target, "special_rules", {}) or {})
        self.assertEqual(sr.get("battle_shock_suppress_other_tests_phase"), "COMMAND_PHASE")
        self.assertEqual(sr.get("battle_shock_suppress_other_tests_source"), "Terror Made Manifest")

    def test_hit_bonus_applies_against_below_half_strength_targets(self):
        _game, _target_player, _nightmare_player, target_army, nightmare_army = _build_game()
        attacker_unit = _make_unit(
            "Night Lords",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        target.models[0].wounds = 1
        nightmare_army.add_unit(attacker_unit)
        target_army.add_unit(target)
        attacker_model = attacker_unit.models[0]
        profile = _make_profile(weapon_type="ranged")

        hit_result = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Terror Made Manifest" in m for m in list(hit_result.get("modifiers", []) or [])))

    def test_attacker_battle_shocked_penalty_applies_when_targeting_heretic_astartes(self):
        _game, _target_player, _nightmare_player, target_army, nightmare_army = _build_game()
        attacker_unit = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        attacker_unit.status_effects.append(BattleShockEffect(current_turn=1))
        target = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        target_army.add_unit(attacker_unit)
        nightmare_army.add_unit(target)
        attacker_model = attacker_unit.models[0]
        profile = _make_profile(weapon_type="ranged")

        hit_result = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Terror Made Manifest" in m for m in list(hit_result.get("modifiers", []) or [])))

    def test_wound_bonus_applies_against_battle_shocked_targets(self):
        _game, _target_player, _nightmare_player, target_army, nightmare_army = _build_game()
        attacker_unit = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        target.status_effects.append(BattleShockEffect(current_turn=1))
        nightmare_army.add_unit(attacker_unit)
        target_army.add_unit(target)
        attacker_model = attacker_unit.models[0]
        profile = _make_profile(weapon_type="ranged")

        wound_result = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Terror Made Manifest" in m for m in list(wound_result.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
