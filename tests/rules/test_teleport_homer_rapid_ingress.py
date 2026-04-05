import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float):
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Space Marines",
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None):
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=["INFANTRY"],
            faction_keywords=["IMPERIUM"],
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    sm_army = Army("Space Marines", "Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    sm_player.command_points = 5
    enemy_player.command_points = 5
    game.deployment_zones = {
        sm_player.id: {"mission_zones": [_RectZone(0.0, 30.0, 0.0, 44.0)]},
        enemy_player.id: {"mission_zones": [_RectZone(30.0, 60.0, 0.0, 44.0)]},
    }
    return game, sm_player, enemy_player, sm_army, enemy_army


def _rapid_ingress_test_stratagem(*, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id="test_rapid_ingress",
        name="Rapid Ingress",
        type="Core - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Opponent's turn",
        phase="Movement phase",
        detachment="",
        faction_id="CORE",
    )


def _find_pick_point_request(game: Game, *, ability: str):
    ability_key = str(ability or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
            continue
        return req
    return None


def _option_for_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


TELEPORT_HOMER_ABILITY = {
    "name": "Teleport Homer",
    "description": (
        "At the start of the battle, you can set up one Teleport Homer token for this unit anywhere on the battlefield "
        "that is not in your opponent's deployment zone. If you do, once per battle, you can target this unit with the "
        "Rapid Ingress Stratagem for 0CP, but when resolving that Stratagem, you must set this unit up within 3\" of that "
        "token and not within 9\" of any enemy models. That token is then removed."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class TestTeleportHomerRapidIngress(unittest.TestCase):
    def test_teleport_homer_pick_point_rejects_enemy_zone_and_accepts_valid_point(self):
        game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
        source = _make_unit("Terminator Squad", abilities=[TELEPORT_HOMER_ABILITY])
        sm_army.add_unit(source)
        game.rebuild_entity_registry()

        game._apply_teleport_homer_declarations()
        request = _find_pick_point_request(game, ability="teleport_homer_marker_placement")
        self.assertIsNotNone(request)
        confirm = _option_for_action(request, "confirm")
        self.assertIsNotNone(confirm)

        invalid = resolve_decision_command(
            game,
            request,
            confirm.option_id,
            result_payload={"point": [50.0, 10.0]},
            player_id=sm_player.id,
        )
        self.assertFalse(bool(getattr(invalid, "ok", False)))
        self.assertTrue(any("deployment zone" in str(err).lower() for err in list(getattr(invalid, "errors", []) or [])))

        request_after_invalid = _find_pick_point_request(game, ability="teleport_homer_marker_placement")
        self.assertIsNotNone(request_after_invalid)
        confirm_after_invalid = _option_for_action(request_after_invalid, "confirm")
        self.assertIsNotNone(confirm_after_invalid)
        valid = resolve_decision_command(
            game,
            request_after_invalid,
            confirm_after_invalid.option_id,
            result_payload={"point": [20.0, 10.0]},
            player_id=sm_player.id,
        )
        self.assertTrue(bool(getattr(valid, "ok", False)))
        marker = source.get_teleport_homer_marker_point()
        self.assertIsNotNone(marker)
        self.assertEqual(tuple(marker), (20.0, 10.0, 0.0))

    def test_teleport_homer_pick_point_skip_marks_declined(self):
        game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
        source = _make_unit("Terminator Squad", abilities=[TELEPORT_HOMER_ABILITY])
        sm_army.add_unit(source)
        game.rebuild_entity_registry()

        game._apply_teleport_homer_declarations()
        request = _find_pick_point_request(game, ability="teleport_homer_marker_placement")
        self.assertIsNotNone(request)
        skip = _option_for_action(request, "skip")
        self.assertIsNotNone(skip)

        resolved = resolve_decision_command(
            game,
            request,
            skip.option_id,
            result_payload={},
            player_id=sm_player.id,
        )
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertTrue(bool(source.special_rules.get("teleport_homer_marker_declined", False)))
        self.assertIsNone(source.get_teleport_homer_marker_point())

    def test_teleport_homer_rapid_ingress_enforces_marker_anchor_and_consumes_token(self):
        game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
        target = _make_unit("Terminator Squad", abilities=[TELEPORT_HOMER_ABILITY])
        sm_army.add_unit(target)
        target.deployed = False
        target.reserve_status = "reserves"
        target._started_in_reserves = True
        target.special_rules["bearer_unit_deep_strike"] = True
        self.assertTrue(bool(target.set_teleport_homer_marker_point((10.0, 10.0, 0.0), source="Teleport Homer")))

        rapid_ingress = _rapid_ingress_test_stratagem(cp_cost=1)
        preview = sm_player.preview_stratagem_cp_cost(
            rapid_ingress,
            target_unit=target,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Teleport Homer" in str(r) for r in list(preview.get("reasons", []) or [])))

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1  # Opponent's turn
        sm_player.command_points = 5
        enemy_player.command_points = 5

        sm_player.set_next_optional_decision("TELEPORT_HOMER_RAPID_INGRESS", True)
        invalid = sm_player.stratagems.use(
            "RAPID INGRESS",
            unit=target,
            phase_name="Movement phase",
            position=(30.0, 30.0, 0.0),
        )
        self.assertFalse(bool(invalid))
        self.assertIsNotNone(target.get_teleport_homer_marker_point())
        self.assertFalse(bool(target.has_used_unit_once_per_battle("teleport_homer_rapid_ingress")))

        sm_player.set_next_optional_decision("TELEPORT_HOMER_RAPID_INGRESS", True)
        valid = sm_player.stratagems.use(
            "RAPID INGRESS",
            unit=target,
            phase_name="Movement phase",
            position=(12.0, 10.0, 0.0),
        )
        self.assertTrue(bool(valid))
        self.assertTrue(bool(target.deployed))
        self.assertEqual(str(target.reserve_status or ""), "deployed")
        self.assertTrue(bool(target.has_used_unit_once_per_battle("teleport_homer_rapid_ingress")))
        self.assertIsNone(target.get_teleport_homer_marker_point())


if __name__ == "__main__":
    unittest.main()
