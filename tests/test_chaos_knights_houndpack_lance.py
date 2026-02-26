import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.decisions import DecisionQueue, DecisionResult
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
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
    def __init__(self, friendly_units=None):
        self._friendly_units = list(friendly_units or [])

    def get_friendly_units(self, _attacker_unit):
        return list(self._friendly_units)


class _GameStub:
    def __init__(self, *, current_player, enemy_units_by_player, units, players):
        self.is_authoritative = True
        self.turn = 1
        self.phase = SimpleNamespace(name="COMMAND_PHASE")
        self.map = _MapStub()
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


class TestChaosKnightsHoundpackLance(unittest.TestCase):
    def _setup_players(self):
        ck_army = Army("Chaos Knights", detachment_type="Houndpack Lance")
        ck_army.faction_id = "QT"
        ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
        ck_army.player = ck_player

        enemy_army = Army("Enemy", detachment_type="None")
        enemy_army.faction_id = "EN"
        enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
        enemy_army.player = enemy_player
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
