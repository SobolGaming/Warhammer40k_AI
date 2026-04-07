from __future__ import annotations

import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POWER_FROM_PAIN_OPTION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        abilities=None,
        wounds: int = 3,
        toughness: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["DRUKHARI"] if faction_name == "Drukhari" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords or [])
        self.keywords = list(keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": str(int(toughness)),
                "Sv": "5",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    abilities=None,
    wounds: int = 3,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            model_count=model_count,
            abilities=abilities,
            wounds=wounds,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Covenite Coterie")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Drukhari", control=PlayerControl.REMOTE, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, p1, p2, drukhari_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _apply_covenite_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="DRU",
        detachment="Covenite Coterie",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_pending_request(game: Game, decision_type: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") == str(decision_type):
            return req
    return None


def _find_option_by_choice_key(request, choice_key: str):
    target = str(choice_key or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        current = str(payload.get("choice_key", "") or "").strip().upper()
        if current == target:
            return option
    return None


def _destroy_models_to_lost(unit: Unit, *, count: int) -> list:
    removed = []
    for _ in range(max(0, int(count))):
        if len(unit.models) <= 1:
            break
        model = unit.models.pop()
        model.wounds = 0
        removed.append(model)
    unit.models_lost.extend(removed)
    return removed


class TestDrukhariCoveniteCoterieEnhancements(unittest.TestCase):
    def test_covenite_coterie_descriptors_registered(self):
        expected = {
            "000010584002": ("Master Regenesist", "fleshcraft_optional_return_up_to_d3_plus_3_instead_of_d3_plus_1"),
            "000010584003": ("Master Nemesine", "grant_bearer_weapon_anti_beast_and_monster"),
            "000010584004": ("Master Artisan", "bearer_wounds_and_bearer_unit_toughness_bonus"),
            "000010584005": (
                "Master Repugnomancer (Aura)",
                "fear_incarnate_range_bonus_and_pain_token_on_friendly_battleshock_fail_or_destroyed",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_master_regenesist_queues_choice_and_applies_d3_plus_3_fleshcraft_return(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Haemonculus",
            model_count=6,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            abilities=[
                {
                    "name": "Fleshcraft (Pain)",
                    "description": "Power from Pain ability.",
                    "type": "Datasheet",
                    "parameter": "",
                }
            ],
        )
        drukhari_army.add_unit(unit)
        _set_unit_position(unit, 0.0, 0.0)
        game.map.units = [unit]
        game.rebuild_entity_registry()
        _apply_covenite_enhancement(unit, enhancement_id="000010584002", enhancement_name="Master Regenesist")

        removed = _destroy_models_to_lost(unit, count=4)
        self.assertEqual(len(removed), 4)
        self.assertEqual(len(list(getattr(unit, "models_lost", []) or [])), 4)

        mgr = drukhari_army.power_from_pain
        mgr.tokens = 1
        queued = mgr.empower_unit_for_trigger(unit, trigger="command", game=game)
        self.assertFalse(queued)
        req = _find_pending_request(game, DECISION_CHOOSE_POWER_FROM_PAIN_OPTION)
        self.assertIsNotNone(req)
        self.assertEqual(str((getattr(req, "context", {}) or {}).get("choice_kind", "") or ""), "master_regenesist")

        enhanced = _find_option_by_choice_key(req, "ENHANCED")
        base = _find_option_by_choice_key(req, "BASE")
        self.assertIsNotNone(enhanced)
        self.assertIsNotNone(base)

        with patch("warhammer40k_ai.rules.power_from_pain.get_roll", return_value=2):
            resolve_decision_command(game, req, enhanced.option_id, player_id=p1.id)

        self.assertEqual(int(mgr.tokens or 0), 0)
        self.assertEqual(len(list(getattr(unit, "models_lost", []) or [])), 0)
        self.assertEqual(len(list(getattr(unit, "models", []) or [])), 6)
        for model in removed:
            self.assertEqual(int(getattr(model, "wounds", 0) or 0), 1)

    def test_master_nemesine_grants_anti_beast_and_monster_to_bearer_weapons_only(self):
        _game, _p1, _p2, drukhari_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Haemonculus",
            model_count=2,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(unit)
        _apply_covenite_enhancement(unit, enhancement_id="000010584003", enhancement_name="Master Nemesine")

        bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_master_nemesine_bearer_model_id", "") or "")
        bearer = None
        other = None
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                bearer = model
            else:
                other = model
        self.assertIsNotNone(bearer)
        self.assertIsNotNone(other)

        bearer_bonus = unit.get_model_weapon_keyword_bonuses(
            model=bearer,
            attack_type="ranged",
        )
        bearer_anti = set(tuple(v) for v in list(bearer_bonus.get("anti_specs", []) or []))
        self.assertIn(("BEAST", 2), bearer_anti)
        self.assertIn(("MONSTER", 4), bearer_anti)

        other_bonus = unit.get_model_weapon_keyword_bonuses(
            model=other,
            attack_type="ranged",
        )
        other_anti = set(tuple(v) for v in list(other_bonus.get("anti_specs", []) or []))
        self.assertNotIn(("BEAST", 2), other_anti)
        self.assertNotIn(("MONSTER", 4), other_anti)

    def test_master_artisan_applies_bearer_wounds_and_unit_toughness_while_bearer_alive(self):
        _game, _p1, _p2, drukhari_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Haemonculus",
            model_count=3,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            wounds=3,
            toughness=4,
        )
        drukhari_army.add_unit(unit)
        models = list(getattr(unit, "models", []) or [])
        self.assertGreaterEqual(len(models), 2)

        base_wounds = {str(get_entity_id(model) or ""): int(getattr(model, "_base_wounds", 0) or 0) for model in models}
        _apply_covenite_enhancement(unit, enhancement_id="000010584004", enhancement_name="Master Artisan")
        sr = getattr(unit, "special_rules", {}) or {}
        bearer_id = str(sr.get("enhancement_master_artisan_bearer_model_id", "") or "")

        bearer = None
        non_bearer = None
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                bearer = model
            else:
                non_bearer = model
        self.assertIsNotNone(bearer)
        self.assertIsNotNone(non_bearer)

        self.assertEqual(int(getattr(bearer, "_base_wounds", 0) or 0), int(base_wounds[bearer_id]) + 1)
        self.assertEqual(
            int(getattr(non_bearer, "_base_wounds", 0) or 0),
            int(base_wounds[str(get_entity_id(non_bearer) or "")]),
        )
        self.assertEqual(int(unit.get_effective_model_characteristic(bearer, "toughness")), 5)
        self.assertEqual(int(unit.get_effective_model_characteristic(non_bearer, "toughness")), 5)

        bearer.wounds = 0
        self.assertEqual(int(unit.get_effective_model_characteristic(non_bearer, "toughness")), 4)

    def test_master_repugnomancer_extends_fear_incarnate_range(self):
        ability = {
            "name": "Fear Incarnate (Aura)",
            "description": (
                "While an enemy unit is within 6\" of this model, in the Battle-shock step of your opponent's Command phase, "
                "if such an enemy unit is below its Starting Strength, it must take a Battle-shock test, subtracting 1 from "
                "that test if it is a PSYKER unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        base_unit = _make_unit(
            "Haemonculus Baseline",
            model_count=1,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            abilities=[ability],
        )
        base_specs = base_unit.model_opponent_command_phase_below_starting_battleshock_specs(base_unit.models[0])
        self.assertEqual(int(base_specs[0].get("range", 0) or 0), 6)

        _game, _p1, _p2, drukhari_army, _enemy_army = _build_game()
        enhanced = _make_unit(
            "Haemonculus",
            model_count=1,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
            abilities=[ability],
        )
        drukhari_army.add_unit(enhanced)
        _apply_covenite_enhancement(
            enhanced,
            enhancement_id="000010584005",
            enhancement_name="Master Repugnomancer (Aura)",
        )
        specs = enhanced.model_opponent_command_phase_below_starting_battleshock_specs(enhanced.models[0])
        self.assertEqual(int(specs[0].get("range", 0) or 0), 9)

    def test_master_repugnomancer_grants_pain_tokens_for_friendly_failed_battleshock_and_destroyed(self):
        game, _p1, _p2, drukhari_army, enemy_army = _build_game()
        source = _make_unit(
            "Haemonculus",
            model_count=1,
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        friendly = _make_unit(
            "Wracks",
            model_count=1,
            keywords=["INFANTRY", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            model_count=1,
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(source)
        drukhari_army.add_unit(friendly)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(friendly, 4.0, 0.0)
        _set_unit_position(enemy, 18.0, 0.0)
        game.map.units = [source, friendly, enemy]
        game.rebuild_entity_registry()

        _apply_covenite_enhancement(
            source,
            enhancement_id="000010584005",
            enhancement_name="Master Repugnomancer (Aura)",
        )
        mgr = drukhari_army.power_from_pain
        mgr.tokens = 0

        destroyed_model = friendly.models[0]
        with patch("warhammer40k_ai.rules.drukhari_detachments.get_roll", side_effect=[4, 4]):
            game._on_battle_shock_test_resolved_power_from_pain(unit=friendly, passed=False)
            destroyed_model.wounds = 0
            game._on_unit_destroyed_power_from_pain(unit=friendly, last_model=destroyed_model)

        self.assertEqual(int(mgr.tokens or 0), 2)


if __name__ == "__main__":
    unittest.main()
