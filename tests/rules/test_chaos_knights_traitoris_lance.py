import unittest
from math import sqrt
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HARBINGER, DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.utility.aura_effects import get_aura_objective_control_bonus
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.units.unit import Unit


class _RegistryStub:
    def __init__(self, units, players):
        self._units = {str(getattr(unit, "_id", "") or ""): unit for unit in list(units or []) if unit is not None}
        self._players = {str(getattr(player, "id", "") or ""): player for player in list(players or []) if player is not None}
        self._models = {}
        for unit in list(units or []):
            if unit is None:
                continue
            for model in list(getattr(unit, "models", []) or []) + list(getattr(unit, "models_lost", []) or []):
                model_id = str(get_entity_id(model) or "")
                if model_id:
                    self._models[model_id] = model

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id or ""))
        if kind == "player":
            return self._players.get(str(entity_id or ""))
        if kind == "model":
            return self._models.get(str(entity_id or ""))
        return None


class _GameStub:
    def __init__(self, *, players, current_player, turn=1, game_map=None, phase_name="COMMAND_PHASE"):
        self.is_authoritative = True
        self.turn = int(turn)
        self.phase = SimpleNamespace(name=str(phase_name or "COMMAND_PHASE"))
        self.players = list(players or [])
        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self._current_player = current_player
        self.map = game_map
        self.objectives = list(getattr(game_map, "objectives", []) or []) if game_map is not None else []
        units = list(getattr(game_map, "units", []) or []) if game_map is not None else []
        self.entity_registry = _RegistryStub(units, self.players)

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_current_player(self):
        return self._current_player

    def get_enemy_units(self, player):
        player_id = str(getattr(player, "id", "") or "")
        enemies = []
        for unit in list(getattr(self.map, "units", []) or []):
            if unit is None:
                continue
            army = getattr(unit, "get_parent_army", lambda: None)()
            owner = getattr(army, "player", None)
            if owner is None or str(getattr(owner, "id", "") or "") == player_id:
                continue
            enemies.append(unit)
        return enemies

    def rebuild_entity_registry(self):
        units = []
        for player in list(self.players or []):
            army = getattr(player, "army", None)
            units.extend(list(getattr(army, "units", []) or []))
        self.entity_registry = _RegistryStub(units, self.players)
        if hasattr(self.map, "units"):
            self.map.units = list(units)


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
        self.terrain_features = []

    def get_friendly_units(self, unit):
        if unit is None:
            return []
        unit_army = getattr(unit, "get_parent_army", lambda: None)()
        return [
            other
            for other in list(self.units or [])
            if other is not None and getattr(other, "get_parent_army", lambda: None)() is unit_army
        ]

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

    def get_distance_between_units(self, unit_a, unit_b):
        return _unit_distance(unit_a, unit_b)

    def is_within_engagement_range(self, unit_a, unit_b):
        distance = self.get_distance_between_units(unit_a, unit_b)
        return distance is not None and float(distance) <= 1.0 + 1e-6


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


def _set_unit_position(unit, x: float, y: float, z: float = 0.0):
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), float(z), 0.0)


def _unit_distance(unit_a, unit_b):
    if unit_a is None or unit_b is None:
        return None
    try:
        model_a = next(iter(list(getattr(unit_a, "models", []) or [])), None)
        model_b = next(iter(list(getattr(unit_b, "models", []) or [])), None)
        if model_a is None or model_b is None:
            return None
        loc_a = model_a.get_location()
        loc_b = model_b.get_location()
        if not loc_a or not loc_b:
            return None
        return sqrt(
            (float(loc_a[0]) - float(loc_b[0])) ** 2
            + (float(loc_a[1]) - float(loc_b[1])) ** 2
            + (float(loc_a[2]) - float(loc_b[2])) ** 2
        )
    except Exception:
        return None


class TestChaosKnightsTraitorisLance(unittest.TestCase):
    def _setup_armies(self, *, detachment_type: str):
        ck_army = Army.with_detachment("Chaos Knights", detachment_type=detachment_type)
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player
        ck_player.command_points = 6

        enemy_army = Army.with_detachment("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        enemy_player.command_points = 0

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
    def _make_chaos_knight(name: str, *, war_dog: bool = False, abhorrent: bool = False, titanic: bool = False):
        keywords = ["CHAOS KNIGHTS"]
        if war_dog:
            keywords.append("WAR DOG")
        if abhorrent:
            keywords.append("ABHORRENT")
        if titanic:
            keywords.append("TITANIC")
        return _make_unit(
            name,
            faction_name="Chaos Knights",
            keywords=keywords,
            faction_keywords=["CHAOS KNIGHTS"],
        )

    @staticmethod
    def _set_game(game, *players):
        for player in players:
            player.set_game(game)

    @staticmethod
    def _set_phase(game, current_player, phase_name: str):
        game.phase = SimpleNamespace(name=str(phase_name or "COMMAND_PHASE"))
        game._current_player = current_player
        label_map = {
            "COMMAND_PHASE": "Command phase",
            "MOVEMENT_PHASE": "Movement phase",
            "SHOOTING_PHASE": "Shooting phase",
            "CHARGE_PHASE": "Charge phase",
            "FIGHT_PHASE": "Fight phase",
        }
        label = label_map.get(str(phase_name or "").strip().upper(), str(phase_name or "").replace("_", " ").title())
        for player in list(getattr(game, "players", []) or []):
            mgr = getattr(player, "stratagems", None)
            if mgr is not None:
                mgr._current_phase_name = label

    @staticmethod
    def _refresh_game(game):
        if hasattr(game, "rebuild_entity_registry"):
            game.rebuild_entity_registry()

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
    def _is_base_harbingers_request(request) -> bool:
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_HARBINGER:
            return False
        context = getattr(request, "context", {}) or {}
        return str(context.get("ability", "") or "") == "harbingers_of_dread"

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
            if self._is_base_harbingers_request(req)
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
            if self._is_base_harbingers_request(req)
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
            if self._is_base_harbingers_request(req)
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
            if self._is_base_harbingers_request(req)
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

    def test_traitoris_stratagem_descriptors_exist(self):
        expected = {
            "000008517002": ("Pterrorshades", "roll_six_d6_for_mortals_and_self_heal"),
            "000008517003": ("Conquerors Without Mercy", "melee_ap_bonus_with_post_fight_battleshock_aura"),
            "000008517004": ("Disdain for the Weak", "conditional_feel_no_pain"),
            "000008517005": ("A Long Leash", "war_dogs_count_within_source_auras"),
            "000008517006": ("Imperious Advance", "phase_move_passthrough_and_desperate_escape_auto_pass"),
            "000008517007": ("Storm of Darkness", "stealth_and_benefit_of_cover"),
        }
        for stratagem_id, (name, effect) in expected.items():
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_a_long_leash_treats_selected_war_dog_as_within_abhorrent_aura(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        abhorrent = self._make_chaos_knight("Knight Abominant", abhorrent=True, titanic=True)
        war_dog = self._make_chaos_knight("War Dog Karnivore", war_dog=True)
        ck_army.add_unit(abhorrent)
        ck_army.add_unit(war_dog)
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(enemy)

        aura = Ability(
            name="Dread Dominion (Aura)",
            faction_id="QT",
            description=(
                "While a friendly War Dog model is within 9\" of this model, "
                "improve that WAR DOG model's Leadership and Objective Control characteristics by 1."
            ),
            type="Datasheet",
            parameter="",
            legend=None,
        )
        abhorrent.possible_abilities = [aura]
        _set_unit_position(abhorrent, 0.0, 0.0)
        _set_unit_position(war_dog, 30.0, 0.0)
        _set_unit_position(enemy, 40.0, 0.0)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1, game_map=game_map)
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, ck_player, "COMMAND_PHASE")

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=False):
            before = get_aura_objective_control_bonus(war_dog, game_map=game_map)
            ok = ck_player.stratagems.use(
                "A LONG LEASH",
                unit=abhorrent,
                target_unit=abhorrent,
                selected_units=[war_dog],
                phase_name="Command phase",
            )
            after = get_aura_objective_control_bonus(war_dog, game_map=game_map)
            self.assertFalse(before)
            self.assertTrue(ok)
            self.assertEqual(int(after or 0), 1)

            game.event_system.publish("phase_start", player=ck_player, phase=game.phase)
            cleared = get_aura_objective_control_bonus(war_dog, game_map=game_map)
            self.assertEqual(int(cleared or 0), 0)

    def test_imperious_advance_movement_phase_applies_move_passthrough_and_cleans_up(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        war_dog_a = self._make_chaos_knight("War Dog Brigand A", war_dog=True)
        war_dog_b = self._make_chaos_knight("War Dog Brigand B", war_dog=True)
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(war_dog_a)
        ck_army.add_unit(war_dog_b)
        enemy_army.add_unit(enemy)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1, game_map=game_map)
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, ck_player, "MOVEMENT_PHASE")

        ok = ck_player.stratagems.use(
            "IMPERIOUS ADVANCE",
            selected_units=[war_dog_a, war_dog_b],
            phase_name="Movement phase",
        )
        self.assertTrue(ok)

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=war_dog_a)
        fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=war_dog_a)
        self.assertTrue(bool(move_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(move_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(move_rules.get("cannot_move_within_engagement_range", True)))
        self.assertTrue(bool(move_rules.get("cannot_end_in_engagement_range")))
        self.assertFalse(bool(fall_back_rules.get("check_desperate_escape", True)))

        game.event_system.publish("phase_end", player=ck_player, phase=game.phase)
        sr_after = dict(getattr(war_dog_a, "special_rules", {}) or {})
        self.assertFalse(bool(sr_after.get("traitoris_imperious_advance_active", False)))
        self.assertNotIn("bearer_unit_phase_move_types", sr_after)

    def test_imperious_advance_charge_phase_suspends_titanic_block_and_restores_it(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        titanic = self._make_chaos_knight("Knight Tyrant", titanic=True)
        titanic.special_rules = {"titanic_phase_move_block_titanic_types": ["charge"]}
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(titanic)
        enemy_army.add_unit(enemy)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(players=[ck_player, enemy_player], current_player=ck_player, turn=1, game_map=game_map)
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, ck_player, "CHARGE_PHASE")

        ok = ck_player.stratagems.use(
            "IMPERIOUS ADVANCE",
            selected_units=[titanic],
            phase_name="Charge phase",
        )
        self.assertTrue(ok)

        charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=titanic)
        self.assertTrue(bool(charge_rules.get("can_move_through_enemy_models")))
        self.assertTrue(bool(charge_rules.get("can_move_through_terrain")))
        self.assertFalse(bool(charge_rules.get("block_titanic_models", False)))

        game.event_system.publish("phase_end", player=ck_player, phase=game.phase)
        sr_after = dict(getattr(titanic, "special_rules", {}) or {})
        self.assertEqual(list(sr_after.get("titanic_phase_move_block_titanic_types", []) or []), ["charge"])

    def test_storm_of_darkness_grants_stealth_and_cover(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        target = self._make_chaos_knight("War Dog Stalker", war_dog=True)
        attacker = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(target)
        enemy_army.add_unit(attacker)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(
            players=[ck_player, enemy_player],
            current_player=enemy_player,
            turn=1,
            game_map=game_map,
            phase_name="SHOOTING_PHASE",
        )
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, enemy_player, "SHOOTING_PHASE")

        ranged_profile = next(
            iter(
                Wargear(
                    {
                        "name": "Enemy Gun",
                        "type": "Ranged",
                        "range": "24",
                        "A": "1",
                        "BS_WS": "3+",
                        "S": "4",
                        "AP": "-1",
                        "D": "1",
                        "description": "",
                    }
                ).profiles.values()
            )
        )
        baseline_result = ranged_profile._save_with_tracking(
            target.models[0],
            {
                "attacker_model": attacker.models[0],
                "attacker_unit": attacker,
                "target_unit": target,
            },
            ap=-1,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )

        ok = ck_player.stratagems.use(
            "STORM OF DARKNESS",
            unit=target,
            target_unit=target,
            attacking_unit=attacker,
            enemy_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        self.assertTrue(bool(target.has_stealth()))

        attack_instance = {
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
            "target_unit": target,
        }
        save_result = ranged_profile._save_with_tracking(
            target.models[0],
            attack_instance,
            ap=-1,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(attack_instance.get("benefit_of_cover", False)))
        self.assertIn("STORM OF DARKNESS", str(attack_instance.get("benefit_of_cover_source", "") or ""))
        self.assertFalse(bool(baseline_result.get("saved", False)))
        self.assertTrue(bool(save_result.get("saved", False)))

        game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
        self.assertFalse(bool(target.has_stealth()))

    def test_disdain_for_the_weak_uses_battleshock_condition_for_better_fnp(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        defender = self._make_chaos_knight("War Dog Defender", war_dog=True)
        attacker = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(defender)
        enemy_army.add_unit(attacker)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(
            players=[ck_player, enemy_player],
            current_player=enemy_player,
            turn=1,
            game_map=game_map,
            phase_name="FIGHT_PHASE",
        )
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, enemy_player, "FIGHT_PHASE")

        ok = ck_player.stratagems.use(
            "DISDAIN FOR THE WEAK",
            unit=defender,
            target_unit=defender,
            attacking_unit=attacker,
            enemy_unit=attacker,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)

        melee_profile = next(
            iter(
                Wargear(
                    {
                        "name": "Enemy Blade",
                        "type": "Melee",
                        "range": "Melee",
                        "A": "1",
                        "BS_WS": "3+",
                        "S": "4",
                        "AP": "-1",
                        "D": "1",
                        "description": "",
                    }
                ).profiles.values()
            )
        )
        attacker_model = attacker.models[0]
        attack_instance = {
            "damage_characteristic": 1,
            "attacker_model": attacker_model,
            "attacker_unit": attacker,
            "target_unit": defender,
        }

        attacker.battle_shocked = False
        attacker.is_battle_shocked = lambda: False
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
            normal_result = melee_profile._apply_damage_with_tracking(
                defender.models[0],
                attacker_model,
                1,
                False,
                attack_instance=dict(attack_instance),
                game_map=game_map,
            )

        attacker.battle_shocked = True
        attacker.is_battle_shocked = lambda: True
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
            battle_shocked_result = melee_profile._apply_damage_with_tracking(
                defender.models[0],
                attacker_model,
                1,
                False,
                attack_instance=dict(attack_instance),
                game_map=game_map,
            )

        self.assertEqual(int(normal_result.get("fnp_saves", 0) or 0), 0)
        self.assertEqual(int(battle_shocked_result.get("fnp_saves", 0) or 0), 1)

    def test_pterrorshades_queues_after_failed_battleshock_and_heals_per_success(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        source = self._make_chaos_knight("War Dog Executioner", war_dog=True)
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 6.0, 0.0)
        source.models[0].wounds = int(source.models[0]._base_wounds) - 3

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(
            players=[ck_player, enemy_player],
            current_player=enemy_player,
            turn=1,
            game_map=game_map,
            phase_name="FIGHT_PHASE",
        )
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, enemy_player, "FIGHT_PHASE")

        self.assertFalse(
            ck_player.stratagems.can_use(
                "PTERRORSHADES",
                unit=source,
                target_unit=source,
                phase_name="Fight phase",
            )
        )
        game.event_system.publish("battle_shock_test_resolved", unit=enemy, passed=False)
        pending = [
            reaction
            for reaction in list(getattr(ck_player.stratagems, "_pending_reactions", []) or [])
            if str(reaction.get("stratagem", "") or "").upper() == "PTERRORSHADES"
        ]
        self.assertTrue(pending)

        mortal_wounds = []
        source._apply_mortal_wounds_to_unit = lambda target, amount, game_map=None: mortal_wounds.append(int(amount))
        self.assertTrue(
            ck_player.stratagems.can_use(
                "PTERRORSHADES",
                unit=source,
                target_unit=source,
                enemy_unit=enemy,
                phase_name="Fight phase",
            )
        )
        with patch("warhammer40k_ai.rules.stratagems_chaos_knights.get_roll", side_effect=[4, 1, 6, 2, 5, 3]):
            ok = ck_player.stratagems.use(
                "PTERRORSHADES",
                unit=source,
                target_unit=source,
                enemy_unit=enemy,
                phase_name="Fight phase",
                dequeue=True,
            )

        self.assertTrue(ok)
        self.assertEqual(mortal_wounds, [3])
        self.assertEqual(int(source.models[0].wounds or 0), int(source.models[0]._base_wounds or 0))

    def test_conquerors_without_mercy_applies_ap_bonus_and_post_fight_battleshock(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_armies(detachment_type="Traitoris Lance")
        attacker = self._make_chaos_knight("War Dog Huntsman", war_dog=True)
        enemy_destroyed = _make_unit(
            "Destroyed Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_near = _make_unit("Nearby Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_far = _make_unit("Far Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(attacker)
        enemy_army.add_unit(enemy_destroyed)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        attacker.round_state.charged_this_round = True
        _set_unit_position(attacker, 0.0, 0.0)
        _set_unit_position(enemy_destroyed, 1.0, 0.0)
        _set_unit_position(enemy_near, 5.0, 0.0)
        _set_unit_position(enemy_far, 9.0, 0.0)

        game_map = _MapStub(units=list(ck_army.units) + list(enemy_army.units))
        game = _GameStub(
            players=[ck_player, enemy_player],
            current_player=ck_player,
            turn=1,
            game_map=game_map,
            phase_name="FIGHT_PHASE",
        )
        self._set_game(game, ck_player, enemy_player)
        self._refresh_game(game)
        self._set_phase(game, ck_player, "FIGHT_PHASE")

        ok = ck_player.stratagems.use(
            "CONQUERORS WITHOUT MERCY",
            unit=attacker,
            target_unit=attacker,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(attacker.models[0].get_temporary_melee_ap_bonus() or 0), 1)

        battle_shock_turns = []
        enemy_near.take_battle_shock_test = lambda turn: battle_shock_turns.append(("near", int(turn or 0)))
        enemy_far.take_battle_shock_test = lambda turn: battle_shock_turns.append(("far", int(turn or 0)))
        enemy_destroyed.models[0].wounds = 0

        ck_player.stratagems._queue_traitoris_fight_attacks_resolved_reactions(
            unit=attacker,
            target_unit=enemy_destroyed,
            killing_models_by_target={enemy_destroyed: [enemy_destroyed.models[0]]},
        )

        self.assertEqual(battle_shock_turns, [("near", 1)])

        game.event_system.publish("phase_end", player=ck_player, phase=game.phase)
        self.assertEqual(int(attacker.models[0].get_temporary_melee_ap_bonus() or 0), 0)


if __name__ == "__main__":
    unittest.main()
