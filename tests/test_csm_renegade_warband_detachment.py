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
    unit.embarked_in = None
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
    army1 = Army("Chaos Space Marines", "Renegade Warband")
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


def _find_request(game: Game, ability_key: str, *, unit_id: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability_key):
            continue
        if unit_id is not None and str(ctx.get("unit_id", "") or "") != str(unit_id):
            continue
        return req
    return None


def _find_option(request, *, choice_key: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == str(choice_key).strip().upper():
            return opt
    return None


def _find_target_option(request, *, target_unit_id: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return opt
    return None


class TestCsmRenegadeWarbandDetachment(unittest.TestCase):
    def test_slaves_to_none_disables_dark_pacts_and_grants_assault(self):
        game, _p1, _p2, army1, army2 = _build_game()
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
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [legionaries, enemy]
        game.rebuild_entity_registry()

        legionaries.has_dark_pacts = lambda: True
        self.assertFalse(legionaries.can_use_dark_pacts())

        profile = _make_profile(weapon_type="ranged")
        self.assertTrue(legionaries.can_shoot_after_advance(profile))

    def test_vendetta_prompt_and_reroll_hit(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Legionaries",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        enemy_a = _make_unit(
            "Enemy A",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_b = _make_unit(
            "Enemy B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(attacker)
        army2.add_unit(enemy_a)
        army2.add_unit(enemy_b)
        game.map.units = [attacker, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        game._maybe_prompt_csm_vendetta()
        req = _find_request(game, "renegade_warband_vendetta_target")
        self.assertIsNotNone(req)

        enemy_a_id = str(get_entity_id(enemy_a) or "")
        option = _find_target_option(req, target_unit_id=enemy_a_id)
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        profile = _make_profile(weapon_type="ranged")
        hit_result = profile._hit_target_with_tracking(
            enemy_a,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        reasons = list(hit_result.get("reroll_full_reasons", []) or [])
        self.assertTrue(any("Vendetta" in str(reason) for reason in reasons))

    def test_twisted_doctrine_fall_back_mode_applies_after_decision(self):
        game, p1, _p2, army1, army2 = _build_game()
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
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [legionaries, enemy]
        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE

        test_calls: list[int] = []

        def _record_battleshock(turn: int = 0):
            test_calls.append(int(turn))

        legionaries.take_battle_shock_test = _record_battleshock

        game._on_unit_move_started_detachment_rules(unit=legionaries, action="fall_back")
        req = _find_request(
            game,
            "renegade_warband_twisted_doctrine",
            unit_id=str(get_entity_id(legionaries) or ""),
        )
        self.assertIsNotNone(req)
        self.assertEqual(len(list(req.options or [])), 3)

        option = _find_option(req, choice_key="FALL_BACK_SHOOT_AND_CHARGE")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertGreaterEqual(len(test_calls), 1)

        profile = _make_profile(weapon_type="ranged")
        self.assertTrue(legionaries.can_shoot_after_fall_back(profile))
        self.assertTrue(legionaries.can_charge_after_fall_back())

    def test_twisted_doctrine_set_up_trigger_can_grant_charge_after_advance(self):
        game, p1, _p2, army1, army2 = _build_game()
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
        army1.add_unit(legionaries)
        army2.add_unit(enemy)
        game.map.units = [legionaries, enemy]
        game.rebuild_entity_registry()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE

        legionaries.arrived_from_reserves_this_turn = True
        game._on_unit_set_up_csm_detachment_rules(
            unit=legionaries,
            set_up_as_reinforcements=True,
        )
        req = _find_request(
            game,
            "renegade_warband_twisted_doctrine",
            unit_id=str(get_entity_id(legionaries) or ""),
        )
        self.assertIsNotNone(req)

        option = _find_option(req, choice_key="ADVANCE_CHARGE")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, req, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(legionaries.can_charge_after_advance())


if __name__ == "__main__":
    unittest.main()
