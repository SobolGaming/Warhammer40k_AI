import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_ADAPTIVE_INSTINCTS
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["TYRANIDS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _adaptive_instincts_ability():
    return {
        "name": "Adaptive Instincts",
        "description": (
            "At the start of the Fight phase, select one of the following: "
            "- Aggression Imperative: Until the end of the phase, each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
            "- Bioregeneration: Until the end of the phase, each time a saving throw is made for a model in this unit, re-roll a saving throw of 1."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _build_game():
    tyr_army = Army("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    tyr_player = Player("Tyranids", PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[tyr_player, enemy_player])
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.current_player_idx = 0
    return game, tyr_army, enemy_army, tyr_player, enemy_player


class TestTyranidsAdaptiveInstincts(unittest.TestCase):
    def _resolve_choice(self, game, request, player, choice_key: str):
        option_id = None
        wanted = str(choice_key or "").strip().upper()
        for opt in list(request.options or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("choice", "") or "").strip().upper() == wanted:
                option_id = str(opt.option_id)
                break
        self.assertIsNotNone(option_id)
        command_result = resolve_decision_command(game, request, option_id, player_id=player.id)
        apply_result = getattr(command_result, "value", None)
        if apply_result is not None and hasattr(apply_result, "ok"):
            self.assertTrue(bool(apply_result.ok), msg=str(getattr(apply_result, "errors", ())))

    def test_fight_phase_queues_and_applies_aggression_imperative(self):
        game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
        warriors = _make_unit(
            "Tyranid Warriors with Melee Bio-weapons",
            abilities=[_adaptive_instincts_ability()],
            keywords=["INFANTRY", "SYNAPSE"],
            faction_keywords=["TYRANIDS"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        tyr_army.add_unit(warriors)
        enemy_army.add_unit(enemy)
        warriors.deployed = True
        enemy.deployed = True
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=tyr_player, phase=game.phase)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_ADAPTIVE_INSTINCTS
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("ability_name", "") or ""), "Adaptive Instincts")
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(warriors)))

        self._resolve_choice(game, request, tyr_player, "AGGRESSION")
        self.assertEqual(str(warriors.special_rules.get("adaptive_instincts_choice", "") or ""), "AGGRESSION")
        self.assertEqual(str(warriors.special_rules.get("adaptive_instincts_expires_phase", "") or ""), "FIGHT_PHASE")

        parent = SimpleNamespace(name="Bonesword", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 6])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _spec: next(rolls)
        try:
            result = profile._hit_target_with_tracking(enemy, warriors.models[0], {"_aura_attack_mods": _aura_stub()})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(result.get("roll", 0) or 0), 6)
        self.assertEqual(int(result.get("reroll_of_one", 0) or 0), 1)

    def test_bioregeneration_rerolls_save_of_one(self):
        game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
        warriors = _make_unit(
            "Tyranid Warriors with Melee Bio-weapons",
            abilities=[_adaptive_instincts_ability()],
            keywords=["INFANTRY", "SYNAPSE"],
            faction_keywords=["TYRANIDS"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        tyr_army.add_unit(warriors)
        enemy_army.add_unit(enemy)
        warriors.deployed = True
        enemy.deployed = True
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=tyr_player, phase=game.phase)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "")) == DECISION_CHOOSE_ADAPTIVE_INSTINCTS
        )
        self._resolve_choice(game, request, tyr_player, "BIOREGENERATION")
        self.assertEqual(str(warriors.special_rules.get("adaptive_instincts_choice", "") or ""), "BIOREGENERATION")

        parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        rolls = iter([1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _spec: next(rolls)
        try:
            save_result = profile._save_with_tracking(
                warriors.models[0],
                {
                    "attacker_model": enemy.models[0],
                    "attacker_unit": enemy,
                    "target_unit": warriors,
                    "_aura_attack_mods": _aura_stub(),
                },
                ap=0,
                log_roll=False,
            )
        finally:
            wargear_mod.get_roll = original_roll

        self.assertEqual(int(save_result.get("roll", 0) or 0), 5)
        self.assertEqual(int(save_result.get("reroll_of_one", 0) or 0), 1)
        self.assertTrue(
            any("Adaptive Instincts" in str(effect) for effect in list(save_result.get("special_effects", []) or []))
        )


if __name__ == "__main__":
    unittest.main()
