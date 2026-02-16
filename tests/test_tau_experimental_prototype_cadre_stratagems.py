from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
        keywords=None,
        faction_keywords=None,
        wounds: str = "6",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "5",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "6") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Experimental Prototype Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tau_player = Player("Tau", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)

    tau_player.command_points = 10
    enemy_player.command_points = 10
    tau_army.configure_rule_managers(force=True)
    tau_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tau_player, enemy_player, tau_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
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


def test_automated_repair_drones_heals_in_either_players_command_phase():
    game, tau_player, enemy_player, tau_army, _enemy_army = _build_game()
    crisis = _make_unit(
        "Crisis Battlesuits",
        keywords=["INFANTRY", "BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
        wounds="6",
    )
    tau_army.add_unit(crisis)
    _deploy_unit(game, crisis, 10.0, 10.0)

    model = crisis.models[0]
    model.wounds = 2

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    with patch("warhammer40k_ai.rules.stratagems_tau_empire.dice_module.get_roll", return_value=2):
        ok = tau_player.stratagems.use(
            "AUTOMATED REPAIR DRONES",
            unit=crisis,
            phase_name="Command phase",
        )

    assert ok
    assert int(model.wounds or 0) == 5
    assert int(tau_player.command_points or 0) == 9


def test_automated_repair_drones_requires_wounded_battlesuit_model():
    game, tau_player, _enemy_player, tau_army, _enemy_army = _build_game()
    crisis = _make_unit(
        "Crisis Battlesuits",
        keywords=["INFANTRY", "BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
        wounds="6",
    )
    tau_army.add_unit(crisis)
    _deploy_unit(game, crisis, 10.0, 10.0)

    _set_phase(game, tau_player, "COMMAND_PHASE", 0)
    ok = tau_player.stratagems.use(
        "AUTOMATED REPAIR DRONES",
        unit=crisis,
        phase_name="Command phase",
    )
    assert not ok
    assert int(tau_player.command_points or 0) == 10


def test_automated_repair_drones_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000009984002")
    assert desc is not None
    assert desc.name == "Automated Repair Drones"
    assert desc.effect == "heal_battlesuit_model"
    assert str(desc.effect_params.get("heal_roll", "")).upper() == "D3+1"
