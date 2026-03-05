from __future__ import annotations

import unittest
from types import SimpleNamespace

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
        faction_name: str = "Drukhari",
        keywords=None,
        faction_keywords=None,
        movement: int = 8,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Drukhari":
                faction_keywords = ["DRUKHARI"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": "4",
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
    faction_name: str = "Drukhari",
    keywords=None,
    faction_keywords=None,
    movement: int = 8,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Reaper's Wager")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Drukhari", control=PlayerControl.LOCAL, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    game.current_player_index = 0

    drukhari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, drukhari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


class TestDrukhariReapersWagerStratagems(unittest.TestCase):
    def test_scintillating_tempo_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000009782006")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "SCINTILLATING TEMPO")
        self.assertIn("overwatch", str(getattr(desc, "effect", "") or "").lower())

    def test_scintillating_tempo_queues_on_move_start_and_blocks_overwatch_until_end_of_turn(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_move_started", unit=source, action="move")
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SCINTILLATING TEMPO",
            unit=source,
            phase_name="Movement phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 1
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 0
        game.turn = 2
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_scintillating_tempo_queues_on_set_up(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        _place_unit(game, source, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_set_up", unit=source)
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

    def test_scintillating_tempo_applies_to_harlequins_units(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        harlequin = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(harlequin)
        enemy_army.add_unit(enemy)
        _place_unit(game, harlequin, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        game.event_system.publish("charge_declared", unit=harlequin, target_units=[enemy])
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SCINTILLATING TEMPO",
            unit=harlequin,
            phase_name="Charge phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertTrue(harlequin.is_overwatch_prevented_against(enemy, game=game))


if __name__ == "__main__":
    unittest.main()
