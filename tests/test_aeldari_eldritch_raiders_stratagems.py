from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        wounds: str = "2",
        move: str = "8",
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
    move: str = "8",
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

    aeldari_army = Army("Aeldari", "Eldritch Raiders")
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
    text = str(name or "").strip().upper()
    return text.replace("\u2019", "'")


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


class TestAeldariEldritchRaidersStratagems(unittest.TestCase):
    def test_yriels_example_reacts_and_grants_fight_phase_fnp(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        defender = _make_unit(
            "Aeldari Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[defender])
        pending = _pending_by_name(p1.stratagems, "YRIEL")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=defender,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        overrides = list((defender.special_rules or {}).get("defensive_fnp_overrides", []) or [])
        self.assertTrue(overrides)
        self.assertEqual(int(overrides[0].get("value", 0) or 0), 5)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        overrides_after = list((defender.special_rules or {}).get("defensive_fnp_overrides", []) or [])
        self.assertFalse(overrides_after)

    def test_withdraw_and_reinforce_queues_and_returns_destroyed_models(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        anhrathe = _make_unit(
            "Corsair Voidreavers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ANHRATHE", "INFANTRY"],
            quantity=3,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )

        destroyed_model = anhrathe.models.pop()
        destroyed_model.wounds = 0
        anhrathe.models_lost.append(destroyed_model)

        aeldari_army.add_unit(anhrathe)
        enemy_army.add_unit(enemy)
        _place_unit(game, anhrathe, 10.0, 10.0)
        _place_unit(game, enemy, 30.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "WITHDRAW AND REINFORCE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=anhrathe, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(str(getattr(anhrathe, "reserve_status", "") or ""), "strategic_reserves")
        self.assertNotIn(anhrathe, list(getattr(game.map, "units", []) or []))

        self.assertIn(destroyed_model, list(getattr(anhrathe, "models", []) or []))
        self.assertNotIn(destroyed_model, list(getattr(anhrathe, "models_lost", []) or []))
        self.assertEqual(len(list(getattr(anhrathe, "models", []) or [])), 3)

    def test_eldritch_raiders_stratagem_descriptors_registered(self):
        yriel = get_stratagem_tool_descriptor(stratagem_id="000010700004")
        self.assertIsNotNone(yriel)
        self.assertEqual(str(yriel.name), "Yriel's Example")
        self.assertEqual(int(yriel.cp_cost), 1)
        self.assertEqual(str(yriel.effect), "feel_no_pain")

        withdraw = get_stratagem_tool_descriptor(stratagem_id="000010700007")
        self.assertIsNotNone(withdraw)
        self.assertEqual(str(withdraw.name), "Withdraw and Reinforce")
        self.assertEqual(int(withdraw.cp_cost), 1)
        self.assertEqual(str(withdraw.effect), "enter_strategic_reserves_and_return_destroyed_models")

        by_name = get_stratagem_tool_descriptor(name="WITHDRAW AND REINFORCE")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(by_name.stratagem_id), "000010700007")


if __name__ == "__main__":
    unittest.main()
