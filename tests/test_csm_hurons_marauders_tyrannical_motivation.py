from __future__ import annotations

import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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
    toughness: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


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
    army1 = Army("Chaos Space Marines", "Huron's Marauders")
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


def _find_request(game: Game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key):
            return req
    return None


def _find_option(request, *, choice_key: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == str(choice_key).strip().upper():
            return opt
    return None


class TestCsmHuronsMaraudersTyrannicalMotivation(unittest.TestCase):
    def test_command_phase_prompt_and_choice_resolution(self):
        game, p1, _p2, army1, army2 = _build_game()
        huron = _make_unit(
            "Huron Blackheart",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        legionaries = _make_unit(
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
        army1.add_unit(huron)
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [huron, legionaries, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_tyrannical_motivation()
        req = _find_request(game, "tyrannical_motivation_choice")
        self.assertIsNotNone(req)
        self.assertEqual(len(list(req.options or [])), 2)
        elite_option = _find_option(req, choice_key="HURONS_ELITE")
        self.assertIsNotNone(elite_option)

        result = resolve_decision_command(game, req, elite_option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        mgr = army1.chaos_space_marines_detachments
        self.assertEqual(str(getattr(mgr, "tyrannical_motivation_choice_key", "") or ""), "HURONS_ELITE")

    def test_hurons_elite_adds_hit_bonus_without_visibility(self):
        game, p1, _p2, army1, army2 = _build_game()
        huron = _make_unit(
            "Huron Blackheart",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        legionaries = _make_unit(
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
        army1.add_unit(huron)
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [huron, legionaries, enemy]
        game.rebuild_entity_registry()

        mgr = army1.chaos_space_marines_detachments
        selection = mgr.select_tyrannical_motivation_choice("HURONS_ELITE", game=game, player=p1)
        self.assertTrue(bool(selection.get("ok", False)))
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game._model_can_see_unit = lambda *_args, **_kwargs: False

        attacker_model = legionaries.models[0]
        profile = _make_profile(weapon_type="ranged", strength="4")
        hit_result = profile._hit_target_with_tracking(
            enemy,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Tyrannical Motivation" in m for m in list(hit_result.get("modifiers", []) or [])))

    def test_hurons_elite_visibility_gates_mobile_marauders_by_phase(self):
        game, p1, _p2, army1, army2 = _build_game()
        huron = _make_unit(
            "Huron Blackheart",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        legionaries = _make_unit(
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
        army1.add_unit(huron)
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [huron, legionaries, enemy]
        game.rebuild_entity_registry()

        mgr = army1.chaos_space_marines_detachments
        self.assertTrue(bool(mgr.select_tyrannical_motivation_choice("HURONS_ELITE", game=game, player=p1).get("ok", False)))
        legionaries.round_state.fell_back_this_round = True
        profile = _make_profile(weapon_type="ranged", strength="4")

        visible_state = {"visible": False}
        game._model_can_see_unit = lambda *_args, **_kwargs: bool(visible_state["visible"])

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        mgr.refresh_tyrannical_motivation_phase_state(game=game, force=True)
        self.assertFalse(mgr.tyrannical_motivation_can_shoot_after_fall_back(legionaries, profile=profile, game=game))

        game.phase = BattleRoundPhases.CHARGE_PHASE
        visible_state["visible"] = True
        mgr.refresh_tyrannical_motivation_phase_state(game=game, force=True)
        self.assertTrue(mgr.tyrannical_motivation_can_charge_after_fall_back(legionaries, game=game))
        self.assertTrue(legionaries.can_charge_after_fall_back())

    def test_mobile_marauders_visibility_grants_hurons_elite_hit_bonus(self):
        game, p1, _p2, army1, army2 = _build_game()
        huron = _make_unit(
            "Huron Blackheart",
            keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        legionaries = _make_unit(
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
        army1.add_unit(huron)
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [huron, legionaries, enemy]
        game.rebuild_entity_registry()

        mgr = army1.chaos_space_marines_detachments
        self.assertTrue(bool(mgr.select_tyrannical_motivation_choice("MOBILE_MARAUDERS", game=game, player=p1).get("ok", False)))
        attacker_model = legionaries.models[0]
        profile = _make_profile(weapon_type="ranged", strength="4")

        visible_state = {"visible": False}
        game._model_can_see_unit = lambda *_args, **_kwargs: bool(visible_state["visible"])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        mgr.refresh_tyrannical_motivation_phase_state(game=game, force=True)
        no_bonus_hit = profile._hit_target_with_tracking(
            enemy,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Tyrannical Motivation" in m for m in list(no_bonus_hit.get("modifiers", []) or [])))

        visible_state["visible"] = True
        game.phase = BattleRoundPhases.FIGHT_PHASE
        mgr.refresh_tyrannical_motivation_phase_state(game=game, force=True)
        with_bonus_hit = profile._hit_target_with_tracking(
            enemy,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Tyrannical Motivation" in m for m in list(with_bonus_hit.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
