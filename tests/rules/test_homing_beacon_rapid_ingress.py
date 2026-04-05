import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit


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
    return game, sm_player, enemy_player, sm_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


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


HOMING_BEACON_ABILITY = {
    "name": "Homing Beacon",
    "description": (
        "Once per battle, you can use the Rapid Ingress Stratagem for 0CP. The target must be set up within 3\" "
        "of the bearer's unit and more than 9\" away from all enemy units."
    ),
    "type": "Datasheet",
    "parameter": "",
}
DROP_POD_ASSAULT_ABILITY = {
    "name": "Drop Pod Assault",
    "description": (
        "This model must start the battle in Reserves and can be set up in the Reinforcements step of your first, "
        "second or third Movement phase, regardless of any mission rules. Any units embarked within this model must "
        "immediately disembark after it has been set up on the battlefield, and they must be set up more than 9\" "
        "away from all enemy models."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class TestHomingBeaconRapidIngress(unittest.TestCase):
    def test_drop_pod_assault_cannot_use_rapid_ingress_in_battle_round_one(self):
        game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
        game.turn = 1
        drop_pod = _make_unit("Drop Pod", abilities=[DROP_POD_ASSAULT_ABILITY])
        sm_army.add_unit(drop_pod)
        drop_pod.deployed = False
        drop_pod.reserve_status = "reserves"
        drop_pod._started_in_reserves = True

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1
        sm_player.command_points = 5
        enemy_player.command_points = 5

        used = sm_player.stratagems.use(
            "RAPID INGRESS",
            unit=drop_pod,
            phase_name="Movement phase",
            position=(12.0, 10.0, 0.0),
        )

        self.assertFalse(bool(used))
        self.assertFalse(bool(drop_pod.deployed))
        self.assertEqual(str(drop_pod.reserve_status or ""), "reserves")

    def test_homing_beacon_preview_and_apply_zero_cp_once_per_battle(self):
        _game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
        source = _make_unit("Phobos Unit", abilities=[HOMING_BEACON_ABILITY])
        target = _make_unit("Terminator Squad")
        sm_army.add_unit(source)
        sm_army.add_unit(target)
        target.deployed = False
        target.reserve_status = "reserves"

        rapid_ingress = _rapid_ingress_test_stratagem(cp_cost=1)

        preview = sm_player.preview_stratagem_cp_cost(
            rapid_ingress,
            target_unit=target,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Homing Beacon" in str(r) for r in list(preview.get("reasons", []) or [])))

        sm_player.set_next_optional_decision("HOMING_BEACON_RAPID_INGRESS", True)
        first = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=target)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("homing_beacon_rapid_ingress_use", False)))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("homing_beacon_rapid_ingress")))

        sm_player.set_next_optional_decision("HOMING_BEACON_RAPID_INGRESS", True)
        second = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=target)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("homing_beacon_rapid_ingress_use", False)))

    def test_homing_beacon_rapid_ingress_requires_position_within_three_of_source(self):
        game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
        source = _make_unit("Phobos Unit", abilities=[HOMING_BEACON_ABILITY])
        target = _make_unit("Terminator Squad")
        sm_army.add_unit(source)
        sm_army.add_unit(target)
        _place_unit(game, source, 10.0, 10.0)
        target.deployed = False
        target.reserve_status = "reserves"
        target._started_in_reserves = True
        target.special_rules["bearer_unit_deep_strike"] = True

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1  # Opponent's turn
        sm_player.command_points = 5
        enemy_player.command_points = 5

        sm_player.set_next_optional_decision("HOMING_BEACON_RAPID_INGRESS", True)
        used = sm_player.stratagems.use(
            "RAPID INGRESS",
            unit=target,
            phase_name="Movement phase",
            position=(30.0, 30.0, 0.0),
        )
        self.assertFalse(bool(used))
        self.assertFalse(bool(target.deployed))
        self.assertEqual(str(target.reserve_status or ""), "reserves")

    def test_homing_beacon_rapid_ingress_succeeds_when_position_is_anchored(self):
        game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
        source = _make_unit("Phobos Unit", abilities=[HOMING_BEACON_ABILITY])
        target = _make_unit("Terminator Squad")
        sm_army.add_unit(source)
        sm_army.add_unit(target)
        _place_unit(game, source, 10.0, 10.0)
        target.deployed = False
        target.reserve_status = "reserves"
        target._started_in_reserves = True
        target.special_rules["bearer_unit_deep_strike"] = True

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 1  # Opponent's turn
        sm_player.command_points = 5
        enemy_player.command_points = 5

        sm_player.set_next_optional_decision("HOMING_BEACON_RAPID_INGRESS", True)
        used = sm_player.stratagems.use(
            "RAPID INGRESS",
            unit=target,
            phase_name="Movement phase",
            position=(12.0, 10.0, 0.0),
        )
        self.assertTrue(bool(used))
        self.assertTrue(bool(target.deployed))
        self.assertEqual(str(target.reserve_status or ""), "deployed")


if __name__ == "__main__":
    unittest.main()
