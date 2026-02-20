from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
        move: str = "8",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
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
        ),
        quantity=int(quantity),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Ghosts of the Webway")
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


def _melee_profile(*, strength: int = 4, ap: int = 0, damage: int = 2, name: str = "Enemy Blade"):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestAeldariGhostsOfTheWebwayStratagems(unittest.TestCase):
    def test_exit_the_stage_queues_and_places_harlequins_unit_in_strategic_reserves(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        harlequins = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "INFANTRY"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(harlequins)
        enemy_army.add_unit(enemy)
        _place_unit(game, harlequins, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "EXIT THE STAGE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=harlequins, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(str(getattr(harlequins, "reserve_status", "") or ""), "strategic_reserves")
        self.assertNotIn(harlequins, list(getattr(game.map, "units", []) or []))

    def test_heroes_fall_queues_and_grants_fight_on_death_on_four_plus(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        target = _make_unit(
            "Harlequins Players",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "INFANTRY"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = _pending_by_name(p1.stratagems, "HEROES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=target,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        rule = target.get_melee_fight_on_death_after_attacks_rule()
        self.assertTrue(bool(rule))
        self.assertEqual(int(rule.get("threshold", 0) or 0), 4)
        self.assertIn("HEROES", str(rule.get("source", "")).upper())

        model = target.models[0]
        target.round_state.fought_this_phase = False
        target._last_destroyed_by_weapon_profile = _melee_profile(name="Enemy Blade")
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
            model._wounds = 0
            target._handle_model_destroyed(model, game.map)

        pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending_models)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIsNone(target.get_melee_fight_on_death_after_attacks_rule())

    def test_ghosts_of_the_webway_step1_stratagem_descriptors_registered(self):
        heroes = get_stratagem_tool_descriptor(stratagem_id="000009916003")
        self.assertIsNotNone(heroes)
        self.assertEqual(str(heroes.name), "Heroes' Fall")
        self.assertEqual(int(heroes.cp_cost), 1)
        self.assertEqual(str(heroes.effect), "fight_on_death_after_attacks")

        exit_stage = get_stratagem_tool_descriptor(stratagem_id="000009916007")
        self.assertIsNotNone(exit_stage)
        self.assertEqual(str(exit_stage.name), "Exit the Stage")
        self.assertEqual(int(exit_stage.cp_cost), 1)
        self.assertEqual(str(exit_stage.effect), "enter_strategic_reserves")

        by_name = get_stratagem_tool_descriptor(name="HEROES' FALL")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(by_name.stratagem_id), "000009916003")


if __name__ == "__main__":
    unittest.main()
