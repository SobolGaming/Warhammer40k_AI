from __future__ import annotations

import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        move: str = "6",
        toughness: str = "4",
        wounds: str = "4",
        leadership: str = "7",
        oc: str = "1",
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
                "M": str(move),
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(oc),
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
    move: str = "6",
    toughness: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            move=move,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.embarked_in = None
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Chaos Space Marines", "Creations of Bile")
    army1.faction_id = "CSM"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, p1, p2, army1, army2


def _find_quarry_request(game: Game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key):
            return req
    return None


def _find_option(request, *, choice_key: str = "", mode: str = "", reroll_mode: str = ""):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if choice_key and str(payload.get("choice_key", "") or "").strip().upper() != str(choice_key).strip().upper():
            continue
        if mode and str(payload.get("mode", "") or "").strip().lower() != str(mode).strip().lower():
            continue
        if reroll_mode and str(payload.get("reroll_mode", "") or "").strip().lower() != str(reroll_mode).strip().lower():
            continue
        return opt
    return None


def _make_profile(*, weapon_type: str, skill: str = "4+", strength: str = "4", attacks: str = "1") -> WargearProfile:
    parent = type(
        "_Parent",
        (),
        {
            "name": "Test Weapon",
            "is_melee": staticmethod(lambda: weapon_type.lower() == "melee"),
            "is_ranged": staticmethod(lambda: weapon_type.lower() == "ranged"),
        },
    )()
    data = {
        "range": "Melee" if weapon_type.lower() == "melee" else "24",
        "A": str(attacks),
        "BS_WS": str(skill),
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


class TestCreationsOfBileExperimentalAugmentations(unittest.TestCase):
    def test_prompt_and_manual_selection_applies_movement_bonus(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
            move="6",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(unit)
        army2.add_unit(enemy)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_experimental_augmentations()
        req = _find_quarry_request(game, "experimental_augmentations_choice")
        self.assertIsNotNone(req)
        choice = _find_option(req, choice_key="HYPERADRENAL_INFUSION", mode="manual")
        self.assertIsNotNone(choice)

        result = resolve_decision_command(game, req, choice.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        mgr = army1.chaos_space_marines_detachments
        self.assertTrue(mgr.experimental_augmentations_selected)
        self.assertEqual(set(mgr.experimental_augmentations_active_keys), {"HYPERADRENAL_INFUSION"})
        model = unit.models[0]
        self.assertEqual(unit.get_effective_model_characteristic(model, "movement"), 8)

    def test_random_selection_with_fabius_warlord_offers_reroll_and_finalizes(self):
        game, p1, _p2, army1, army2 = _build_game()
        fabius = _make_unit(
            "Fabius Bile",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        fabius.is_warlord = True
        battleline = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(fabius)
        army1.add_unit(battleline)
        army2.add_unit(enemy)
        army1.warlord = fabius
        game.map.units = [fabius, battleline, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_experimental_augmentations()
        choice_req = _find_quarry_request(game, "experimental_augmentations_choice")
        self.assertIsNotNone(choice_req)
        random_option = _find_option(choice_req, choice_key="ROLL", mode="random")
        self.assertIsNotNone(random_option)

        with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", side_effect=[1, 1, 5]):
            initial_result = resolve_decision_command(game, choice_req, random_option.option_id, player_id=p1.id)
            self.assertTrue(bool(getattr(initial_result, "ok", False)))

            reroll_req = _find_quarry_request(game, "experimental_augmentations_reroll")
            self.assertIsNotNone(reroll_req)
            reroll_option = _find_option(reroll_req, reroll_mode="reroll_first")
            self.assertIsNotNone(reroll_option)
            reroll_result = resolve_decision_command(game, reroll_req, reroll_option.option_id, player_id=p1.id)
            self.assertTrue(bool(getattr(reroll_result, "ok", False)))

        mgr = army1.chaos_space_marines_detachments
        self.assertTrue(mgr.experimental_augmentations_selected)
        self.assertFalse(mgr.has_pending_experimental_augmentations_rolls())
        self.assertEqual(set(mgr.experimental_augmentations_active_keys), {"CHOLINERGIC_ACCELERANTS", "MACROTENSILE_SINEWS"})

    def test_all_augmentation_effects_apply_to_characteristics_and_weapons(self):
        game, _p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
            move="6",
            toughness="4",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        army1.add_unit(unit)
        army2.add_unit(enemy)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        mgr = army1.chaos_space_marines_detachments
        mgr._finalize_experimental_augmentations(
            keys=[
                "CHOLINERGIC_ACCELERANTS",
                "HYPERADRENAL_INFUSION",
                "PARANEURAL_REACTIONS",
                "SUPRACUTANEOUS_CHITINATION",
                "MACROTENSILE_SINEWS",
                "OPHTHALMIC_ENHANCEMENT",
            ],
            battle_round=1,
            mode="manual",
            rolls=[],
        )

        model = unit.models[0]
        self.assertEqual(unit.get_effective_model_characteristic(model, "movement"), 8)
        self.assertEqual(unit.get_effective_model_characteristic(model, "toughness"), 5)

        melee = _make_profile(weapon_type="melee", skill="4+", strength="4", attacks="1")
        ranged = _make_profile(weapon_type="ranged", skill="4+", strength="4", attacks="1")

        hit_melee = melee._hit_target_with_tracking(enemy, model, {})
        self.assertEqual(int(hit_melee.get("base_skill", 0) or 0), 3)
        self.assertTrue(any("Paraneural Reactions" in str(v) for v in list(hit_melee.get("special_effects", []) or [])))

        hit_ranged = ranged._hit_target_with_tracking(enemy, model, {})
        self.assertEqual(int(hit_ranged.get("base_skill", 0) or 0), 3)
        self.assertTrue(any("Ophthalmic Enhancement" in str(v) for v in list(hit_ranged.get("special_effects", []) or [])))

        wound_melee = melee._wound_target_with_tracking(enemy, model, {"_aura_attack_mods": type("_Aura", (), {})()})
        self.assertTrue(any("Macrotensile Sinews" in str(v) for v in list(wound_melee.get("modifiers", []) or [])))

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            attack_result = melee.attack(enemy, model, game_map=None)
        self.assertEqual(int(getattr(attack_result, "attacks_rolled", 0) or 0), 2)
        self.assertTrue(any("Cholinergic Accelerants" in str(v) for v in list(attack_result.attacks_special_modifiers or [])))

    def test_effects_exclude_damned_and_non_infantry_models(self):
        _game, _p1, _p2, army1, _army2 = _build_game()
        eligible = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
            move="6",
            toughness="4",
        )
        damned = _make_unit(
            "Accursed Cultists",
            keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
            faction_keywords=["HERETIC ASTARTES"],
            move="6",
            toughness="4",
        )
        vehicle = _make_unit(
            "Chaos Predator",
            keywords=["HERETIC ASTARTES", "VEHICLE"],
            faction_keywords=["HERETIC ASTARTES"],
            move="10",
            toughness="10",
        )
        army1.add_unit(eligible)
        army1.add_unit(damned)
        army1.add_unit(vehicle)

        mgr = army1.chaos_space_marines_detachments
        mgr._finalize_experimental_augmentations(
            keys=["HYPERADRENAL_INFUSION", "SUPRACUTANEOUS_CHITINATION"],
            battle_round=1,
            mode="manual",
            rolls=[],
        )

        eligible_model = eligible.models[0]
        damned_model = damned.models[0]
        vehicle_model = vehicle.models[0]

        self.assertEqual(eligible.get_effective_model_characteristic(eligible_model, "movement"), 8)
        self.assertEqual(eligible.get_effective_model_characteristic(eligible_model, "toughness"), 5)
        self.assertEqual(damned.get_effective_model_characteristic(damned_model, "movement"), 6)
        self.assertEqual(damned.get_effective_model_characteristic(damned_model, "toughness"), 4)
        self.assertEqual(vehicle.get_effective_model_characteristic(vehicle_model, "movement"), 10)
        self.assertEqual(vehicle.get_effective_model_characteristic(vehicle_model, "toughness"), 10)


if __name__ == "__main__":
    unittest.main()
