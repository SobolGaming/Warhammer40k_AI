from __future__ import annotations

import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "0",
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
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Subterranean Assault")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.turn = 1
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _set_deployed(unit: Unit, *, deployed: bool, in_reserves: bool) -> None:
    unit.deployed = bool(deployed)
    unit.reserve_status = "reserves" if in_reserves else "deployed"
    unit.embarked_in = None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TYR",
        detachment="Subterranean Assault",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    if bearer_id:
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(*, skill: str = "4+", strength: str = "5") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Monstrous Scything Talons",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestTyranidsSubterraneanAssaultEnhancements(unittest.TestCase):
    def test_subterranean_assault_enhancement_descriptors_exist(self):
        expected = {
            "000010147002": ("Synaptic Strategy", "rapid_ingress_zero_cp_with_repeat_bypass"),
            "000010147003": ("Tremor Senses", "redeploy_units"),
            "000010147004": ("Vanguard Intellect", "strategic_reserves_setup_round_bonus_for_deep_strike"),
            "000010147005": (
                "Trygon Prime",
                "bearer_gain_synapse_and_bearer_melee_strength_and_weapon_skill_bonus",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_synaptic_strategy_allows_rapid_ingress_for_zero_cp_once_per_battle(self):
        game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Trygon",
            keywords=["TYRANIDS", "MONSTER", "TRYGON"],
            faction_keywords=["TYRANIDS"],
        )
        tyr_army.add_unit(bearer)
        _set_deployed(bearer, deployed=False, in_reserves=True)
        _apply_enhancement(bearer, enhancement_id="000010147002", enhancement_name="Synaptic Strategy")

        strat = SimpleNamespace(name="Rapid Ingress", cp_cost=1)
        preview = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=bearer,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Synaptic Strategy" in str(reason) for reason in list(preview.get("reasons", []) or [])))

        tyr_player.set_next_optional_decision("SYNAPTIC_STRATEGY_RAPID_INGRESS", True)
        first = tyr_player.apply_stratagem_cp_cost(strat, target_unit=bearer)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("synaptic_strategy_use", False)))

        second_preview = tyr_player.preview_stratagem_cp_cost(
            strat,
            target_unit=bearer,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(second_preview.get("cost", -1)), 1)

    def test_synaptic_strategy_repeat_bypass_allows_second_rapid_ingress_target(self):
        game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Trygon",
            keywords=["TYRANIDS", "MONSTER", "TRYGON"],
            faction_keywords=["TYRANIDS"],
        )
        other = _make_unit(
            "Raveners",
            keywords=["TYRANIDS", "INFANTRY"],
            faction_keywords=["TYRANIDS"],
        )
        tyr_army.add_unit(bearer)
        tyr_army.add_unit(other)
        _set_deployed(bearer, deployed=False, in_reserves=True)
        _set_deployed(other, deployed=False, in_reserves=True)
        _apply_enhancement(bearer, enhancement_id="000010147002", enhancement_name="Synaptic Strategy")

        manager = StratagemManager(tyr_player)
        manager._used_stratagems_this_phase.add("RAPID INGRESS")
        manager._record_rapid_ingress_use(other)

        self.assertTrue(bool(manager._rapid_ingress_repeat_allowed(target_unit=bearer)))
        self.assertFalse(bool(manager._rapid_ingress_repeat_allowed(target_unit=other)))

    def test_tremor_senses_registers_tyranids_redeploy_with_strategic_reserves_override(self):
        _game, tyr_army, _enemy_army, _tyr_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Trygon",
            keywords=["TYRANIDS", "MONSTER", "TRYGON"],
            faction_keywords=["TYRANIDS"],
        )
        tyr_army.add_unit(bearer)
        _apply_enhancement(bearer, enhancement_id="000010147003", enhancement_name="Tremor Senses")

        has_redeploy, count, can_place_in_reserves = bearer.has_redeploy()
        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 3)
        self.assertTrue(bool(can_place_in_reserves))

        specs = list(getattr(bearer, "special_rules", {}).get("enhancement_redeploy_specs", []) or [])
        matching = [
            spec
            for spec in specs
            if str(spec.get("source", "") or "").strip() == "Tremor Senses"
        ]
        self.assertEqual(len(matching), 1)
        spec = matching[0]
        self.assertIn("TYRANIDS", list(spec.get("filters", []) or []))
        self.assertTrue(bool(spec.get("strategic_reserves_ignore_current_unit_count_limit", False)))

    def test_vanguard_intellect_grants_turn_one_reserves_arrival_for_deep_strike(self):
        game, tyr_army, _enemy_army, _tyr_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Trygon",
            keywords=["TYRANIDS", "MONSTER", "TRYGON"],
            faction_keywords=["TYRANIDS"],
        )
        tyr_army.add_unit(bearer)
        _set_deployed(bearer, deployed=False, in_reserves=True)
        bearer._started_in_reserves = True
        bearer.has_deep_strike = lambda: True
        _apply_enhancement(bearer, enhancement_id="000010147004", enhancement_name="Vanguard Intellect")

        self.assertEqual(int(bearer._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(bool(bearer.can_arrive_from_reserves(1)))
        self.assertEqual(int(bearer.get_strategic_reserves_setup_turn(game=game, current_turn=1) or 0), 2)

        bearer.has_deep_strike = lambda: False
        self.assertEqual(int(bearer._strategic_reserves_round_bonus() or 0), 0)
        self.assertFalse(bool(bearer.can_arrive_from_reserves(1)))

    def test_trygon_prime_grants_synapse_and_bearer_melee_strength_and_weapon_skill_bonus(self):
        _game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Trygon",
            keywords=["TYRANIDS", "MONSTER", "TRYGON"],
            faction_keywords=["TYRANIDS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        tyr_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        _apply_enhancement(bearer_unit, enhancement_id="000010147005", enhancement_name="Trygon Prime")

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        self.assertTrue(bool(bearer_unit.has_any_keyword("SYNAPSE")))
        self.assertTrue(bool(bearer.has_any_keyword("SYNAPSE")))

        melee_profile = _make_melee_profile(skill="4+", strength="5")
        hit_preview = melee_profile._hit_target_with_tracking(enemy, bearer, {}, preview_modifiers=True)
        self.assertTrue(
            any(
                int(value) == 1 and "Trygon Prime" in str(reason or "")
                for value, reason in list(hit_preview.get("skill_mods", []) or [])
            )
        )

        wound_preview = melee_profile._wound_target_with_tracking(
            enemy,
            bearer,
            {"target_model": enemy.models[0]},
            roll_value=4,
        )
        self.assertTrue(
            any("Trygon Prime" in str(modifier or "") for modifier in list(wound_preview.get("modifiers", []) or []))
        )


if __name__ == "__main__":
    unittest.main()
