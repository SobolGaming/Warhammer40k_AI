from __future__ import annotations

from types import SimpleNamespace

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
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Synaptic Nexus")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


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


def test_override_instincts_grants_shoot_and_charge_after_fall_back():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Warrior Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    unit.round_state.fell_back_this_round = True

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "OVERRIDE INSTINCTS",
        unit=unit,
        phase_name="Movement phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    profile = Wargear(
        {
            "name": "Bio Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    assert unit.can_shoot_after_fall_back(profile) is True
    assert unit.can_charge_after_fall_back() is True


def test_override_instincts_rejects_units_that_did_not_fall_back():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Warrior Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    unit.round_state.fell_back_this_round = False

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "OVERRIDE INSTINCTS",
        unit=unit,
        phase_name="Movement phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10


def test_synaptic_nexus_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000008556007")
    assert descriptor is not None
    assert descriptor.name == "Override Instincts"
    assert descriptor.effect == "eligible_to_shoot_and_charge_after_fall_back"
    assert bool(descriptor.effect_params.get("requires_synapse_range", False)) is True
