import unittest
from math import sqrt
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_FRENZY_TARGET,
    DECISION_CHOOSE_QUARRY,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
)
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _RegistryStub:
    def __init__(self, units, players):
        self._units = {str(getattr(unit, "_id", "") or ""): unit for unit in list(units or []) if unit is not None}
        self._players = {str(getattr(player, "id", "") or ""): player for player in list(players or []) if player is not None}

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id or ""))
        if kind == "player":
            return self._players.get(str(entity_id or ""))
        return None


class _MapStub:
    def __init__(self, friendly_units=None, all_units=None):
        self._friendly_units = list(friendly_units or [])
        self._all_units = list(all_units or friendly_units or [])
        self.objectives = []

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
    def __init__(self, *, current_player, enemy_units_by_player, units, players, map_obj=None):
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name="COMMAND_PHASE")
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

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, player):
        player_id = str(getattr(player, "id", "") or "")
        return list(self._enemy_units_by_player.get(player_id, []))


class _MockDatasheet:
    def __init__(self, name, *, faction_name, keywords=None, faction_keywords=None):
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


def _make_unit(name, *, faction_name, keywords=None, faction_keywords=None):
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


def _make_weapon_profile(name: str, *, melee: bool):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestChaosKnightsHoundpackLance(unittest.TestCase):
    def _setup_players(self):
        ck_army = Army.with_detachment("Chaos Knights", detachment_type="Houndpack Lance")
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

    def _make_war_dog(self, name: str):
        return _make_unit(
            name,
            faction_name="Chaos Knights",
            keywords=["WAR DOG", "CHAOS KNIGHTS"],
            faction_keywords=["CHAOS KNIGHTS"],
        )

    def test_houndpack_validation_requires_three_war_dogs(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        ck_army.add_unit(self._make_war_dog("War Dog 1"))
        ck_army.add_unit(
            _make_unit(
                "Knight Tyrant",
                faction_name="Chaos Knights",
                keywords=["TITANIC", "CHAOS KNIGHTS"],
                faction_keywords=["CHAOS KNIGHTS"],
            )
        )

        with self.assertRaises(ArmyValidationError):
            ck_army.validate_detachment_rules()

    def test_houndpack_validation_applies_battleline_and_character(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        dogs = [self._make_war_dog(f"War Dog {i}") for i in range(1, 4)]
        for unit in dogs:
            ck_army.add_unit(unit)

        ck_army.validate_detachment_rules()
        mgr = ck_army.chaos_knights_detachments

        self.assertEqual(len(getattr(mgr, "_houndpack_character_unit_ids", set())), 3)
        for unit in dogs:
            self.assertTrue(unit.has_any_keyword("BATTLELINE"))
            self.assertTrue(unit.has_any_keyword("CHARACTER"))

    def test_houndpack_muster_selection_request_and_apply(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dogs = [self._make_war_dog(f"War Dog {i}") for i in range(1, 5)]
        for unit in dogs:
            ck_army.add_unit(unit)
        enemy_unit = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(enemy_unit)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy_unit],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.queue_houndpack_lance_character_selection_request(game=game, player=ck_player)

        requests = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "houndpack_lance_character_selection"
        ]
        self.assertTrue(requests)
        request = requests[-1]

        selected_ids = [str(getattr(unit, "_id", "") or "") for unit in dogs[1:4]]
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=request.options[0].option_id,
            payload={"unit_ids": list(selected_ids)},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        self.assertEqual(set(getattr(mgr, "_houndpack_character_unit_ids", set())), set(selected_ids))
        self.assertFalse(dogs[0].has_any_keyword("CHARACTER"))
        for unit in dogs[1:4]:
            self.assertTrue(unit.has_any_keyword("CHARACTER"))

    def test_marked_prey_request_and_apply(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dogs = [self._make_war_dog(f"War Dog {i}") for i in range(1, 4)]
        for unit in dogs:
            ck_army.add_unit(unit)
        enemy_unit = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(enemy_unit)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [enemy_unit],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        mgr.on_command_phase_start(game=game, player=ck_player)

        requests = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "marked_prey"
        ]
        self.assertTrue(requests)
        request = requests[-1]
        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(getattr(enemy_unit, "_id", "") or "")
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        self.assertEqual(str(getattr(mgr, "houndpack_marked_prey_unit_id", "")), str(getattr(enemy_unit, "_id", "")))

    def test_marked_prey_grants_sustained_hits_only_when_visible(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        attacker_unit = self._make_war_dog("War Dog Hunter")
        target_unit = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(attacker_unit)
        ck_army.add_unit(self._make_war_dog("War Dog 2"))
        ck_army.add_unit(self._make_war_dog("War Dog 3"))
        enemy_army.add_unit(target_unit)

        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={
                ck_player.id: [target_unit],
                enemy_player.id: list(ck_army.units),
            },
            units=all_units,
            players=[ck_player, enemy_player],
        )
        ck_player.game = game
        enemy_player.game = game

        mgr = ck_army.chaos_knights_detachments
        self.assertTrue(mgr.select_marked_prey(target_unit, game=game, player=ck_player))

        attacker_model = attacker_unit.models[0]
        attacker_unit._has_line_of_sight_to_target = lambda _model, _target, _map: True

        bonuses_visible = attacker_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=attacker_model,
            weapon_name="Chainblade",
            target=target_unit,
        )
        self.assertEqual(int(bonuses_visible.get("sustained_hits_value", 0) or 0), 1)
        self.assertTrue(
            any("Marked Prey" in str(source) for source in list(bonuses_visible.get("sources", []) or []))
        )

        attacker_unit._has_line_of_sight_to_target = lambda _model, _target, _map: False
        bonuses_blocked = attacker_unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=attacker_model,
            weapon_name="Chainblade",
            target=target_unit,
        )
        self.assertEqual(int(bonuses_blocked.get("sustained_hits_value", 0) or 0), 0)

    def test_houndpack_enhancement_descriptors_exist(self):
        expected = {
            "000010312002": ("Preyslayer's Mantle", "grant_super_heavy_walker"),
            "000010312003": ("Final Howl (Aura)", "reroll_wound_roll_of_1"),
            "000010312004": ("Loping Predator", "grant_weapon_keywords"),
            "000010312005": ("Panoply of the Cursed Knight", "worsen_incoming_ap"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_houndpack_stratagem_descriptors_exist(self):
        expected = {
            "000010313002": ("Vox-Howl", "battle_shock_aura_and_friendly_clear"),
            "000010313003": ("Hungry For Combat", "melee_target_lock_and_crit_hit_threshold"),
            "000010313004": ("Cunning Hunter", "shoot_and_charge_after_fall_back"),
            "000010313005": ("Animalistic Rage", "shoot_or_fight_before_removal"),
            "000010313006": ("Harrying Hounds", "reactive_normal_move"),
            "000010313007": ("Encircling Pack", "enter_strategic_reserves"),
        }
        for stratagem_id, (name, effect) in expected.items():
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_vox_howl_queues_and_applies_battleshock_effects(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = self._make_war_dog("War Dog Alpha")
        ally = self._make_war_dog("War Dog Beta")
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(source)
        ck_army.add_unit(ally)
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        ck_army.validate_detachment_rules()
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game_map = _MapStub(all_units=all_units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=game_map,
        )
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(ally, 4.0, 0.0, 0.0)
        _set_unit_position(enemy, 5.0, 0.0, 0.0)
        enemy_tests: list[int] = []
        cleared: list[str] = []
        enemy.take_battle_shock_test = lambda turn: enemy_tests.append(int(turn))
        ally.is_battle_shocked = lambda: True
        ally.pass_leadership_check = lambda: True
        ally.clear_battle_shock = lambda: cleared.append(str(ally.name)) or True

        ck_player.stratagems._queue_houndpack_lance_phase_start_reactions(player=ck_player, phase=game.phase)

        pending = [r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "VOX-HOWL"]
        self.assertTrue(pending)
        self.assertTrue(ck_player.stratagems.use("VOX-HOWL", unit=source, phase_name="Shooting phase", dequeue=True))
        self.assertEqual(enemy_tests, [1])
        self.assertEqual(cleared, [ally.name])

    def test_hungry_for_combat_applies_lock_and_restricts_fight_targets(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dog_one = self._make_war_dog("War Dog Alpha")
        dog_two = self._make_war_dog("War Dog Beta")
        dog_three = self._make_war_dog("War Dog Gamma")
        enemy_one = _make_unit("Enemy One", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_two = _make_unit("Enemy Two", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(dog_one)
        ck_army.add_unit(dog_two)
        ck_army.add_unit(dog_three)
        ck_army.validate_detachment_rules()
        enemy_army.add_unit(enemy_one)
        enemy_army.add_unit(enemy_two)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game_map = _MapStub(all_units=all_units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: list(enemy_army.units), enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=game_map,
        )
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        _set_unit_position(dog_one, 0.0, 0.0, 0.0)
        _set_unit_position(dog_two, 0.0, 0.0, 0.0)
        _set_unit_position(dog_three, 10.0, 0.0, 0.0)
        _set_unit_position(enemy_one, 0.0, 0.0, 0.0)
        _set_unit_position(enemy_two, 0.0, 0.0, 0.0)

        ck_player.stratagems._queue_houndpack_lance_phase_start_reactions(player=ck_player, phase=game.phase)

        pending = [
            r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "HUNGRY FOR COMBAT"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "HUNGRY FOR COMBAT",
                enemy_unit=enemy_one,
                selected_unit_ids=[dog_one._id, dog_two._id],
                phase_name="Fight phase",
                dequeue=True,
            )
        )
        context = dog_one._houndpack_hungry_for_combat_context(game=game)
        self.assertIsNotNone(context)
        self.assertEqual(int(context["crit_threshold"]), 5)
        self.assertTrue(dog_one._houndpack_hungry_for_combat_target_locked_to(enemy_one, game=game))
        self.assertFalse(dog_one._houndpack_hungry_for_combat_target_locked_to(enemy_two, game=game))

        fight_manager = FightPhaseManager(game)
        eligible = fight_manager._get_eligible_targets(dog_one)
        self.assertEqual([enemy_one], eligible)

    def test_cunning_hunter_allows_shoot_and_charge_after_fall_back(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dog = self._make_war_dog("War Dog Alpha")
        ck_army.add_unit(dog)
        ck_army.add_unit(self._make_war_dog("War Dog Beta"))
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        ck_army.validate_detachment_rules()
        all_units = list(ck_army.units)
        game = _GameStub(
            current_player=ck_player,
            enemy_units_by_player={ck_player.id: [], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=_MapStub(all_units=all_units),
        )
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        dog.round_state.fell_back_this_round = True
        profile = _make_weapon_profile("War Dog Cannon", melee=False)

        self.assertTrue(ck_player.stratagems.use("CUNNING HUNTER", unit=dog, phase_name="Movement phase"))
        self.assertTrue(dog.can_shoot_after_fall_back(profile))
        self.assertTrue(dog.can_charge_after_fall_back())

    def test_harrying_hounds_queues_reactive_move(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dog = self._make_war_dog("War Dog Alpha")
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(dog)
        ck_army.add_unit(self._make_war_dog("War Dog Beta"))
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        ck_army.validate_detachment_rules()
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=_MapStub(all_units=all_units),
        )
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        _set_unit_position(dog, 0.0, 0.0, 0.0)
        _set_unit_position(enemy, 8.0, 0.0, 0.0)
        queued: list[dict] = []
        game._queue_reactive_move_movement_decision = lambda **kwargs: queued.append(dict(kwargs)) or SimpleNamespace()

        ck_player.stratagems._queue_houndpack_lance_move_end_reactions(unit=enemy, action="move")
        pending = [
            r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "HARRYING HOUNDS"
        ]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "HARRYING HOUNDS",
                unit=dog,
                enemy_unit=enemy,
                action="move",
                phase_name="Movement phase",
                dequeue=True,
            )
        )
        self.assertEqual(len(queued), 1)
        self.assertEqual(int(queued[0]["max_distance"]), 6)
        self.assertIs(queued[0]["unit"], dog)

    def test_encircling_pack_places_unit_into_reserves(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dog = self._make_war_dog("War Dog Alpha")
        ck_army.add_unit(dog)
        ck_army.add_unit(self._make_war_dog("War Dog Beta"))
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        ck_army.validate_detachment_rules()
        all_units = list(ck_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=_MapStub(all_units=all_units),
        )
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        ck_player.stratagems._unit_wholly_within_battlefield_edge_distance = lambda unit, distance: unit is dog and distance == 12.0
        entered: list[str] = []
        dog.enter_strategic_reserves_midgame = lambda **_kwargs: entered.append(dog.name) or True

        ck_player.stratagems._queue_houndpack_lance_phase_end_reactions(player=enemy_player, phase=game.phase)
        pending = [
            r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "ENCIRCLING PACK"
        ]
        self.assertTrue(pending)
        self.assertTrue(ck_player.stratagems.use("ENCIRCLING PACK", unit=dog, phase_name="Fight phase", dequeue=True))
        self.assertEqual(entered, [dog.name])

    def test_animalistic_rage_queues_on_destroyed_model_and_resolves_fight(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        dog = self._make_war_dog("War Dog Alpha")
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(dog)
        ck_army.add_unit(self._make_war_dog("War Dog Beta"))
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        ck_army.validate_detachment_rules()
        enemy_army.add_unit(enemy)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(
            current_player=enemy_player,
            enemy_units_by_player={ck_player.id: [enemy], enemy_player.id: list(ck_army.units)},
            units=all_units,
            players=[ck_player, enemy_player],
            map_obj=_MapStub(all_units=all_units),
        )
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        ck_player.set_game(game)
        enemy_player.set_game(game)
        game._frenzy_can_fight_target = lambda unit, target, phase_name="": unit is dog and target is enemy
        frenzy_calls: list[tuple[str, str]] = []
        game._execute_frenzy_fight = lambda unit, target, phase_name="": frenzy_calls.append((unit.name, target.name)) or True
        dog._last_destroyed_by_unit = enemy

        model = dog.models[0]
        dog.remove_model(model, game_map=game.map)
        self.assertEqual(len(dog.models), 1)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_FRENZY_TARGET
        ]
        self.assertTrue(requests)
        request = requests[-1]
        option = next(opt for opt in list(request.options or []) if str((getattr(opt, "payload", {}) or {}).get("action", "")) == "fight")
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=ck_player.id,
            option_id=option.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(apply_result.ok)
        self.assertEqual(frenzy_calls, [(dog.name, enemy.name)])
        self.assertEqual(len(dog.models), 0)

    def test_preyslayers_mantle_grants_super_heavy_walker(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        bearer_unit = self._make_war_dog("War Dog Alpha")
        ck_army.add_unit(bearer_unit)

        self.assertFalse(bool(bearer_unit.has_super_heavy_walker()))
        bearer_unit._get_enhancement_bearer_model = lambda: bearer_unit.models[0]
        Enhancement(
            id="000010312002",
            name="Preyslayer's Mantle",
            faction_id="QT",
            detachment="Houndpack Lance",
            description="",
        ).apply_to_unit(bearer_unit)

        self.assertTrue(bool(bearer_unit.has_super_heavy_walker()))

    def test_loping_predator_grants_assault_to_bearer_ranged_weapons(self):
        ck_army, _ck_player, _enemy_army, _enemy_player = self._setup_players()
        bearer_unit = self._make_war_dog("War Dog Alpha")
        ck_army.add_unit(bearer_unit)

        bearer_unit._get_enhancement_bearer_model = lambda: bearer_unit.models[0]
        Enhancement(
            id="000010312004",
            name="Loping Predator",
            faction_id="QT",
            detachment="Houndpack Lance",
            description="",
        ).apply_to_unit(bearer_unit)

        weapon = Wargear(
            {
                "name": "Test Cannon",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-1",
                "D": "2",
                "description": "",
            }
        )
        profile = next(iter(weapon.profiles.values()))
        bearer_unit.round_state.advanced_this_round = True
        self.assertTrue(bool(bearer_unit.can_shoot_after_advance(profile)))

    def test_final_howl_aura_grants_wound_reroll_ones_within_six(self):
        ck_army, _ck_player, enemy_army, _enemy_player = self._setup_players()
        source = self._make_war_dog("War Dog Alpha")
        attacker = self._make_war_dog("War Dog Beta")
        target = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(source)
        ck_army.add_unit(attacker)
        ck_army.add_unit(self._make_war_dog("War Dog Gamma"))
        enemy_army.add_unit(target)

        _set_unit_position(source, 0.0, 0.0, 0.0)
        _set_unit_position(attacker, 5.0, 0.0, 0.0)
        _set_unit_position(target, 12.0, 0.0, 0.0)

        source._get_enhancement_bearer_model = lambda: source.models[0]
        Enhancement(
            id="000010312003",
            name="Final Howl (Aura)",
            faction_id="QT",
            detachment="Houndpack Lance",
            description="",
        ).apply_to_unit(source)

        weapon_profile = SimpleNamespace(name="Test Gun")
        aura_map = _MapStub([source, attacker])
        mods_in = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertTrue(bool(mods_in.reroll_wound_ones))

        _set_unit_position(attacker, 20.0, 0.0, 0.0)
        mods_out = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=aura_map)
        self.assertFalse(bool(mods_out.reroll_wound_ones))

    def test_panoply_of_the_cursed_knight_worsens_incoming_ap(self):
        ck_army, _ck_player, enemy_army, _enemy_player = self._setup_players()
        defender = self._make_war_dog("War Dog Defender")
        attacker = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ck_army.add_unit(defender)
        ck_army.add_unit(self._make_war_dog("War Dog 2"))
        ck_army.add_unit(self._make_war_dog("War Dog 3"))
        enemy_army.add_unit(attacker)

        defender._get_enhancement_bearer_model = lambda: defender.models[0]
        Enhancement(
            id="000010312005",
            name="Panoply of the Cursed Knight",
            faction_id="QT",
            detachment="Houndpack Lance",
            description="",
        ).apply_to_unit(defender)

        weapon = Wargear(
            {
                "name": "Test Rifle",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-2",
                "D": "2",
                "description": "",
            }
        )
        profile = next(iter(weapon.profiles.values()))

        ap_vs_bearer = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(int(ap_vs_bearer or 0), -1)

        bearer_model = defender.models[0]
        bearer_model.take_damage(int(getattr(bearer_model, "wounds", 0) or 0), game_map=None)
        ap_after_destroyed = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(int(ap_after_destroyed or 0), -2)


if __name__ == "__main__":
    unittest.main()
