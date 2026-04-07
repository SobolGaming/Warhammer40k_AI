import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, model_count: int = 1):
        count = max(1, int(model_count or 1))
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "14",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "60x35mm",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    datasheet = _MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game(*, size: BattlefieldSize = BattlefieldSize.STRIKE_FORCE):
    aeldari_army = Army.with_detachment("Aeldari", "Windrider Host")
    aeldari_army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "SM"

    aeldari_player = Player("Aeldari", control=PlayerControl.REMOTE, army=aeldari_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size), players=[aeldari_player, enemy_player])
    return game, aeldari_army, enemy_army, aeldari_player, enemy_player


def _ride_the_wind_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "ride_the_wind_end_of_opponent_turn"
    ]


class TestAeldariWindriderHostDetachment(unittest.TestCase):
    def test_windriders_gain_battleline_keyword(self):
        _game, aeldari_army, _enemy_army, _aeldari_player, _enemy_player = _build_game()
        windriders = _make_unit(
            "Windriders",
            keywords=["MOUNTED", "WINDRIDERS"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        vyper = _make_unit(
            "Vyper",
            keywords=["MOUNTED", "VYPER"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )

        aeldari_army.add_unit(windriders)
        aeldari_army.add_unit(vyper)

        windrider_keywords = {str(k).strip().lower() for k in list(getattr(windriders, "keywords", []) or [])}
        vyper_keywords = {str(k).strip().lower() for k in list(getattr(vyper, "keywords", []) or [])}
        self.assertIn("battleline", windrider_keywords)
        self.assertNotIn("battleline", vyper_keywords)

    def test_ride_the_wind_reserves_allocation_becomes_strategic_reserves(self):
        game, aeldari_army, _enemy_army, _aeldari_player, _enemy_player = _build_game()
        mounted = _make_unit(
            "Shining Spears",
            keywords=["MOUNTED"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        aeldari_army.add_unit(mounted)
        game.map.units = [mounted]

        decision_key = str(getattr(mounted, "_id", "") or "")
        self.assertTrue(decision_key)
        applied = game.apply_reserves_decisions(aeldari_army, {decision_key: "reserves"})
        self.assertTrue(applied)
        self.assertTrue(mounted.is_in_strategic_reserves())
        self.assertTrue(aeldari_army._ride_the_wind_allows_standard_reserves(mounted))
        self.assertTrue(mounted.can_arrive_from_reserves(1))

    def test_ride_the_wind_queues_single_multiselect_request(self):
        game, aeldari_army, enemy_army, _aeldari_player, enemy_player = _build_game(size=BattlefieldSize.STRIKE_FORCE)
        rider_a = _make_unit("Rider A", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        rider_b = _make_unit("Rider B", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        vyper = _make_unit("Vyper", keywords=["VYPER"], faction_keywords=["AELDARI", "ASURYANI"])
        engaged_rider = _make_unit("Engaged Rider", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])

        _set_model_location(rider_a, x=4.0, y=4.0)
        _set_model_location(rider_b, x=10.0, y=4.0)
        _set_model_location(vyper, x=16.0, y=4.0)
        _set_model_location(engaged_rider, x=22.0, y=4.0)
        _set_model_location(enemy, x=22.0, y=4.0)

        for unit in (rider_a, rider_b, vyper, engaged_rider):
            aeldari_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        game.map.units = [rider_a, rider_b, vyper, engaged_rider, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

        requests = _ride_the_wind_requests(game)
        self.assertEqual(len(requests), 1)
        req = requests[0]
        ctx = dict(getattr(req, "context", {}) or {})
        allowed_ids = set(str(v) for v in list(ctx.get("allowed_unit_ids") or []))

        self.assertEqual(int(ctx.get("max_units", 0) or 0), 2)
        self.assertIn(str(get_entity_id(rider_a)), allowed_ids)
        self.assertIn(str(get_entity_id(rider_b)), allowed_ids)
        self.assertIn(str(get_entity_id(vyper)), allowed_ids)
        self.assertNotIn(str(get_entity_id(engaged_rider)), allowed_ids)
        self.assertEqual(str(ctx.get("skip_label", "")), "None (do not use this ability)")

    def test_ride_the_wind_selection_moves_units_and_prevents_repeat_prompt_same_turn(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = _build_game()
        rider_a = _make_unit("Rider A", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        rider_b = _make_unit("Rider B", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        _set_model_location(rider_a, x=6.0, y=6.0)
        _set_model_location(rider_b, x=12.0, y=6.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        aeldari_army.add_unit(rider_a)
        aeldari_army.add_unit(rider_b)
        enemy_army.add_unit(enemy)
        game.map.units = [rider_a, rider_b, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _ride_the_wind_requests(game)[0]
        confirm_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "confirm"
        )
        resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={"unit_ids": [str(get_entity_id(rider_a))]},
            player_id=aeldari_player.id,
        )

        self.assertTrue(rider_a.is_in_strategic_reserves())
        self.assertFalse(rider_b.is_in_strategic_reserves())

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_ride_the_wind_requests(game)), 0)

    def test_ride_the_wind_skip_marks_phase_resolved(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = _build_game()
        rider = _make_unit("Rider", keywords=["MOUNTED"], faction_keywords=["AELDARI", "ASURYANI"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        _set_model_location(rider, x=8.0, y=8.0)
        _set_model_location(enemy, x=30.0, y=30.0)

        aeldari_army.add_unit(rider)
        enemy_army.add_unit(enemy)
        game.map.units = [rider, enemy]
        game.rebuild_entity_registry()

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _ride_the_wind_requests(game)[0]
        skip_option = next(
            opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "skip"
        )
        resolve_decision_command(
            game,
            request,
            skip_option.option_id,
            result_payload={"skipped": True},
            player_id=aeldari_player.id,
        )

        self.assertFalse(rider.is_in_strategic_reserves())
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        self.assertEqual(len(_ride_the_wind_requests(game)), 0)


if __name__ == "__main__":
    unittest.main()
