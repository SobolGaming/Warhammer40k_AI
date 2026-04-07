from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import convert_mm_to_inches
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.model_geometry import resolve_model_geometry
from warhammer40k_ai.utility.deployment_special_rules import validate_aegis_defence_line_deployment_base


def _circle_part(part_id: str, diameter_mm: float, x_mm: float, y_mm: float, *, section_type: str) -> dict:
    return {
        "part_id": part_id,
        "shape": "circle",
        "radius": (convert_mm_to_inches(diameter_mm / 2.0), convert_mm_to_inches(diameter_mm / 2.0)),
        "offset": (convert_mm_to_inches(x_mm), convert_mm_to_inches(y_mm)),
        "facing": 0.0,
        "section_type": section_type,
    }


def _hull_part(part_id: str, length_mm: float, width_mm: float, x_mm: float, y_mm: float, *, section_type: str) -> dict:
    return {
        "part_id": part_id,
        "shape": "hull",
        "radius": (convert_mm_to_inches(length_mm / 2.0), convert_mm_to_inches(width_mm / 2.0)),
        "offset": (convert_mm_to_inches(x_mm), convert_mm_to_inches(y_mm)),
        "facing": 0.0,
        "section_type": section_type,
    }


def test_aegis_validator_accepts_seeded_geometry():
    resolved = resolve_model_geometry(
        datasheet_id="000002619",
        datasheet_name="Aegis Defence Line",
        model_name="Aegis Defence Line",
        unit_keywords=["Fortification"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    base = Base(resolved.base_type, resolved.radius)
    base.set_compound_parts(resolved.compound_parts)
    valid, reason = validate_aegis_defence_line_deployment_base(base)
    assert valid is True
    assert reason == ""


def test_aegis_validator_rejects_missing_platform():
    resolved = resolve_model_geometry(
        datasheet_id="000002619",
        datasheet_name="Aegis Defence Line",
        model_name="Aegis Defence Line",
        unit_keywords=["Fortification"],
        parsed_base_type=BaseType.HULL,
        parsed_radius=(1.0, 1.0),
    )
    base = Base(resolved.base_type, resolved.radius)
    parts_without_platform = [
        part for part in list(resolved.compound_parts or []) if str(part.get("part_id", "")).lower() != "platform"
    ]
    base.set_compound_parts(parts_without_platform)
    valid, reason = validate_aegis_defence_line_deployment_base(base)
    assert valid is False
    assert "exactly 1 platform" in reason


def test_aegis_validator_rejects_single_broken_shield_in_middle():
    base = Base(BaseType.HULL, (convert_mm_to_inches(115.0 / 2.0), convert_mm_to_inches(115.0 / 2.0)))
    base.set_compound_parts(
        [
            _circle_part("platform", 115.0, 0.0, 0.0, section_type="platform"),
            _hull_part("shield_left", 70.0, 10.0, -70.0, 0.0, section_type="shield"),
            _hull_part("broken_only", 70.0, 10.0, 0.0, 0.0, section_type="broken_shield"),
            _hull_part("shield_right", 70.0, 10.0, 70.0, 0.0, section_type="shield"),
        ]
    )
    valid, reason = validate_aegis_defence_line_deployment_base(base)
    assert valid is False
    assert "broken shield sections can only be in the middle as a pair" in reason


class _AegisDatasheet:
    def __init__(self):
        self.id = "000002619"
        self.name = "Aegis Defence Line"
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = ["Fortification"]
        self.faction_keywords = ["ASTRA MILITARUM"]
        self.datasheets_unit_composition = [{"description": "1 Aegis Defence Line"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 145}]
        self.datasheets_models = [
            {
                "M": "0",
                "T": "8",
                "Sv": "2",
                "W": "10",
                "Ld": "7",
                "OC": "0",
                "base_size": "Hull",
                "inv_sv": "-",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "ability_data": {
                    "name": "DEPLOYMENT",
                    "faction_id": "AM",
                    "description": (
                        "When this model is set up, it will consist of 1 platform section, up to 5 shield sections, "
                        "up to 2 broken shield sections, and up to 2 end sections. All sections must be connected to "
                        "each other to form a continuous defence line; the two broken shield sections can be placed "
                        "either at the end of the defence line, or in the middle of it such that both are within 1/2\" "
                        "of each other (in this case, these two sections count as being connected to each other). "
                        "All the sections that have been set up are then treated as a single model for all rules purposes."
                    ),
                    "legend": "",
                },
                "type": "Special",
                "parameter": "",
            }
        ]
        self.loadout = "This model has no weapons."


def test_single_model_deployment_enforces_aegis_compound_legality():
    army = Army.with_detachment("Astra Militarum", "Combined Regiment")
    enemy_army = Army.with_detachment("Space Marines", "Gladius Task Force")

    player = Player("AM", PlayerControl.LOCAL, army=army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    army.set_player(player)
    enemy_army.set_player(enemy_player)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    unit = Unit(_AegisDatasheet(), quantity=1)
    army.add_unit(unit)
    game.rebuild_entity_registry()

    game.is_position_wholly_in_deployment_zone = lambda _x, _y, _base, _pid: True
    game.is_position_in_enemy_deployment_zone = lambda _x, _y, _pid: False
    game.get_distance_to_enemy_deployment_zone = lambda _x, _y, _pid: 999.0
    game.get_distance_to_enemy_models = lambda _x, _y, _pid: 999.0

    model = unit.models[0]
    check = game.is_valid_single_model_deployment(model, 10.0, 10.0, 0.0, player.id)
    assert check["valid"] is True

    parts_without_platform = [
        part for part in list(model.model_base.get_compound_parts() or []) if str(part.get("part_id", "")).lower() != "platform"
    ]
    model.model_base.set_compound_parts(parts_without_platform)
    invalid = game.is_valid_single_model_deployment(model, 10.0, 10.0, 0.0, player.id)
    assert invalid["valid"] is False
    assert "exactly 1 platform" in str(invalid["reason"])


def test_unit_deployment_position_enforces_aegis_compound_legality():
    army = Army.with_detachment("Astra Militarum", "Combined Regiment")
    enemy_army = Army.with_detachment("Space Marines", "Gladius Task Force")

    player = Player("AM", PlayerControl.LOCAL, army=army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    army.set_player(player)
    enemy_army.set_player(enemy_player)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    unit = Unit(_AegisDatasheet(), quantity=1)
    army.add_unit(unit)
    game.rebuild_entity_registry()

    game.is_position_wholly_in_deployment_zone = lambda _x, _y, _base, _pid: True
    game.is_position_in_enemy_deployment_zone = lambda _x, _y, _pid: False
    game.get_distance_to_enemy_deployment_zone = lambda _x, _y, _pid: 999.0
    game.get_distance_to_enemy_models = lambda _x, _y, _pid: 999.0

    unit.calculate_model_positions = (
        lambda x, y, _map, avoid_friendly_units=False, boundary_repulsors=None: [(x, y, 0.0, 0.0)]
    )

    assert game.is_valid_deployment_position(unit, 10.0, 10.0, player.id) is True

    model = unit.models[0]
    parts_without_platform = [
        part for part in list(model.model_base.get_compound_parts() or []) if str(part.get("part_id", "")).lower() != "platform"
    ]
    model.model_base.set_compound_parts(parts_without_platform)

    assert game.is_valid_deployment_position(unit, 10.0, 10.0, player.id) is False
