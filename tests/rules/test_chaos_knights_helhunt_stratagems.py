import unittest
from math import sqrt
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.engine.decisions import DecisionQueue
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _RegistryStub:
    def __init__(self, units, players):
        self._units = {str(getattr(unit, "_id", "") or ""): unit for unit in list(units or []) if unit is not None}
        self._players = {
            str(getattr(player, "id", "") or ""): player for player in list(players or []) if player is not None
        }
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
    def __init__(self, *, units=None):
        self.units = list(units or [])
        self.objectives = []
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
        return [
            other
            for other in list(self.units or [])
            if other is not None and getattr(other, "get_parent_army", lambda: None)() is not unit_army
        ]

    def get_distance_between_units(self, unit_a, unit_b):
        return _unit_distance(unit_a, unit_b)

    def is_within_engagement_range(self, unit_a, unit_b):
        distance = self.get_distance_between_units(unit_a, unit_b)
        return distance is not None and float(distance) <= 1.0 + 1e-6


class _GameStub:
    def __init__(self, *, current_player, players, units, phase_name="COMMAND_PHASE", turn=1):
        self.is_authoritative = True
        self.turn = int(turn)
        self.phase = SimpleNamespace(name=str(phase_name or "COMMAND_PHASE"))
        self.players = list(players or [])
        self.map = _MapStub(units=units)
        self.objectives = []
        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self.entity_registry = _RegistryStub(units, players)
        self._current_player = current_player
        self.queued_reactive_moves = []
        self.fight_phase_manager = FightPhaseManager(self)

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

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
        self.map.units = list(units)
        self.entity_registry = _RegistryStub(units, self.players)

    def _queue_reactive_move_movement_decision(self, **kwargs):
        self.queued_reactive_moves.append(dict(kwargs))
        return SimpleNamespace(context=dict(kwargs))


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
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, faction_name="Chaos Knights", keywords=None, faction_keywords=None):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_phase = False
    unit.round_state.fell_back_this_round = False
    return unit


def _set_unit_position(unit, x: float, y: float, z: float = 0.0):
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), float(z), 0.0)


def _unit_distance(unit_a, unit_b):
    if unit_a is None or unit_b is None:
        return None
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


def _add_weapon(unit, name: str, *, melee: bool):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear.append(weapon)
    return weapon.profiles["default"]


class TestChaosKnightsHelhuntStratagems(unittest.TestCase):
    def _setup_players(self):
        ck_army = Army.with_detachment("Chaos Knights", detachment_type="Helhunt Lance")
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player
        ck_player.command_points = 6

        enemy_army = Army.with_detachment("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
        enemy_player.command_points = 0
        return ck_army, ck_player, enemy_army, enemy_player

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

    def test_helhunt_stratagem_descriptors_registered(self):
        expected = {
            "000010752002": ("Feral Arrogance", "conditional_feel_no_pain"),
            "000010752003": ("Merciless Fusillade", "phase_target_lock_and_weapon_keyword_bonus"),
            "000010752004": ("Beasthide Manifestation", "worsen_incoming_ap"),
            "000010752005": ("Flush the Quarry", "phase_move_passthrough_and_desperate_escape_auto_pass"),
            "000010752006": ("Contemptuous Volleys", "shoot_and_charge_after_fall_back"),
            "000010752007": ("Goaded Beast", "reactive_surge_move"),
        }
        for stratagem_id, (name, effect) in expected.items():
            descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(descriptor)
            self.assertEqual(str(getattr(descriptor, "name", "") or ""), name)
            self.assertEqual(str(getattr(descriptor, "effect", "") or ""), effect)

    def test_flush_the_quarry_applies_and_cleans_up_movement_effects(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = _make_unit(
            "Knight Tyrant",
            keywords=["CHAOS KNIGHTS", "TITANIC"],
            faction_keywords=["CHAOS KNIGHTS"],
        )
        dog_a = _make_unit("War Dog A", keywords=["CHAOS KNIGHTS", "WAR DOG"], faction_keywords=["CHAOS KNIGHTS"])
        dog_b = _make_unit("War Dog B", keywords=["CHAOS KNIGHTS", "WAR DOG"], faction_keywords=["CHAOS KNIGHTS"])
        ck_army.add_unit(source)
        ck_army.add_unit(dog_a)
        ck_army.add_unit(dog_b)
        game = _GameStub(current_player=ck_player, players=[ck_player, enemy_player], units=list(ck_army.units))
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, ck_player, "MOVEMENT_PHASE")
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(dog_a, 3.0, 0.0)
        _set_unit_position(dog_b, 5.0, 0.0)
        game.rebuild_entity_registry()

        self.assertTrue(
            ck_player.stratagems.use(
                "FLUSH THE QUARRY",
                unit=source,
                selected_units=[dog_a, dog_b],
                phase_name="Movement phase",
            )
        )
        for dog in (dog_a, dog_b):
            special_rules = dict(getattr(dog, "special_rules", {}) or {})
            self.assertTrue(bool(special_rules.get("helhunt_flush_the_quarry_active")))
            self.assertEqual(
                set(special_rules.get("bearer_unit_phase_move_types") or []),
                {"advance", "fall_back", "move"},
            )
            self.assertEqual(
                set(special_rules.get("bearer_unit_phase_move_engagement_types") or []),
                {"advance", "fall_back", "move"},
            )
            self.assertTrue(bool(special_rules.get("bearer_unit_auto_pass_desperate_escape")))

        ck_player.stratagems._cleanup_helhunt_phase_end_effects(player=ck_player, phase=game.phase)
        for dog in (dog_a, dog_b):
            special_rules = dict(getattr(dog, "special_rules", {}) or {})
            self.assertFalse(bool(special_rules.get("helhunt_flush_the_quarry_active")))
            self.assertFalse(bool(special_rules.get("bearer_unit_phase_move_types")))
            self.assertFalse(bool(special_rules.get("bearer_unit_phase_move_engagement_types")))
            self.assertFalse(bool(special_rules.get("bearer_unit_auto_pass_desperate_escape")))

    def test_merciless_fusillade_locks_ranged_targets_and_grants_sustained_hits(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = _make_unit(
            "Knight Despoiler",
            keywords=["CHAOS KNIGHTS", "TITANIC"],
            faction_keywords=["CHAOS KNIGHTS"],
        )
        dog = _make_unit("War Dog", keywords=["CHAOS KNIGHTS", "WAR DOG"], faction_keywords=["CHAOS KNIGHTS"])
        enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        source_profile = _add_weapon(source, "Despoiler Cannon", melee=False)
        dog_profile = _add_weapon(dog, "War Dog Cannon", melee=False)
        ck_army.add_unit(source)
        ck_army.add_unit(dog)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(current_player=ck_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, ck_player, "SHOOTING_PHASE")
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(dog, 2.0, 0.0)
        _set_unit_position(enemy_a, 10.0, 0.0)
        _set_unit_position(enemy_b, 12.0, 0.0)
        game.rebuild_entity_registry()

        self.assertTrue(
            ck_player.stratagems.use(
                "MERCILESS FUSILLADE",
                unit=source,
                selected_units=[dog],
                enemy_unit=enemy_a,
                phase_name="Shooting phase",
            )
        )

        self.assertTrue(
            source._can_model_shoot_weapon_at_target(source.models[0], source_profile, enemy_a, game.map)
        )
        self.assertFalse(
            source._can_model_shoot_weapon_at_target(source.models[0], source_profile, enemy_b, game.map)
        )
        self.assertTrue(dog._can_model_shoot_weapon_at_target(dog.models[0], dog_profile, enemy_a, game.map))
        self.assertFalse(dog._can_model_shoot_weapon_at_target(dog.models[0], dog_profile, enemy_b, game.map))
        lookup_name = source_profile._temporary_weapon_lookup_name()
        bonuses = source.models[0].get_temporary_weapon_keyword_bonuses(lookup_name)
        self.assertTrue(any(str(entry.get("keyword", "") or "") == "SUSTAINED HITS 1" for entry in list(bonuses or [])))

    def test_merciless_fusillade_melee_lock_relaxes_when_marked_enemy_is_no_longer_eligible(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        source = _make_unit(
            "Knight Rampager",
            keywords=["CHAOS KNIGHTS", "TITANIC"],
            faction_keywords=["CHAOS KNIGHTS"],
        )
        _add_weapon(source, "Reaper Chainsword", melee=True)
        enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(source)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(current_player=enemy_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, enemy_player, "FIGHT_PHASE")
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_a, 0.5, 0.0)
        _set_unit_position(enemy_b, 5.0, 0.0)
        game.rebuild_entity_registry()

        self.assertTrue(
            ck_player.stratagems.use(
                "MERCILESS FUSILLADE",
                unit=source,
                selected_units=[],
                enemy_unit=enemy_a,
                phase_name="Fight phase",
            )
        )
        eligible_now = list(game.fight_phase_manager._get_eligible_targets(source) or [])
        self.assertEqual(eligible_now, [enemy_a])

        _set_unit_position(enemy_a, 8.0, 0.0)
        _set_unit_position(enemy_b, 0.5, 0.0)
        eligible_after = list(game.fight_phase_manager._get_eligible_targets(source) or [])
        self.assertIn(enemy_b, eligible_after)
        self.assertNotIn(enemy_a, eligible_after)

    def test_beasthide_manifestation_applies_ap_worsen_until_attacker_finishes(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        defender = _make_unit("Knight Abominant", keywords=["CHAOS KNIGHTS"], faction_keywords=["CHAOS KNIGHTS"])
        attacker = _make_unit("Enemy Shooter", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(current_player=enemy_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, enemy_player, "SHOOTING_PHASE")
        game.rebuild_entity_registry()

        ck_player.stratagems._queue_helhunt_shooting_target_reactions(attacking_unit=attacker, target_units=[defender])
        pending = [r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "BEASTHIDE MANIFESTATION"]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "BEASTHIDE MANIFESTATION",
                unit=defender,
                enemy_unit=attacker,
                candidates=[defender],
                phase_name="Shooting phase",
                dequeue=True,
            )
        )

        attacker_key = ck_player.stratagems._attacker_unit_key(attacker)
        spec = dict(getattr(defender, "special_rules", {}) or {}).get("armour_of_contempt_ap_worsen")
        self.assertEqual(int(dict(spec or {}).get(str(attacker_key), 0) or 0), 1)

        ck_player.stratagems._on_unit_shooting_resolved_armour_of_contempt_cleanup(attacker_unit=attacker)
        self.assertFalse(bool(dict(getattr(defender, "special_rules", {}) or {}).get("armour_of_contempt_ap_worsen")))

    def test_goaded_beast_queues_after_enemy_shooting_and_requests_surge_move(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        defender = _make_unit("Knight Desecrator", keywords=["CHAOS KNIGHTS"], faction_keywords=["CHAOS KNIGHTS"])
        attacker = _make_unit("Enemy Shooter", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        ck_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(current_player=enemy_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, enemy_player, "SHOOTING_PHASE")
        _set_unit_position(defender, 0.0, 0.0)
        _set_unit_position(attacker, 6.0, 0.0)
        game.rebuild_entity_registry()

        ck_player.stratagems._capture_helhunt_goaded_beast_shooting_targets(
            attacking_unit=attacker,
            target_units=[defender],
        )
        defender.models[0].wounds -= 2
        ck_player.stratagems._queue_helhunt_shooting_resolved_reactions(attacker_unit=attacker)
        pending = [r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "GOADED BEAST"]
        self.assertTrue(pending)

        with patch("warhammer40k_ai.rules.stratagems_chaos_knights.get_roll", return_value=5):
            self.assertTrue(
                ck_player.stratagems.use(
                    "GOADED BEAST",
                    unit=defender,
                    enemy_unit=attacker,
                    candidates=[defender],
                    phase_name="Shooting phase",
                    dequeue=True,
                )
            )
        self.assertEqual(len(game.queued_reactive_moves), 1)
        self.assertEqual(int(game.queued_reactive_moves[0]["max_distance"]), 5)
        self.assertEqual(str(game.queued_reactive_moves[0]["movement_type"]), "blood_surge")
        self.assertIs(game.queued_reactive_moves[0]["unit"], defender)

    def test_contemptuous_volleys_queues_and_grants_fall_back_permissions(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        unit = _make_unit("Knight Stalker", keywords=["CHAOS KNIGHTS"], faction_keywords=["CHAOS KNIGHTS"])
        profile = _add_weapon(unit, "Stalker Cannon", melee=False)
        ck_army.add_unit(unit)
        all_units = list(ck_army.units)
        game = _GameStub(current_player=ck_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, ck_player, "MOVEMENT_PHASE")
        unit.round_state.fell_back_this_round = True

        ck_player.stratagems._queue_helhunt_move_end_reactions(unit=unit, action="fall_back")
        pending = [r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "CONTEMPTUOUS VOLLEYS"]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "CONTEMPTUOUS VOLLEYS",
                unit=unit,
                phase_name="Movement phase",
                dequeue=True,
            )
        )
        self.assertTrue(unit.can_shoot_after_fall_back(profile))
        self.assertTrue(unit.can_charge_after_fall_back())

        ck_player.stratagems._cleanup_helhunt_phase_end_effects(
            player=ck_player,
            phase=SimpleNamespace(name="FIGHT_PHASE"),
        )
        self.assertFalse(unit._helhunt_contemptuous_volleys_active())

    def test_feral_arrogance_applies_mortal_wound_fnp_and_cleans_up(self):
        ck_army, ck_player, enemy_army, enemy_player = self._setup_players()
        defender = _make_unit("Knight Lancer", keywords=["CHAOS KNIGHTS"], faction_keywords=["CHAOS KNIGHTS"])
        attacker = _make_unit("Enemy Psyker", faction_name="Enemy", keywords=["PSYKER"], faction_keywords=["ENEMY"])
        ck_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        all_units = list(ck_army.units) + list(enemy_army.units)
        game = _GameStub(current_player=enemy_player, players=[ck_player, enemy_player], units=all_units)
        self._set_game(game, ck_player, enemy_player)
        self._set_phase(game, enemy_player, "SHOOTING_PHASE")

        ck_player.stratagems._queue_helhunt_mortal_wound_reactions(
            target_unit=defender,
            attacker_unit=attacker,
            target_model=defender.models[0],
            phase_name="Shooting phase",
        )
        pending = [r for r in list(ck_player.stratagems._pending_reactions or []) if r.get("stratagem") == "FERAL ARROGANCE"]
        self.assertTrue(pending)
        self.assertTrue(
            ck_player.stratagems.use(
                "FERAL ARROGANCE",
                unit=defender,
                phase_name="Shooting phase",
                dequeue=True,
            )
        )
        entries = list(dict(getattr(defender, "special_rules", {}) or {}).get("defensive_fnp_overrides", []) or [])
        self.assertTrue(
            any(
                int(entry.get("value", 0) or 0) == 5
                and str(entry.get("condition", "") or "").strip().lower() == "against mortal wounds"
                for entry in list(entries or [])
            )
        )

        ck_player.stratagems._cleanup_helhunt_phase_end_effects(player=enemy_player, phase=game.phase)
        entries_after = list(dict(getattr(defender, "special_rules", {}) or {}).get("defensive_fnp_overrides", []) or [])
        self.assertFalse(entries_after)


if __name__ == "__main__":
    unittest.main()
