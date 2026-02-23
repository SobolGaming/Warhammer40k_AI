import unittest

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HARBINGER
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _GameStub:
    def __init__(self, *, players, current_player, turn=1):
        self.is_authoritative = True
        self.turn = int(turn)
        self.players = list(players or [])
        self.decision_queue = DecisionQueue()
        self._current_player = current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_current_player(self):
        return self._current_player


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Chaos Knights", keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name="Chaos Knights", keywords=None, faction_keywords=None):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


class TestChaosKnightsTraitorisLance(unittest.TestCase):
    def _setup_armies(self, *, detachment_type: str):
        ck_army = Army("Chaos Knights", detachment_type=detachment_type)
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player

        enemy_army = Army("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player

        # Keep at least one Chaos Knights unit present for source checks in related systems.
        ck_army.add_unit(
            _make_unit(
                "Knight",
                keywords=["CHAOS KNIGHTS", "CHARACTER"],
                faction_keywords=["CHAOS KNIGHTS"],
            )
        )
        return ck_army, ck_player, enemy_army, enemy_player

    @staticmethod
    def _choose_first_non_random_option(request):
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if bool(payload.get("skip", False)):
                continue
            if bool(payload.get("random", False)):
                continue
            if str(payload.get("choice_key", "") or "").strip().upper() == "ROLL":
                continue
            return option
        return None

    def test_traitoris_lance_paragons_of_terror_queues_extra_dread_choice(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1)
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.harbingers_of_dread
        mgr.on_battle_round_start(1, game=game)

        base_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and not str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        ]
        self.assertTrue(base_requests)
        base_request = base_requests[-1]
        base_option = self._choose_first_non_random_option(base_request)
        self.assertIsNotNone(base_option)

        base_result = DecisionResult(
            decision_id=base_request.decision_id,
            player_id=ck_player.id,
            option_id=base_option.option_id,
            payload={},
        )
        apply_base = dispatch_decision(game, base_request, base_result)
        self.assertTrue(apply_base.ok)

        bonus_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_paragons_of_terror_bonus"
        ]
        self.assertTrue(bonus_requests)
        bonus_request = bonus_requests[-1]
        self.assertTrue(
            any(bool((getattr(opt, "payload", {}) or {}).get("skip", False)) for opt in list(bonus_request.options or []))
        )
        self.assertFalse(
            any(
                bool((getattr(opt, "payload", {}) or {}).get("random", False))
                or str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == "ROLL"
                for opt in list(bonus_request.options or [])
            )
        )

        bonus_option = self._choose_first_non_random_option(bonus_request)
        self.assertIsNotNone(bonus_option)
        bonus_payload = dict(getattr(bonus_option, "payload", {}) or {})
        bonus_key = str(bonus_payload.get("choice_key", "") or "").strip().upper()
        self.assertTrue(bool(bonus_key))

        bonus_result = DecisionResult(
            decision_id=bonus_request.decision_id,
            player_id=ck_player.id,
            option_id=bonus_option.option_id,
            payload={},
        )
        apply_bonus = dispatch_decision(game, bonus_request, bonus_result)
        self.assertTrue(apply_bonus.ok)

        ck_det_mgr = ck_army.chaos_knights_detachments
        self.assertEqual(int(getattr(ck_det_mgr, "_traitoris_paragons_bonus_round", 0) or 0), 1)
        self.assertIn(bonus_key, {str(key).upper() for key in list(mgr.active_dread_keys or [])})
        self.assertIsNone(
            ck_det_mgr.queue_traitoris_paragons_bonus_choice(
                battle_round=1,
                game=game,
                player=ck_player,
            )
        )

    def test_traitoris_lance_paragons_of_terror_skip_still_consumes_bonus(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1)
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.harbingers_of_dread
        mgr.on_battle_round_start(1, game=game)
        base_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and not str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        )
        base_option = self._choose_first_non_random_option(base_request)
        base_result = DecisionResult(
            decision_id=base_request.decision_id,
            player_id=ck_player.id,
            option_id=base_option.option_id,
            payload={},
        )
        self.assertTrue(dispatch_decision(game, base_request, base_result).ok)

        bonus_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_paragons_of_terror_bonus"
        )
        skip_option = next(
            opt
            for opt in list(bonus_request.options or [])
            if bool((getattr(opt, "payload", {}) or {}).get("skip", False))
        )
        skip_result = DecisionResult(
            decision_id=bonus_request.decision_id,
            player_id=ck_player.id,
            option_id=skip_option.option_id,
            payload={},
        )
        self.assertTrue(dispatch_decision(game, bonus_request, skip_result).ok)

        ck_det_mgr = ck_army.chaos_knights_detachments
        self.assertEqual(int(getattr(ck_det_mgr, "_traitoris_paragons_bonus_round", 0) or 0), 1)
        self.assertIsNone(
            ck_det_mgr.queue_traitoris_paragons_bonus_choice(
                battle_round=1,
                game=game,
                player=ck_player,
            )
        )

    def test_non_traitoris_detachment_does_not_queue_paragons_bonus_choice(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Infernal Lance")
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1)
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.harbingers_of_dread
        mgr.on_battle_round_start(1, game=game)
        base_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and not str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        )
        base_option = self._choose_first_non_random_option(base_request)
        result = DecisionResult(
            decision_id=base_request.decision_id,
            player_id=ck_player.id,
            option_id=base_option.option_id,
            payload={},
        )
        self.assertTrue(dispatch_decision(game, base_request, result).ok)

        bonus_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_paragons_of_terror_bonus"
        ]
        self.assertFalse(bonus_requests)


if __name__ == "__main__":
    unittest.main()
