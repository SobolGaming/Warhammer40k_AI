import unittest
from math import sqrt
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
    DECISION_SELECT_TARGET_MODEL,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.utility.entity_ids import get_entity_id


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


class _MapStub:
    def __init__(self, friendly_units=None, all_units=None):
        self._friendly_units = list(friendly_units or [])
        self._all_units = list(all_units or friendly_units or [])
        self.units = list(self._all_units)
        self.objectives = []
        self.terrain_features = []

    def get_friendly_units(self, _attacker_unit):
        return list(self._friendly_units)

    def get_enemy_units(self, attacker_unit):
        if attacker_unit is None:
            return []
        attacker_army = attacker_unit.get_parent_army() if hasattr(attacker_unit, "get_parent_army") else None
        return [
            unit
            for unit in list(self._all_units or [])
            if unit is not None and getattr(unit, "get_parent_army", lambda: None)() is not attacker_army
        ]

    def get_distance_between_units(self, unit_a, unit_b):
        return _unit_distance(unit_a, unit_b)

    def is_within_engagement_range(self, unit_a, unit_b):
        distance = self.get_distance_between_units(unit_a, unit_b)
        return distance is not None and float(distance) <= 1.0 + 1e-6


class _GameStub:
    def __init__(self, *, current_player, enemy_units_by_player, units, players, phase_name="SHOOTING_PHASE", map_obj=None):
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name=str(phase_name or "SHOOTING_PHASE"))
        self.map = map_obj or _MapStub(all_units=units)
        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self.players = list(players or [])
        self.entity_registry = _RegistryStub(units, players)
        self._current_player = current_player
        self._enemy_units_by_player = {
            str(player_id or ""): list(enemy_units or [])
            for player_id, enemy_units in dict(enemy_units_by_player or {}).items()
        }
        self.queued_reactive_moves = []

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, player):
        player_id = str(getattr(player, "id", "") or "")
        return list(self._enemy_units_by_player.get(player_id, []))

    def rebuild_entity_registry(self):
        units = []
        for player in list(self.players or []):
            army = getattr(player, "army", None)
            units.extend(list(getattr(army, "units", []) or []))
        self.entity_registry = _RegistryStub(units, self.players)
        if hasattr(self.map, "units"):
            self.map.units = list(units)
        if hasattr(self.map, "_all_units"):
            self.map._all_units = list(units)

    def _queue_reactive_move_movement_decision(self, **kwargs):
        self.queued_reactive_moves.append(dict(kwargs))
        return SimpleNamespace(context=dict(kwargs))


class _MockDatasheet:
    def __init__(self, name, *, faction_name, keywords=None, faction_keywords=None, cost=100):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1-10 Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None, cost=100, quantity=1):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
    )
    unit = Unit(datasheet, quantity=int(quantity))
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
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


class TestChaosKnightsIconoclastFiefdom(unittest.TestCase):
    def _setup_players(self, *, points_limit=2000):
        ck_army = Army.with_detachment("Chaos Knights", detachment_type="Iconoclast Fiefdom", points_limit=points_limit)
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player
        ck_player.command_points = 6

        enemy_army = Army.with_detachment("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        enemy_player.command_points = 0
        return ck_army, ck_player, enemy_army, enemy_player

    def _make_chaos_knight(self, name: str, *, titanic=False, cost=400):
        keywords = ["CHAOS KNIGHTS"]
        if titanic:
            keywords.append("TITANIC")
        return _make_unit(
            name,
            faction_name="Chaos Knights",
            keywords=keywords,
            faction_keywords=["CHAOS KNIGHTS"],
            cost=cost,
        )

    def _make_damned(self, name: str, *, cost=100, character=False, quantity=1, extra_keywords=None):
        keywords = ["DAMNED", "INFANTRY"]
        if character:
            keywords.append("CHARACTER")
        keywords.extend(list(extra_keywords or []))
        return _make_unit(
            name,
            faction_name="Heretic Astartes",
            keywords=keywords,
            faction_keywords=["HERETIC ASTARTES"],
            cost=cost,
            quantity=quantity,
        )

    def _set_game(self, game, *players):
        for player in players:
            player.set_game(game)

    def test_iconoclast_validation_rejects_damned_warlord(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        ck_army.add_unit(self._make_chaos_knight("Knight Abominant", titanic=True))
        damned = self._make_damned("Cultist Mob", character=True)
        ck_army.add_unit(damned)
        ck_army.select_warlord(damned)

        with self.assertRaises(ArmyValidationError):
            ck_army.validate_detachment_rules()

    def test_iconoclast_validation_rejects_damned_points_cap(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players(points_limit=1000)
        ck_army.add_unit(self._make_chaos_knight("Knight Abominant", titanic=True))
        ck_army.add_unit(self._make_damned("Damned A", cost=100))
        ck_army.add_unit(self._make_damned("Damned B", cost=100))
        ck_army.add_unit(self._make_damned("Damned C", cost=100))

        with self.assertRaises(ArmyValidationError):
            ck_army.validate_detachment_rules()

    def test_iconoclast_dark_sacrifice_request_and_apply(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0, 0.0)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_dark_sacrifice_choice(source, trigger="shooting", game=game)

        requests = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_dark_sacrifice"
        ]
        self.assertTrue(requests)
        request = requests[-1]

        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("damned_unit_id", "") or "") == str(getattr(damned, "_id", ""))
            and str((getattr(opt, "payload", {}) or {}).get("sacrifice_mode", "") or "") == "LETHAL_HITS"
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )

        damned.pass_leadership_check = lambda *_a, **_k: True
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=2):
            apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        self.assertEqual(len(getattr(damned, "models", []) or []), 0)

        source_model = source.models[0]
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        bonuses_after = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertFalse(bool(bonuses_after.get("lethal_hits", False)))

    def test_iconoclast_dark_sacrifice_invalid_path_rejected(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 12.0, 0.0, 0.0)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        bad_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Dark Sacrifice invalid test",
            player_id=ck_player.id,
            options=[
                DecisionOption.create(
                    "Bad option",
                    payload={
                        "source_unit_id": str(getattr(source, "_id", "")),
                        "damned_unit_id": str(getattr(enemy, "_id", "")),
                        "target_unit_id": str(getattr(enemy, "_id", "")),
                        "sacrifice_mode": "LETHAL_HITS",
                        "trigger": "shooting",
                    },
                )
            ],
            context={
                "ability": "iconoclast_dark_sacrifice",
                "ability_name": "Dark Sacrifice",
                "source_unit_id": str(getattr(source, "_id", "")),
                "trigger": "shooting",
                "candidate_damned_unit_ids": [str(getattr(damned, "_id", ""))],
                "allowed_modes": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "optional": True,
            },
        )
        bad_result = DecisionResult(
            decision_id=bad_request.decision_id,
            player_id=ck_player.id,
            option_id=bad_request.options[0].option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, bad_request, bad_result)
        self.assertFalse(apply_result.ok)

    def test_iconoclast_profane_altar_dark_sacrifice_grants_both_keywords_and_max_models(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 3.0, 0.0, 0.0)
        _set_unit_position(enemy, 10.0, 0.0, 0.0)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765002",
            name="Profane Altar",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_profane_altar")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        ck_player.game = game
        enemy_player.game = game

        damned.pass_leadership_check = lambda *_a, **_k: False
        mgr = ck_army.chaos_knights_detachments
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=1):
            outcome = mgr.apply_iconoclast_dark_sacrifice(
                source,
                damned,
                mode="LETHAL_HITS",
                game=game,
                player=ck_player,
            )
        self.assertTrue(bool(outcome.get("ok")))
        self.assertEqual(int(outcome.get("destroy_target", 0) or 0), 6)
        self.assertEqual(set(outcome.get("weapon_keywords") or []), {"LETHAL HITS", "SUSTAINED HITS 1"})

        source_model = source.models[0]
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source_model,
            weapon_name="Desecrator Cannon",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))
        self.assertEqual(int(bonuses.get("sustained_hits_value", 0) or 0), 1)

    def test_iconoclast_tyrants_banner_allows_visible_dark_sacrifice_target(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Desecrator", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 12.0, 0.0, 0.0)
        _set_unit_position(enemy, 20.0, 0.0, 0.0)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765004",
            name="Tyrant's Banner",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_tyrants_banner")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
        )
        game._model_can_see_unit = lambda model, target, game_map=None: target is damned
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_dark_sacrifice_choice(source, trigger="shooting", game=game)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_dark_sacrifice"
        ]
        self.assertTrue(requests)
        request = requests[-1]
        self.assertIn(str(getattr(damned, "_id", "")), list((request.context or {}).get("candidate_damned_unit_ids", []) or []))

        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("damned_unit_id", "") or "") == str(getattr(damned, "_id", ""))
        )
        damned.pass_leadership_check = lambda *_a, **_k: True
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )
        with patch("warhammer40k_ai.rules.chaos_knights_detachments.get_roll", return_value=1):
            apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)

    def test_iconoclast_pave_the_way_selection_applies_scouts(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Rampager", titanic=True)
        damned_a = self._make_damned("Damned A")
        damned_b = self._make_damned("Damned B")
        damned_c = self._make_damned("Damned C")
        damned_d = self._make_damned("Damned D")
        ck_army.add_unit(source)
        ck_army.add_unit(damned_a)
        ck_army.add_unit(damned_b)
        ck_army.add_unit(damned_c)
        ck_army.add_unit(damned_d)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000009765003",
            name="Pave the Way",
            faction_id="QT",
            detachment="Iconoclast Fiefdom",
            description="",
        ).apply_to_unit(source)
        self.assertTrue(bool(source.special_rules.get("enhancement_iconoclast_pave_the_way")))

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: list(enemy_army.units),
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="DECLARE_BATTLE_FORMATIONS",
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_iconoclast_pave_the_way_selection_request(game=game, player=ck_player)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "iconoclast_pave_the_way_selection"
        ]
        self.assertTrue(requests)
        request = requests[-1]
        select_ids = [str(getattr(damned_a, "_id", "")), str(getattr(damned_b, "_id", "")), str(getattr(damned_c, "_id", ""))]
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=request.options[0].option_id,
            payload={"unit_ids": list(select_ids)},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        for unit in (damned_a, damned_b, damned_c):
            self.assertTrue(bool(unit.special_rules.get("iconoclast_pave_the_way_active")))
            has_scout, distance = unit.has_scout()
            self.assertTrue(bool(has_scout))
            self.assertEqual(float(distance), 6.0)
        self.assertFalse(bool(damned_d.special_rules.get("iconoclast_pave_the_way_active")))

    def test_iconoclast_dread_tyrants_aura_applies_within_range(self):
        ck_army, _ck_player, enemy_army, _enemy_player = self._setup_players()
        source = self._make_chaos_knight("Knight Tyrant", titanic=True)
        attacker = self._make_damned("Damned Squad")
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source)
        ck_army.add_unit(attacker)
        enemy_army.add_unit(target)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(attacker, 4.0, 0.0, 0.0)
        _set_unit_position(target, 12.0, 0.0, 0.0)

        weapon_profile = SimpleNamespace(name="Autogun")
        aura_map = _MapStub([source, attacker])
        mods = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertTrue(bool(mods.reroll_hit_ones))
        self.assertTrue(bool(mods.reroll_wound_ones))

        _set_unit_position(source, 20.0, 0.0, 0.0)
        mods_out_of_range = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertFalse(bool(mods_out_of_range.reroll_hit_ones))
        self.assertFalse(bool(mods_out_of_range.reroll_wound_ones))

    def test_iconoclast_stratagem_descriptors_resolve_all_new_entries(self):
        expected = {
            "000009766002": "Avenge the Masters!",
            "000009766003": "Wretched Masses",
            "000009766004": "Soul Hunger",
            "000009766005": "Unrestrained Rage",
            "000009766006": "Worthless Chattel",
            "000009766007": "Preserve the Idols",
        }
        for stratagem_id, name in expected.items():
            descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(descriptor)
            self.assertEqual(str(getattr(descriptor, "name", "") or ""), name)
        self.assertEqual(
            str(getattr(get_stratagem_tool_descriptor(name="WORTHLESS CHATTEL"), "name", "") or ""),
            "Worthless Chattel",
        )

    def test_iconoclast_avenge_the_masters_marks_enemy_for_damned_lethal_hits(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        destroyed_knight = self._make_chaos_knight("Knight Abominant", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(destroyed_knight)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="FIGHT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)

        destroyed_knight.models[0].die(game_map=game.map)
        game.event_system.publish("unit_destroyed", unit=destroyed_knight, destroyed_by_unit=enemy)
        pending = [
            reaction
            for reaction in list(ck_player.stratagems._pending_reactions or [])
            if reaction.get("stratagem") == "AVENGE THE MASTERS!"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "AVENGE THE MASTERS!",
                unit=destroyed_knight,
                enemy_unit=enemy,
                phase_name="Fight phase",
                dequeue=True,
            )
        )

        bonuses = damned.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=damned.models[0],
            weapon_name="Autogun",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))

    def test_iconoclast_wretched_masses_returns_destroyed_damned_to_strategic_reserves_once(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        knight = self._make_chaos_knight("Knight Tyrant", titanic=True)
        damned = self._make_damned("Cultist Mob", quantity=3)
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(knight)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="FIGHT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)

        for model in list(damned.models):
            model.die(game_map=game.map)
        game.event_system.publish("unit_destroyed", unit=damned, destroyed_by_unit=enemy)
        pending = [
            reaction
            for reaction in list(ck_player.stratagems._pending_reactions or [])
            if reaction.get("stratagem") == "WRETCHED MASSES"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "WRETCHED MASSES",
                unit=damned,
                phase_name="Fight phase",
                dequeue=True,
            )
        )

        returned = [unit for unit in list(ck_army.units) if unit is not damned and getattr(unit, "name", "") == damned.name]
        self.assertEqual(len(returned), 1)
        returned_unit = returned[0]
        self.assertEqual(str(getattr(returned_unit, "reserve_status", "") or ""), "strategic_reserves")
        self.assertEqual(len(list(getattr(returned_unit, "models", []) or [])), 3)
        self.assertFalse(
            ck_player.stratagems.use(
                "WRETCHED MASSES",
                unit=damned,
                phase_name="Fight phase",
            )
        )

    def test_iconoclast_soul_hunger_queues_on_kill_and_heals_bonus_vs_battleshocked(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        knight = self._make_chaos_knight("Knight Abominant", titanic=True)
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(knight)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="FIGHT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)
        ck_player.stratagems._current_phase_name = "Fight phase"
        knight.models[0].wounds = 1
        enemy.is_battle_shocked = lambda: True

        game.event_system.publish(
            "fight_attacks_resolved",
            unit=knight,
            target_unit=enemy,
            killing_models_by_target={enemy: [enemy.models[0]]},
        )
        pending = [
            reaction
            for reaction in list(ck_player.stratagems._pending_reactions or [])
            if reaction.get("stratagem") == "SOUL HUNGER"
        ]
        self.assertTrue(pending)
        with patch("warhammer40k_ai.rules.stratagems_chaos_knights.get_roll", return_value=2):
            self.assertTrue(
                ck_player.stratagems.use(
                    "SOUL HUNGER",
                    unit=knight,
                    battle_shocked_kills=True,
                    phase_name="Fight phase",
                    dequeue=True,
                )
            )
        self.assertEqual(int(knight.models[0].wounds), 2)

    def test_iconoclast_unrestrained_rage_queues_on_advance_and_grants_shoot_and_charge(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        knight = self._make_chaos_knight("Knight Rampager", titanic=True)
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(knight)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="MOVEMENT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)
        knight.round_state.advanced_this_round = True

        game.event_system.publish("unit_move_ended", unit=knight, action="advance")
        pending = [
            reaction
            for reaction in list(ck_player.stratagems._pending_reactions or [])
            if reaction.get("stratagem") == "UNRESTRAINED RAGE"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "UNRESTRAINED RAGE",
                unit=knight,
                action="advance",
                phase_name="Movement phase",
                dequeue=True,
            )
        )
        ranged_profile = SimpleNamespace(
            parent_wargear=SimpleNamespace(is_ranged=lambda: True),
            is_assault=lambda: False,
        )
        self.assertTrue(bool(knight.can_shoot_after_advance(ranged_profile)))
        self.assertTrue(bool(knight.can_charge_after_advance()))

    def test_iconoclast_unrestrained_rage_supports_fall_back_trigger(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        knight = self._make_chaos_knight("Knight Despoiler", titanic=True)
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(knight)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="MOVEMENT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)
        knight.round_state.fell_back_this_round = True

        self.assertTrue(
            ck_player.stratagems.use(
                "UNRESTRAINED RAGE",
                unit=knight,
                action="fall_back",
                phase_name="Movement phase",
            )
        )
        ranged_profile = SimpleNamespace(
            parent_wargear=SimpleNamespace(is_ranged=lambda: True),
            is_assault=lambda: False,
        )
        self.assertTrue(bool(knight.can_shoot_after_fall_back(ranged_profile)))
        self.assertTrue(bool(knight.can_charge_after_fall_back()))

    def test_iconoclast_worthless_chattel_queues_model_destruction_after_engaged_shooting_damage(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        damned = self._make_damned("Cultist Mob", quantity=3)
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(self._make_chaos_knight("Knight Tyrant", titanic=True))
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="SHOOTING_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)
        ck_player.stratagems._current_phase_name = "Shooting phase"
        _set_unit_position(damned, 0.0, 0.0, 0.0)
        _set_unit_position(enemy, 0.5, 0.0, 0.0)

        self.assertTrue(
            ck_player.stratagems.use(
                "WORTHLESS CHATTEL",
                unit=damned,
                phase_name="Shooting phase",
            )
        )
        self.assertTrue(bool(damned._ignore_engagement_for_ranged_targeting_active()))

        with patch("warhammer40k_ai.rules.stratagems_chaos_knights.get_roll", side_effect=[4, 4]):
            game.event_system.publish(
                "unit_shooting_resolved",
                attacker_unit=damned,
                damage_by_target_while_engaged={enemy: 2},
            )

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_TARGET_MODEL
            and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "worthless_chattel_destroy"
        ]
        self.assertTrue(requests)
        first_request = requests[-1]
        first_result = DecisionResult(
            decision_id=first_request.decision_id,
            player_id=ck_player.id,
            option_id=first_request.options[0].option_id,
            payload={},
        )
        first_apply = dispatch_decision(game, first_request, first_result)
        self.assertTrue(first_apply.ok)

        followups = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_TARGET_MODEL
            and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "worthless_chattel_destroy"
            and int((getattr(req, "context", {}) or {}).get("destroy_remaining", 0) or 0) == 1
        ]
        self.assertTrue(followups)
        second_request = followups[-1]
        second_result = DecisionResult(
            decision_id=second_request.decision_id,
            player_id=ck_player.id,
            option_id=second_request.options[0].option_id,
            payload={},
        )
        second_apply = dispatch_decision(game, second_request, second_result)
        self.assertTrue(second_apply.ok)
        self.assertEqual(len(list(getattr(damned, "models", []) or [])), 1)

    def test_iconoclast_preserve_the_idols_queues_reactive_move_and_requires_ending_closer(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source_knight = self._make_chaos_knight("Knight Tyrant", titanic=True)
        damned = self._make_damned("Cultist Mob")
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            cost=100,
        )
        ck_army.add_unit(source_knight)
        ck_army.add_unit(damned)
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            phase_name="MOVEMENT_PHASE",
            map_obj=_MapStub(all_units=all_units),
        )
        self._set_game(game, ck_player, enemy_player)
        _set_unit_position(source_knight, 0.0, 0.0, 0.0)
        _set_unit_position(damned, 5.0, 0.0, 0.0)
        _set_unit_position(enemy, 8.0, 0.0, 0.0)

        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = [
            reaction
            for reaction in list(ck_player.stratagems._pending_reactions or [])
            if reaction.get("stratagem") == "PRESERVE THE IDOLS"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "PRESERVE THE IDOLS",
                unit=damned,
                source_unit=source_knight,
                enemy_unit=enemy,
                action="move",
                phase_name="Movement phase",
                dequeue=True,
            )
        )
        self.assertEqual(len(game.queued_reactive_moves), 1)
        queued = game.queued_reactive_moves[0]
        self.assertEqual(str(queued.get("kind", "") or ""), "chaos_knights_preserve_the_idols")
        self.assertIs(queued.get("unit"), damned)
        self.assertEqual(
            str((queued.get("extra_context") or {}).get("preserve_the_idols_enemy_unit_id", "") or ""),
            str(get_entity_id(enemy) or ""),
        )

        move_request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            "Preserve the Idols move",
            player_id=ck_player.id,
            options=[
                DecisionOption.create(
                    "Confirm",
                    payload={
                        "unit_id": str(get_entity_id(damned) or ""),
                        "movement_type": "reactive",
                        "action": "confirm",
                    },
                )
            ],
            context={
                "unit_id": str(get_entity_id(damned) or ""),
                "movement_type": "reactive",
                "max_distance": 6,
                "allow_skip": False,
                "reactive_move_kind": "chaos_knights_preserve_the_idols",
                "reactive_move_movement_type": "preserve_the_idols",
                "preserve_the_idols_enemy_unit_id": str(get_entity_id(enemy) or ""),
                "preserve_the_idols_source_unit_id": str(get_entity_id(source_knight) or ""),
            },
        )
        model_id = str(get_entity_id(damned.models[0]) or "")
        valid_result = DecisionResult(
            decision_id=move_request.decision_id,
            player_id=ck_player.id,
            option_id=move_request.options[0].option_id,
            payload={"model_positions": [{"model_id": model_id, "position": [6.0, 0.0, 0.0]}]},
        )
        valid_apply = dispatch_decision(game, move_request, valid_result)
        self.assertTrue(valid_apply.ok)
        self.assertAlmostEqual(float(damned.models[0].get_location()[0]), 6.0)

        _set_unit_position(damned, 5.0, 0.0, 0.0)
        invalid_result = DecisionResult(
            decision_id=move_request.decision_id,
            player_id=ck_player.id,
            option_id=move_request.options[0].option_id,
            payload={"model_positions": [{"model_id": model_id, "position": [5.0, 0.0, 0.0]}]},
        )
        invalid_apply = dispatch_decision(game, move_request, invalid_result)
        self.assertFalse(invalid_apply.ok)
        self.assertIn("Preserve the Idols", str(invalid_apply.errors[0]))


if __name__ == "__main__":
    unittest.main()
