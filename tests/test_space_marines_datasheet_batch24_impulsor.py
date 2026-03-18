from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _mock_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, abilities=abilities, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_player(*units: Unit) -> tuple[Player, Army]:
    army = Army("Space Marines", detachment_type="Other")
    army.faction_id = "SM"
    army.units = list(units)
    for unit in units:
        unit.set_parent_army(army)
    player = Player("Space Marines", control=PlayerControl.LOCAL, army=army)
    player.set_game(SimpleNamespace(turn=1))
    return player, army


def _impulsor_with_orbital_comms_array() -> Unit:
    return _mock_unit(
        "Impulsor",
        abilities=[
            {
                "name": "Orbital Comms Array (Aura)",
                "description": 'While a friendly ADEPTUS ASTARTES unit is within 6" of the bearer, each time you target that unit with a Stratagem, roll one D6: on a 5+, you gain 1CP.',
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )


def test_impulsor_orbital_comms_array_parses_as_targeted_stratagem_cp_refund_aura():
    impulsor = _impulsor_with_orbital_comms_array()

    specs = list(impulsor.special_rules.get("stratagem_target_cp_refund_aura", []) or [])

    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("roll_min", 0) or 0) == 5
    assert int(spec.get("cp_gain", 0) or 0) == 1
    assert int(spec.get("range", 0) or 0) == 6
    assert str(spec.get("keyword", "") or "").upper() == "ADEPTUS ASTARTES"


def test_impulsor_orbital_comms_array_refunds_cp_for_nearby_adeptus_astartes_target():
    impulsor = _impulsor_with_orbital_comms_array()
    target = _mock_unit("Target Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["SM"])
    impulsor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    player, _army = _make_player(impulsor, target)
    player.command_points = 2
    player._pending_stratagem_target_unit_id = str(get_entity_id(target) or "")
    player._pending_stratagem_name = "Rapid Fire"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
        ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

    assert ok is True
    assert int(player.command_points or 0) == 2


def test_impulsor_orbital_comms_array_does_not_refund_cp_out_of_range():
    impulsor = _impulsor_with_orbital_comms_array()
    target = _mock_unit("Target Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["SM"])
    impulsor.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    player, _army = _make_player(impulsor, target)
    player.command_points = 2
    player._pending_stratagem_target_unit_id = str(get_entity_id(target) or "")
    player._pending_stratagem_name = "Rapid Fire"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
        ok = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

    assert ok is True
    assert int(player.command_points or 0) == 1
