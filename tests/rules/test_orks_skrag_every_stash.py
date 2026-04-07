from __future__ import annotations

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Orks",
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        model_count: int = 1,
        objective_control: int = 1,
    ) -> None:
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    *,
    faction_name: str = "Orks",
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    model_count: int = 1,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            model_count=model_count,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * float(idx)), float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]) -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Da Big Hunt")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    game.map.units = list(ork_units or []) + list(enemy_units or [])
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player


def _make_objective(name: str, x: float, y: float, *, radius: float = 3.0) -> Objective:
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _game: False,
        location=ObjectivePoint(float(x), float(y), 0.0, control_radius=float(radius)),
    )


def _apply_skrag(unit: Unit) -> None:
    Enhancement(
        id="000008868004",
        name="Skrag Every Stash!",
        faction_id="ORK",
        detachment="Da Big Hunt",
        points=25,
        description="",
    ).apply_to_unit(unit)


def test_skrag_every_stash_applies_sticky_control_at_end_of_command_phase():
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    _set_unit_position(bearer, 0.0, 0.0)
    game, ork_player, _enemy_player = _build_game(ork_units=[bearer], enemy_units=[])
    objective = _make_objective("Primary", 0.0, 0.0)
    game.map.objectives = [objective]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert objective.location.sticky_controller is ork_player
    assert str(getattr(objective.location, "sticky_source", "") or "") == "unit_sticky_objective"


def test_skrag_every_stash_does_not_apply_at_end_of_wrong_phase():
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    _set_unit_position(bearer, 0.0, 0.0)
    game, ork_player, _enemy_player = _build_game(ork_units=[bearer], enemy_units=[])
    objective = _make_objective("Primary", 0.0, 0.0)
    game.map.objectives = [objective]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    assert objective.location.sticky_controller is None


def test_skrag_every_stash_requires_bearer_model_in_range_not_other_models_in_attached_unit():
    bodyguard = _make_unit(
        "Beast Snagga Boyz",
        keywords=["INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        model_count=3,
    )
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    game, ork_player, _enemy_player = _build_game(ork_units=[bodyguard, bearer], enemy_units=[])
    bearer.attach_to_unit(bodyguard)
    _set_unit_position(bodyguard, 0.0, 0.0)
    _set_unit_position(bearer, 10.0, 0.0)
    objective = _make_objective("Primary", 0.0, 0.0)
    game.map.objectives = [objective]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert objective.location.sticky_controller is None


def test_skrag_every_stash_requires_objective_to_be_controlled_by_you():
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        objective_control=1,
    )
    enemy = _make_unit(
        "Enemy Captain",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        objective_control=3,
    )
    _set_unit_position(bearer, 0.0, 0.0)
    _set_unit_position(enemy, 0.0, 0.0)
    game, ork_player, _enemy_player = _build_game(ork_units=[bearer], enemy_units=[enemy])
    objective = _make_objective("Primary", 0.0, 0.0)
    game.map.objectives = [objective]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert objective.location.sticky_controller is None


def test_skrag_every_stash_does_not_leak_to_unrelated_objectives():
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    other_orks = _make_unit(
        "Boyz",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=5,
    )
    _set_unit_position(bearer, 0.0, 0.0)
    _set_unit_position(other_orks, 12.0, 0.0)
    game, ork_player, _enemy_player = _build_game(ork_units=[bearer, other_orks], enemy_units=[])
    primary = _make_objective("Primary", 0.0, 0.0)
    secondary = _make_objective("Secondary", 12.0, 0.0)
    game.map.objectives = [primary, secondary]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert primary.location.sticky_controller is ork_player
    assert secondary.location.sticky_controller is None


def test_skrag_every_stash_sticky_control_breaks_when_enemy_later_controls_objective():
    bearer = _make_unit(
        "Beastboss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        objective_control=1,
    )
    enemy = _make_unit(
        "Enemy Troops",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        objective_control=2,
    )
    _set_unit_position(bearer, 0.0, 0.0)
    _set_unit_position(enemy, 24.0, 0.0)
    game, ork_player, enemy_player = _build_game(ork_units=[bearer], enemy_units=[enemy])
    objective = _make_objective("Primary", 0.0, 0.0)
    game.map.objectives = [objective]

    _apply_skrag(bearer)

    game.event_system.publish("phase_end", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert objective.location.sticky_controller is ork_player

    _set_unit_position(bearer, 24.0, 0.0)
    objective.location.update_control(game)
    assert objective.location.sticky_controller is ork_player
    assert objective.location.controlling_player is ork_player

    _set_unit_position(enemy, 0.0, 0.0)
    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert objective.location.sticky_controller is None
    assert objective.location.controlling_player is enemy_player
