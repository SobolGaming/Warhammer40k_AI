import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        wounds: int = 6,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Emperor's Children":
                faction_keywords = ["EMPEROR'S CHILDREN"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
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
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    wounds: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army("Emperor's Children", "Rapid Evisceration")
    ec_army.faction_id = "EC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    player = Player("P1", control=PlayerControl.REMOTE, army=ec_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(player)
    game.add_player(enemy_player)
    return game, ec_army, enemy_army, player, enemy_player


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_option_with(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


class TestRapidEviscerationEnhancements(unittest.TestCase):
    def test_spearhead_striker_applies_charge_reroll_and_no_overwatch_after_disembark(self):
        game, army, enemy_army, _player, _enemy_player = _build_game()
        game.turn = 1
        game.current_player_index = 0

        source = _make_unit("Lord Exultant", keywords=["CHARACTER", "INFANTRY"])
        transport = _make_unit("Raider", keywords=["Transport", "Vehicle", "Dedicated Transport"])
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        army.add_unit(source)
        army.add_unit(transport)
        enemy_army.add_unit(enemy)
        source.deployed = True
        transport.deployed = True
        enemy.deployed = True
        transport.transport_capacity = 10

        Enhancement(
            id="000010006003",
            name="Spearhead Striker",
            faction_id="EC",
            detachment="Rapid Evisceration",
            points=15,
            description="",
        ).apply_to_unit(source)

        transport.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)
        transport.add_passenger(source, game_map=game.map)
        source.round_state.embarked_this_round = False

        self.assertFalse(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        ok = source.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(ok)
        self.assertTrue(source.can_reroll_charge_roll(target_unit=enemy, game=game, game_map=game.map))
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

    def test_sublime_prescience_grants_temporary_strategic_reserves_round_bonus(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.turn = 1
        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE

        source = _make_unit("Lord Exultant", keywords=["CHARACTER", "INFANTRY"])
        transport = _make_unit("Transport", keywords=["Transport", "Vehicle"])
        army.add_unit(source)
        army.add_unit(transport)
        source.deployed = True
        transport.deployed = True
        transport.reserve_status = "strategic_reserves"
        transport._started_in_reserves = True
        game.map.units = [source]

        Enhancement(
            id="000010006002",
            name="Sublime Prescience",
            faction_id="EC",
            detachment="Rapid Evisceration",
            points=20,
            description="",
        ).apply_to_unit(source)

        self.assertFalse(transport.can_arrive_from_reserves(1))

        game.rebuild_entity_registry()
        game._on_phase_start_emperors_children_enhancements(player=player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="sublime_prescience",
        )
        self.assertIsNotNone(request)
        pick_transport = _first_option_with(
            request,
            lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(transport)),
        )
        self.assertIsNotNone(pick_transport)
        resolve_decision_command(game, request, pick_transport.option_id, player_id=player.id)

        self.assertTrue(transport.can_arrive_from_reserves(1))
        self.assertEqual(int(source.special_rules.get("enhancement_sublime_prescience_turn", 0) or 0), 1)

    def test_accomplished_tactician_embarks_hit_unit_once_per_turn(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.turn = 2
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1

        source = _make_unit("Lord Exultant", keywords=["CHARACTER", "INFANTRY"])
        passenger = _make_unit("Noise Marines", keywords=["INFANTRY"])
        existing_passenger = _make_unit("Existing Squad", keywords=["INFANTRY"])
        transport = _make_unit("Transport", keywords=["Transport", "Vehicle", "Dedicated Transport"])
        attacker = _make_unit(
            "Enemy Shooter",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        army.add_unit(source)
        army.add_unit(passenger)
        army.add_unit(existing_passenger)
        army.add_unit(transport)
        enemy_army.add_unit(attacker)
        source.deployed = True
        passenger.deployed = True
        existing_passenger.deployed = True
        transport.deployed = True
        attacker.deployed = True
        transport.transport_capacity = 20

        Enhancement(
            id="000010006004",
            name="Accomplished Tactician",
            faction_id="EC",
            detachment="Rapid Evisceration",
            points=15,
            description="",
        ).apply_to_unit(source)

        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        passenger.models[0].set_location(3.0, 0.0, 0.0, 0.0)
        existing_passenger.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        transport.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        attacker.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, passenger, existing_passenger, transport, attacker]

        transport.add_passenger(existing_passenger, game_map=game.map)
        existing_passenger.round_state.embarked_this_round = False

        game.rebuild_entity_registry()
        game._on_unit_shooting_resolved_emperors_children(
            attacker_unit=attacker,
            hits_by_target={passenger: 2},
        )
        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="accomplished_tactician",
        )
        self.assertIsNotNone(request)

        choose_pair = _first_option_with(
            request,
            lambda payload: (
                str(payload.get("target_unit_id", "") or "") == str(get_entity_id(passenger))
                and str(payload.get("transport_unit_id", "") or "") == str(get_entity_id(transport))
            ),
        )
        self.assertIsNotNone(choose_pair)
        resolve_decision_command(game, request, choose_pair.option_id, player_id=player.id)

        self.assertIs(passenger.embarked_in, transport)
        self.assertEqual(len(list(transport.transport_passengers or [])), 2)

        game._on_unit_shooting_resolved_emperors_children(
            attacker_unit=attacker,
            hits_by_target={passenger: 1},
        )
        second = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="accomplished_tactician",
        )
        self.assertIsNone(second)

    def test_heretek_adept_sets_damage_to_zero_once_per_battle_round(self):
        game, army, enemy_army, _player, _enemy_player = _build_game()
        game.turn = 2
        game.current_player_index = 0

        source = _make_unit("Lord Exultant", keywords=["CHARACTER", "INFANTRY"])
        vehicle = _make_unit("Predator", keywords=["VEHICLE"])
        attacker = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        army.add_unit(source)
        army.add_unit(vehicle)
        enemy_army.add_unit(attacker)
        source.deployed = True
        vehicle.deployed = True
        attacker.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        attacker.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, vehicle, attacker]

        Enhancement(
            id="000010006005",
            name="Heretek Adept",
            faction_id="EC",
            detachment="Rapid Evisceration",
            points=15,
            description="",
        ).apply_to_unit(source)

        parent = type("WargearStub", (), {"name": "Test Gun", "is_melee": lambda _self: False, "is_ranged": lambda _self: True})()
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "2",
                "description": "",
            },
            parent_wargear=parent,
        )
        target_model = vehicle.models[0]
        attacker_model = attacker.models[0]

        first_attack = {}
        first_save = profile._save_with_tracking(
            target_model,
            first_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(first_save.get("saved", True)))
        self.assertTrue(bool(first_attack.get("force_damage_zero", False)))
        first_damage = profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            first_attack,
            roll_value=2,
            allow_rerolls=False,
        )
        self.assertEqual(int(first_damage.get("damage_applied", -1)), 0)

        second_attack = {}
        second_save = profile._save_with_tracking(
            target_model,
            second_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(second_save.get("saved", True)))
        self.assertFalse(bool(second_attack.get("force_damage_zero", False)))

        game.turn = 3
        third_attack = {}
        third_save = profile._save_with_tracking(
            target_model,
            third_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(third_save.get("saved", True)))
        self.assertTrue(bool(third_attack.get("force_damage_zero", False)))


if __name__ == "__main__":
    unittest.main()
