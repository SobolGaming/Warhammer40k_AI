import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Grey Knights",
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["GREY KNIGHTS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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


def _make_unit(name: str, *, faction_name: str = "Grey Knights", keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    gk_army = Army.with_detachment("Grey Knights", "Hallowed Conclave")
    gk_army.faction_id = "GK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gk_player = Player("GK", control=PlayerControl.REMOTE, army=gk_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gk_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gk_army, enemy_army, gk_player, enemy_player


def _apply_enhancement(
    unit: Unit,
    *,
    enhancement_id: str = "000010352002",
    enhancement_name: str = "Eye of the Augurium",
) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="GK",
        detachment="Hallowed Conclave",
        points=15,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _overwatch_stratagem() -> Stratagem:
    return Stratagem(
        id="core_overwatch",
        name="Fire Overwatch",
        type="Core",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Movement phase, Charge phase",
        detachment="",
        faction_id="",
    )


def _heroic_intervention_stratagem() -> Stratagem:
    return Stratagem(
        id="core_heroic_intervention",
        name="Heroic Intervention",
        type="Core",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Charge phase",
        detachment="",
        faction_id="",
    )


class TestGreyKnightsHallowedConclaveEnhancements(unittest.TestCase):
    def test_descriptors_registered(self):
        expected = {
            "000010352002": (
                "Eye of the Augurium",
                "stratagem_cp_cost_set_zero_with_repeat_exception",
            ),
            "000010352003": (
                "Inescapable Judgement (Psychic)",
                "optional_enemy_fall_back_mortal_wound_table",
            ),
            "000010352004": ("Sanctic Reaper", "bearer_melee_attacks_bonus"),
            "000010352005": ("Nemesis Rounds", "fire_overwatch_hit_threshold"),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_eye_of_the_augurium_descriptor_and_apply_registration(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010352002")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Eye of the Augurium")
        self.assertEqual(
            tuple(getattr(desc, "effect_params", {}).get("stratagems", ()) or ()),
            ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
        )
        by_name = get_enhancement_tool_descriptor(name="Eye of the Augurium")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "enhancement_id", "") or ""), "000010352002")

        _game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        _apply_enhancement(bearer)

        sr = dict(getattr(bearer, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_eye_of_the_augurium", False)))
        self.assertEqual(
            tuple(sr.get("enhancement_eye_of_the_augurium_stratagems", ()) or ()),
            ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"),
        )
        self.assertEqual(str(sr.get("enhancement_eye_of_the_augurium_limit", "") or ""), "battle_round")
        rule = bearer.get_eye_of_the_augurium_stratagem_rule()
        self.assertIsInstance(rule, dict)
        self.assertEqual(str((rule or {}).get("source", "") or ""), "Eye of the Augurium")

    def test_eye_of_the_augurium_allows_fire_overwatch_repeat_for_zero_cp_once_per_battle_round(self):
        game, gk_army, _enemy_army, gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        _apply_enhancement(bearer)

        stratagem = _overwatch_stratagem()
        gk_player.stratagems._used_this_turn["OVERWATCH"] = True

        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        first = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertFalse(bool(first.get("denied", False)))
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "1")

        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        second = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertTrue(bool(second.get("denied", False)))
        self.assertIn("already used this turn", str(second.get("reason", "") or "").lower())

        game.turn = 2
        gk_player.stratagems._used_this_turn["OVERWATCH"] = True
        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        third = gk_player.apply_stratagem_cp_cost(stratagem, target_unit=bearer)
        self.assertFalse(bool(third.get("denied", False)))
        self.assertEqual(int(third.get("cost", -1)), 0)
        self.assertTrue(bool(third.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "2")

    def test_eye_of_the_augurium_allows_heroic_intervention_repeat_for_zero_cp(self):
        game, gk_army, _enemy_army, gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        other = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        gk_army.add_unit(other)
        _apply_enhancement(bearer)

        manager = gk_player.stratagems
        manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
        manager._record_heroic_intervention_use(other)
        self.assertTrue(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))
        self.assertFalse(bool(manager._heroic_intervention_repeat_allowed(target_unit=other)))

        heroic = _heroic_intervention_stratagem()
        gk_player.set_next_optional_decision("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", True)
        applied = gk_player.apply_stratagem_cp_cost(heroic, target_unit=bearer)
        self.assertFalse(bool(applied.get("denied", False)))
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertTrue(bool(applied.get("eye_of_the_augurium_use", False)))
        self.assertEqual(str(bearer.special_rules.get("eye_of_the_augurium_used_battle_round", "") or ""), "1")
        self.assertFalse(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))

        game.turn = 2
        self.assertTrue(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))

    def test_sanctic_reaper_sets_bearer_melee_attacks_bonus(self):
        _game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brother-captain",
            keywords=["INFANTRY", "CHARACTER", "TERMINATOR"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(bearer)
        _apply_enhancement(
            bearer,
            enhancement_id="000010352004",
            enhancement_name="Sanctic Reaper",
        )

        sr = dict(getattr(bearer, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_sanctic_reaper", False)))
        self.assertEqual(int(sr.get("enhancement_sanctic_reaper_melee_attacks_bonus", 0) or 0), 3)
        self.assertEqual(int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0), 3)

    def test_nemesis_rounds_sets_overwatch_hit_threshold_to_five(self):
        game, gk_army, enemy_army, _gk_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Brother-captain",
            keywords=["INFANTRY", "CHARACTER", "TERMINATOR"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(bearer)
        enemy_army.add_unit(enemy)
        _apply_enhancement(
            bearer,
            enhancement_id="000010352005",
            enhancement_name="Nemesis Rounds",
        )

        sr = dict(getattr(bearer, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_nemesis_rounds", False)))
        self.assertEqual(int(sr.get("enhancement_nemesis_rounds_overwatch_hit_threshold", 0) or 0), 5)
        self.assertEqual(int(bearer.get_nemesis_rounds_overwatch_hit_threshold(enemy_unit=enemy, game=game) or 0), 5)

    @patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6, 5])
    def test_inescapable_judgement_queues_and_applies_fall_back_mortal_wounds(self, mocked_roll):
        game, gk_army, enemy_army, gk_player, _enemy_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(enemy)
        game.rebuild_entity_registry()
        _apply_enhancement(
            source,
            enhancement_id="000010352003",
            enhancement_name="Inescapable Judgement (Psychic)",
        )
        for model in list(getattr(source, "models", []) or []):
            model.set_location(20.0, 20.0, 0.0, 0.0)
        for model in list(getattr(enemy, "models", []) or []):
            model.set_location(21.5, 20.0, 0.0, 0.0)
        self.assertTrue(bool(game.map.place_unit(source)))
        self.assertTrue(bool(game.map.place_unit(enemy)))

        enemy.round_state.fell_back_this_round = True
        game.current_player_index = 1
        game._on_unit_move_started_detachment_rules(unit=enemy, action="fall_back")
        game._on_unit_move_ended_detachment_rules(unit=enemy, action="fall_back")

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str(getattr(req, "context", {}).get("ability", "") or "") == "grey_knights_hallowed_inescapable_judgement"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(getattr(request, "player_id", "") or ""), str(gk_player.id))

        enemy_id = str(get_entity_id(enemy) or "")
        use_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str(getattr(opt, "payload", {}).get("target_unit_id", "") or "") == enemy_id
        )
        resolve_decision_command(game, request, use_option.option_id, player_id=gk_player.id)
        self.assertEqual(mocked_roll.call_count, 2)
        self.assertLess(sum(int(getattr(model, "wounds", 0) or 0) for model in enemy.models), 4)


if __name__ == "__main__":
    unittest.main()
