import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HARBINGER, DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.units.unit import Unit


class _GameStub:
    def __init__(self, *, players, current_player, turn=1, game_map=None):
        self.is_authoritative = True
        self.turn = int(turn)
        self.players = list(players or [])
        self.decision_queue = DecisionQueue()
        self._current_player = current_player
        self.map = game_map
        self.objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_current_player(self):
        return self._current_player


class _ObjectivePointStub:
    def __init__(self, x: float, y: float, *, controlling_player=None):
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0
        self.control_radius = 3.0
        self.removed = False
        self.controlling_player = controlling_player
        self.sticky_controller = None
        self.sticky_source = None

    def set_sticky_control(self, player, source: str | None = None) -> None:
        self.sticky_controller = player
        self.sticky_source = source
        self.controlling_player = player


class _ObjectiveStub:
    def __init__(self, objective_id: str, *, x: float, y: float, controlling_player=None):
        self._id = str(objective_id)
        self.id = str(objective_id)
        self.name = f"Objective {objective_id}"
        self.location = _ObjectivePointStub(x, y, controlling_player=controlling_player)


class _MapStub:
    def __init__(self, *, units=None, objectives=None):
        self.units = list(units or [])
        self.objectives = list(objectives or [])

    def get_enemy_units(self, unit):
        if unit is None:
            return []
        unit_army = getattr(unit, "get_parent_army", lambda: None)()
        out = []
        for other in list(self.units or []):
            if other is None:
                continue
            other_army = getattr(other, "get_parent_army", lambda: None)()
            if other_army is unit_army:
                continue
            out.append(other)
        return out


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

    @staticmethod
    def _choose_roll_option(request):
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if bool(payload.get("random", False)):
                return option
            if str(payload.get("choice_key", "") or "").strip().upper() == "ROLL":
                return option
        return None

    @staticmethod
    def _apply_enhancement(unit, *, enhancement_id: str, enhancement_name: str):
        unit._get_enhancement_bearer_model = lambda: unit.models[0]
        enhancement = Enhancement(
            id=str(enhancement_id),
            name=str(enhancement_name),
            faction_id="QT",
            detachment="Traitoris Lance",
            description="",
        )
        unit.enhancement = enhancement
        enhancement.apply_to_unit(unit)
        return enhancement

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

    def test_traitoris_enhancement_descriptors_exist(self):
        expected = {
            "000008516002": ("Nightmare's Master", "force_battleshock_for_enemy_units_within_bearer_engagement_range"),
            "000008516003": ("Tyrant's Shadow", "objective_marker_sticky_control_and_harbingers_deathly_terror"),
            "000008516004": ("Malevolent Heraldry", "optional_reroll_one_or_both_harbingers_dice"),
            "000008516005": ("Veil of Medrengard", "bearer_attack_type_specific_invulnerable_save"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_malevolent_heraldry_queues_reroll_before_random_harbingers_are_applied(self):
        ck_army, ck_player, _enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        source_unit = ck_army.units[0]
        self._apply_enhancement(
            source_unit,
            enhancement_id="000008516004",
            enhancement_name="Malevolent Heraldry",
        )

        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1)
        ck_player.game = game
        enemy_player.game = game

        with patch("warhammer40k_ai.rules.harbingers_of_dread.get_roll", side_effect=[2, 3]):
            ck_army.harbingers_of_dread.on_battle_round_start(1, game=game)

        base_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and not str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        )
        roll_option = self._choose_roll_option(base_request)
        self.assertIsNotNone(roll_option)
        base_result = DecisionResult(
            decision_id=base_request.decision_id,
            player_id=ck_player.id,
            option_id=roll_option.option_id,
            payload={},
        )
        self.assertTrue(dispatch_decision(game, base_request, base_result).ok)

        # Random Harbingers results are deferred until Malevolent Heraldry resolves.
        self.assertEqual(
            {str(v).upper() for v in list(ck_army.harbingers_of_dread.active_dread_keys or [])},
            {"DEATHLY_TERROR"},
        )

        reroll_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_malevolent_heraldry"
        )
        reroll_option = next(
            opt
            for opt in list(reroll_request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("reroll_mode", "") or "") == "reroll_both"
        )
        reroll_result = DecisionResult(
            decision_id=reroll_request.decision_id,
            player_id=ck_player.id,
            option_id=reroll_option.option_id,
            payload={},
        )
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", side_effect=[5, 6]):
            self.assertTrue(dispatch_decision(game, reroll_request, reroll_result).ok)

        active = {str(v).upper() for v in list(ck_army.harbingers_of_dread.active_dread_keys or [])}
        self.assertIn("DELIRIUM", active)
        self.assertIn("DOMINION", active)
        self.assertNotIn("DOOM", active)
        self.assertNotIn("DARKNESS", active)

        bonus_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_HARBINGER
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_paragons_of_terror_bonus"
        ]
        self.assertTrue(bonus_requests)

    def test_tyrants_shadow_selects_objective_and_objective_projects_deathly_terror(self):
        from warhammer40k_ai.rules.harbingers_of_dread import DEATHLY_TERROR

        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        source_unit = ck_army.units[0]
        self._apply_enhancement(
            source_unit,
            enhancement_id="000008516003",
            enhancement_name="Tyrant's Shadow",
        )
        source_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)

        enemy_unit = _make_unit(
            "Enemy Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_army.add_unit(enemy_unit)
        enemy_unit.models[0].set_location(1.0, 0.0, 0.0, 0.0)

        objective = _ObjectiveStub("obj-a", x=0.0, y=0.0, controlling_player=ck_player)
        game_map = _MapStub(units=[source_unit, enemy_unit], objectives=[objective])
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1, game_map=game_map)
        ck_player.game = game
        enemy_player.game = game

        ck_army.chaos_knights_detachments.on_command_phase_end(game=game, player=ck_player)

        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "traitoris_tyrants_shadow_objective"
        )
        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "") == "obj-a"
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )
        self.assertTrue(dispatch_decision(game, request, result).ok)
        self.assertIs(objective.location.sticky_controller, ck_player)
        self.assertEqual(str(objective.location.sticky_source or ""), "traitoris_tyrants_shadow")

        # Move the source unit away to prove the objective itself projects the aura.
        source_unit.models[0].set_location(30.0, 30.0, 0.0, 0.0)
        auras_near = ck_army.harbingers_of_dread.leadership_auras_for_unit(enemy_unit, game_map=game_map)
        self.assertIn(DEATHLY_TERROR.key, auras_near)

        enemy_unit.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        auras_far = ck_army.harbingers_of_dread.leadership_auras_for_unit(enemy_unit, game_map=game_map)
        self.assertNotIn(DEATHLY_TERROR.key, auras_far)

    def test_nightmares_master_adds_start_of_fight_engagement_battleshock_spec_for_bearer(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        source_unit = ck_army.units[0]
        self._apply_enhancement(
            source_unit,
            enhancement_id="000008516002",
            enhancement_name="Nightmare's Master",
        )
        bearer = source_unit.models[0]

        specs = list(source_unit.model_start_fight_phase_engagement_battleshock_specs(bearer) or [])
        self.assertTrue(any(str(spec.get("source", "") or "") == "Nightmare's Master" for spec in specs))

    def test_veil_of_medrengard_applies_attack_type_specific_invulnerable_save(self):
        ck_army, _ck_player, enemy_army, _enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        target_unit = ck_army.units[0]
        self._apply_enhancement(
            target_unit,
            enhancement_id="000008516005",
            enhancement_name="Veil of Medrengard",
        )
        target_model = target_unit.models[0]
        target_model._inv_save = 0
        target_model._inv_save_condition = ""

        attacker_unit = _make_unit(
            "Enemy Attacker",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_army.add_unit(attacker_unit)
        attacker_model = attacker_unit.models[0]

        ranged_weapon = Wargear(
            {
                "name": "Test Ranged",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-1",
                "D": "1",
                "description": "",
            }
        )
        melee_weapon = Wargear(
            {
                "name": "Test Melee",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-1",
                "D": "1",
                "description": "",
            }
        )
        ranged_profile = next(iter(ranged_weapon.profiles.values()))
        melee_profile = next(iter(melee_weapon.profiles.values()))

        ranged_result = ranged_profile._save_with_tracking(
            target_model,
            {"attacker_model": attacker_model, "attacker_unit": attacker_unit, "target_unit": target_unit},
            ap=-3,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        melee_result = melee_profile._save_with_tracking(
            target_model,
            {"attacker_model": attacker_model, "attacker_unit": attacker_unit, "target_unit": target_unit},
            ap=-3,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertEqual(int(ranged_result.get("final_save", 0) or 0), 4)
        self.assertEqual(str(ranged_result.get("save_type", "") or ""), "invulnerable")
        self.assertEqual(int(melee_result.get("final_save", 0) or 0), 5)
        self.assertEqual(str(melee_result.get("save_type", "") or ""), "invulnerable")


if __name__ == "__main__":
    unittest.main()
