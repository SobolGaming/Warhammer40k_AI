from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        wounds: str = "2",
        move: str = "14",
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    wounds: str = "2",
    move: str = "14",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
            move=move,
            model_count=int(quantity),
        ),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Windrider Host")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10

    aeldari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, aeldari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    return str(name or "").strip().upper().replace("\u2019", "'")


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _ranged_profile(name: str = "Twin Shuriken Catapult"):
    return Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]


class TestAeldariWindriderHostStratagems(unittest.TestCase):
    def test_wind_of_blades_queues_and_grants_advance_fall_back_shoot_charge(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        riders = _make_unit(
            "Shining Spears",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "MOUNTED"],
            quantity=2,
        )
        aeldari_army.add_unit(riders)
        _place_unit(game, riders, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "WIND OF BLADES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=riders, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        self.assertTrue(bool(getattr(riders, "special_rules", {}).get("aeldari_wind_of_blades_active")))
        profile = _ranged_profile()
        self.assertTrue(riders.can_shoot_after_advance(profile))
        self.assertTrue(riders.can_charge_after_advance())

        riders.round_state.fell_back_this_round = True
        self.assertTrue(riders.can_shoot_after_fall_back(profile))
        self.assertTrue(riders.can_charge_after_fall_back())

    def test_daring_riders_queues_and_applies_reserves_setup_and_conditional_no_charge(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        riders = _make_unit(
            "Windriders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "MOUNTED", "WINDRIDERS"],
            quantity=1,
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(riders)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 16.0, 10.0)

        riders.deployed = False
        riders.reserve_status = "reserves"

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "DARING RIDERS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=riders, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(riders.has_deep_strike())
        self.assertEqual(float(riders.get_deep_strike_min_distance_override() or 0.0), 6.0)
        self.assertTrue(bool(getattr(riders, "special_rules", {}).get("aeldari_daring_riders_no_charge_if_within")))

        riders.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.place_unit(riders)
        riders._finalize_reserves_arrival(turn=game.turn, game_map=game.map)
        _set_phase(game, p1, "CHARGE_PHASE", 0)
        self.assertFalse(riders.can_declare_charge_against(enemy, game))

        sr = getattr(riders, "special_rules", {}) or {}
        self.assertNotIn("aeldari_daring_riders_no_charge_if_within", sr)

    def test_windrider_host_step4_stratagem_descriptors_registered(self):
        wind_of_blades = get_stratagem_tool_descriptor(stratagem_id="000009904004")
        self.assertIsNotNone(wind_of_blades)
        self.assertEqual(str(wind_of_blades.name), "Wind of Blades")
        self.assertEqual(int(wind_of_blades.cp_cost), 1)
        self.assertEqual(str(wind_of_blades.effect), "shoot_and_charge_after_advance_or_fall_back")

        daring_riders = get_stratagem_tool_descriptor(stratagem_id="000009904005")
        self.assertIsNotNone(daring_riders)
        self.assertEqual(str(daring_riders.name), "Daring Riders")
        self.assertEqual(int(daring_riders.cp_cost), 1)
        self.assertEqual(str(daring_riders.effect), "deep_strike_min_distance_override_with_conditional_no_charge")

        by_name_wind = get_stratagem_tool_descriptor(name="WIND OF BLADES")
        self.assertIsNotNone(by_name_wind)
        self.assertEqual(str(by_name_wind.stratagem_id), "000009904004")

        by_name_daring = get_stratagem_tool_descriptor(name="DARING RIDERS")
        self.assertIsNotNone(by_name_daring)
        self.assertEqual(str(by_name_daring.stratagem_id), "000009904005")


if __name__ == "__main__":
    unittest.main()
