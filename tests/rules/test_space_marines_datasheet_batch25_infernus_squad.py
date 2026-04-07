from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None) -> None:
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id is not None:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def test_infernus_squad_incendiary_terror_limits_targets_to_infantry_and_applies_minus_one():
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    infernus = _actual_unit("Infernus Squad", datasheet_id="000000126")
    infantry_target = _mock_unit("Infantry Target", keywords=["INFANTRY"])
    vehicle_target = _mock_unit("Vehicle Target", keywords=["VEHICLE"])

    infantry_target.models = [_make_model("Infantry", infantry_target)]
    vehicle_target.models = [_make_model("Vehicle", vehicle_target)]

    sm_army.units = [infernus]
    enemy_army.units = [infantry_target, vehicle_target]
    infernus.set_parent_army(sm_army)
    infantry_target.set_parent_army(enemy_army)
    vehicle_target.set_parent_army(enemy_army)
    game.rebuild_entity_registry()

    specs = infernus.unit_post_shoot_battleshock_specs()
    assert len(specs) == 1
    assert bool(specs[0].get("infantry_only")) is True
    assert int(specs[0].get("test_modifier", 0) or 0) == -1

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=infernus,
        hits_by_target={infantry_target: 1, vehicle_target: 1},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
    assert len(list(request.options or [])) == 1
    payload = request.options[0].payload or {}
    assert int(payload.get("battle_shock_test_modifier", 0) or 0) == -1
