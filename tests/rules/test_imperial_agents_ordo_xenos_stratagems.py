import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        model_count=1,
        movement=6,
        toughness=4,
        wounds=3,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{str(name).lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
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
    name,
    *,
    faction_name="Imperial Agents",
    keywords=None,
    faction_keywords=None,
    model_count=1,
    movement=6,
    toughness=4,
    wounds=3,
):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    ia_army = Army.with_detachment("Imperial Agents", "Ordo Xenos Alien Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    ia_player.command_points = 10
    enemy_player.command_points = 10
    return game, ia_player, enemy_player, ia_army, enemy_army


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    for player in players:
        player.stratagems.refresh_available()


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    expected = str(name or "").strip().upper()
    for pending in list(getattr(stratagems, "_pending_reactions", []) or []):
        if str(pending.get("stratagem", "") or "").strip().upper() == expected:
            return pending
    return None


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


class TestImperialAgentsOrdoXenosStratagems(unittest.TestCase):
    def test_ordo_xenos_stratagem_descriptors_registered(self):
        expected = {
            "000009127002": ("Armour of Contempt", "defensive_ap_worsen"),
            "000009127003": ("Adaptive Tactics", "unit_specific_mission_tactic_override"),
            "000009127004": ("Hellfire Rounds", "ranged_anti_infantry_2_and_anti_monster_5_except_devastating_wounds"),
            "000009127005": ("Dragonfire Rounds", "ranged_assault_and_ignores_cover"),
            "000009127006": ("Kraken Rounds", "ranged_ap_and_range_bonus"),
            "000009127007": ("Rapid Tactical Relocation", "enter_strategic_reserves_with_temp_deep_strike"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(getattr(by_id, "name", "") or ""), expected_name)
            self.assertEqual(str(getattr(by_id, "effect", "") or ""), expected_effect)
            self.assertEqual(str(getattr(by_name, "name", "") or ""), expected_name)
            self.assertEqual(str(getattr(by_name, "effect", "") or ""), expected_effect)

    def test_rapid_tactical_relocation_queues_for_inquisitor_or_deathwatch_infantry_and_grants_next_turn_deep_strike(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        deathwatch = _make_unit(
            "Deathwatch Veterans",
            keywords=["INFANTRY", "DEATHWATCH"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        inquisitor = _make_unit(
            "Inquisitor",
            keywords=["INFANTRY", "CHARACTER", "INQUISITOR"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        voidsmen = _make_unit(
            "Voidsmen-at-Arms",
            keywords=["INFANTRY", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        deathwatch_bikers = _make_unit(
            "Deathwatch Bikers",
            keywords=["MOUNTED", "DEATHWATCH"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(deathwatch)
        ia_army.add_unit(inquisitor)
        ia_army.add_unit(voidsmen)
        ia_army.add_unit(deathwatch_bikers)
        enemy_army.add_unit(enemy)
        _place_unit(game, deathwatch, 10.0, 10.0)
        _place_unit(game, inquisitor, 14.0, 10.0)
        _place_unit(game, voidsmen, 18.0, 10.0)
        _place_unit(game, deathwatch_bikers, 22.0, 10.0)
        _place_unit(game, enemy, 30.0, 10.0)
        game.map.is_within_engagement_range = lambda _first, _second: False
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(ia_player.stratagems, "RAPID TACTICAL RELOCATION")
        self.assertIsNotNone(pending)

        candidates = list(pending.get("candidates") or [])
        self.assertIn(deathwatch, candidates)
        self.assertIn(inquisitor, candidates)
        self.assertNotIn(voidsmen, candidates)
        self.assertNotIn(deathwatch_bikers, candidates)

        ok = ia_player.stratagems.use("RAPID TACTICAL RELOCATION", unit=deathwatch, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(ia_player.command_points or 0), 9)
        self.assertTrue(bool(deathwatch.is_in_strategic_reserves()))
        self.assertNotIn(deathwatch, list(getattr(game.map, "units", []) or []))

        sr = dict(getattr(deathwatch, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("midgame_temp_deep_strike")))
        self.assertEqual(str(sr.get("midgame_temp_deep_strike_turn_owner", "") or ""), str(ia_player.id or ""))
        self.assertEqual(int(sr.get("midgame_temp_deep_strike_must_arrive_turn", 0) or 0), 2)

        game.turn = 2
        game.current_player_index = 0
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        self.assertTrue(bool(deathwatch.has_deep_strike()))
        self.assertTrue(bool(deathwatch.can_arrive_from_reserves(game.turn)))
        self.assertTrue(bool(deathwatch.must_arrive_from_reserves(game.turn)))

        evaluation = _evaluate_reserves_arrival_positions(
            game,
            deathwatch,
            _model_positions_for(deathwatch, (30.0, 30.0, 0.0)),
        )
        self.assertEqual(list(evaluation.get("errors") or []), [])


if __name__ == "__main__":
    unittest.main()
