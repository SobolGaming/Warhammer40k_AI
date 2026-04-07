from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.movement import _validate_move_unit
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        movement: int = 5,
        attached_to=None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    movement: int = 5,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            movement=movement,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _build_game(*, necron_units: list[Unit], enemy_units: list[Unit]) -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army.with_detachment("Necrons", "Cursed Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_idx = 1
    game.current_player_index = 1
    game.battle_round_starting_player_index = 1
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    for unit in list(necron_units or []):
        necron_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
    necron_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    game.map.units = list(necron_units or []) + list(enemy_units or [])
    game.rebuild_entity_registry()
    return game, necron_army, enemy_army, necron_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Cursed Legion",
        points=20,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    getter = getattr(unit, "_get_enhancement_bearer_model", None)
    if callable(getter):
        model = getter()
        if model is not None:
            return model
    models = list(getattr(unit, "models", []) or [])
    return models[0] if models else None


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _make_ranged_profile(*, name: str = "Gauss Blaster", hit: str = "3+") -> WargearProfile:
    parent = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": hit,
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return parent.profiles["default"]


def _make_cursed_circlet_move_request(
    unit: Unit,
    *,
    max_distance: int,
    destination: tuple[float, float, float],
) -> tuple[DecisionRequest, DecisionResult]:
    option = DecisionOption.create(
        "Confirm",
        payload={"unit_id": get_entity_id(unit), "movement_type": "reactive", "action": "confirm"},
    )
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="player-1",
        options=[option],
        context={
            "unit_id": get_entity_id(unit),
            "movement_type": "reactive",
            "max_distance": int(max_distance),
            "reactive_move_kind": "cursed_circlet",
            "reactive_move_movement_type": "cursed_circlet",
            "reactive_move_allow_engagement_range": True,
            "cursed_circlet_closest_enemy_exclude_keywords_any": ["AIRCRAFT"],
        },
    )
    model = unit.models[0]
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(model),
                    "position": [float(destination[0]), float(destination[1]), float(destination[2])],
                    "facing": 0.0,
                }
            ]
        },
    )
    return request, result


def test_cursed_legion_enhancement_descriptors_registered():
    expected = {
        "000010668002": ("Destroyer Ankh", "bearer_keyword_and_bearer_unit_move_bonus_with_bearer_melee_attacks_bonus"),
        "000010668003": ("Murdermind", "bearer_keyword_move_bonus_and_attach_to_destroyer_cult_unit"),
        "000010668004": ("Mark of the Nekrosor", "bearer_unit_hit_roll_bonus"),
        "000010668005": ("Cursed Circlet", "post_enemy_shooting_destroyed_models_surge_move"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_destroyer_ankh_grants_keyword_move_bonus_and_drops_move_bonus_when_bearer_dies():
    leader = _make_unit(
        "Overlord",
        "necron-overlord",
        keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Lychguard",
        "necron-lychguard",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=2,
        movement=5,
    )
    _game, necron_army, enemy_army, _player, _enemy_player = _build_game(
        necron_units=[leader, bodyguard],
        enemy_units=[],
    )
    del enemy_army
    del necron_army
    _attach_leader(bodyguard, leader)
    _apply_enhancement(
        leader,
        enhancement_id="000010668002",
        name="Destroyer Ankh",
        description=(
            "Catacomb Command Barge or Overlord model only. The bearer has the Destroyer Cult keyword. "
            "Add 2\" to the Move characteristic of models in the bearer's unit and add 2 to the Attacks "
            "characteristic of melee weapons equipped by the bearer."
        ),
    )

    bodyguard._refresh_bearer_unit_common_modifiers()
    bearer = _bearer_model(leader)
    assert bearer is not None
    assert "DESTROYER CULT" in {str(value or "").upper() for value in list(getattr(bearer, "keywords", []) or [])}
    assert int(bodyguard.models[0].movement or 0) == 7
    assert int(getattr(leader, "special_rules", {}).get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 2

    bearer.wounds = 0
    bodyguard._refresh_bearer_unit_common_modifiers()
    assert int(bodyguard.models[0].movement or 0) == 5


def test_murdermind_grants_keyword_move_bonus_and_destroyer_cult_attachment_override():
    cryptek = _make_unit(
        "Chronomancer",
        "necron-chronomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        attached_to=["necron-immortals"],
        movement=5,
    )
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        "necron-skorpekh-destroyers",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
        model_count=3,
        wounds=3,
    )
    warriors = _make_unit(
        "Necron Warriors",
        "necron-warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        model_count=10,
        wounds=1,
    )
    character_destroyer = _make_unit(
        "Skorpekh Lord",
        "necron-skorpekh-lord",
        keywords=["CHARACTER", "DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    _game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[cryptek, destroyers, warriors, character_destroyer],
        enemy_units=[],
    )

    _apply_enhancement(
        cryptek,
        enhancement_id="000010668003",
        name="Murdermind",
        description=(
            "Cryptek model only. The bearer has the Destroyer Cult keyword and during the Declare Battle "
            "Formations step, the bearer can be attached to a DESTROYER CULT unit (excluding CHARACTER units). "
            "If you do, the bearer's unit cannot contain any models without the DESTROYER CULT keyword. Add 3\" "
            "to the Move characteristic of the bearer."
        ),
    )

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    assert "DESTROYER CULT" in {str(value or "").upper() for value in list(getattr(bearer, "keywords", []) or [])}
    assert int(bearer.movement or 0) == 8
    assert cryptek.can_attach_to(destroyers) is True
    assert cryptek.can_attach_to(warriors) is False
    assert cryptek.can_attach_to(character_destroyer) is False

    cryptek.attach_to_unit(destroyers)
    assert cryptek.attached_to is destroyers
    assert cryptek in list(getattr(destroyers, "attached_leaders", []) or [])


def test_mark_of_the_nekrosor_adds_hit_bonus_for_bearers_unit_attacks():
    bearer_unit = _make_unit(
        "Skorpekh Lord",
        "necron-mark-bearer",
        keywords=["CHARACTER", "DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[bearer_unit],
        enemy_units=[enemy],
    )
    _set_unit_location(bearer_unit, x=0.0, y=0.0)
    _set_unit_location(enemy, x=12.0, y=0.0)
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer_unit,
        enhancement_id="000010668004",
        name="Mark of the Nekrosor",
        description="Destroyer Cult model only. Each time a model in the bearer's unit makes an attack, add 1 to the Hit roll.",
    )

    profile = _make_ranged_profile()
    hit = profile._hit_target_with_tracking(
        enemy,
        bearer_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Mark of the Nekrosor" in str(reason) for reason in list(hit.get("modifiers", []) or []))
    assert int(hit.get("final_needed", 0) or 0) == 2


def test_cursed_circlet_queues_reactive_move_after_shooting_casualties():
    target = _make_unit(
        "Ophydian Destroyers",
        "necron-cursed-circlet-target",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=3,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        "enemy-shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=5,
        wounds=1,
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[target],
        enemy_units=[attacker],
    )
    _set_unit_location(target, x=0.0, y=0.0)
    _set_unit_location(attacker, x=8.0, y=0.0)
    game.map.units = [target, attacker]
    game.rebuild_entity_registry()

    _apply_enhancement(
        target,
        enhancement_id="000010668005",
        name="Cursed Circlet",
        description=(
            "Destroyer Cult model only. Each time an enemy unit is selected to shoot, after that unit has shot, "
            "if any models from the bearer's unit were destroyed as a result of those attacks, the bearer's unit "
            "can make a Surge move. To do so, roll one D6: the bearer's unit can be moved a number of inches up "
            "to the result, but the bearer's unit must finish that move as close as possible to the closest enemy "
            "unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that "
            "enemy unit. A unit cannot make a Surge move while it is Battle-shocked."
        ),
    )

    game._on_shooting_targets_selected_cursed_circlet(attacking_unit=attacker, target_units=[target])
    target.models[1].wounds = 0
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game._on_unit_shooting_resolved_cursed_circlet(attacker_unit=attacker)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_MOVE_UNIT
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "cursed_circlet"
    assert str(context.get("reactive_move_movement_type", "") or "") == "cursed_circlet"
    assert int(context.get("max_distance", 0) or 0) == 4
    assert bool(context.get("reactive_move_allow_engagement_range", False)) is True
    assert "AIRCRAFT" in list(context.get("cursed_circlet_closest_enemy_exclude_keywords_any", []) or [])


def test_cursed_circlet_does_not_queue_when_unit_is_battle_shocked():
    target = _make_unit(
        "Lokhust Destroyers",
        "necron-cursed-circlet-battleshocked",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=3,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        "enemy-shooters-battleshocked",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[target],
        enemy_units=[attacker],
    )

    _apply_enhancement(
        target,
        enhancement_id="000010668005",
        name="Cursed Circlet",
        description=(
            "Destroyer Cult model only. Each time an enemy unit is selected to shoot, after that unit has shot, "
            "if any models from the bearer's unit were destroyed as a result of those attacks, the bearer's unit "
            "can make a Surge move. To do so, roll one D6: the bearer's unit can be moved a number of inches up "
            "to the result, but the bearer's unit must finish that move as close as possible to the closest enemy "
            "unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that "
            "enemy unit. A unit cannot make a Surge move while it is Battle-shocked."
        ),
    )

    target.is_battle_shocked = lambda: True
    game._on_shooting_targets_selected_cursed_circlet(attacking_unit=attacker, target_units=[target])
    target.models[1].wounds = 0
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game._on_unit_shooting_resolved_cursed_circlet(attacker_unit=attacker)

    assert list(game.decision_queue.list() or []) == []


def test_cursed_circlet_does_not_queue_when_bearer_is_destroyed():
    target = _make_unit(
        "Lokhust Destroyers",
        "necron-cursed-circlet-bearer-dead",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=3,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        "enemy-shooters-bearer-dead",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[target],
        enemy_units=[attacker],
    )

    _apply_enhancement(
        target,
        enhancement_id="000010668005",
        name="Cursed Circlet",
        description=(
            "Destroyer Cult model only. Each time an enemy unit is selected to shoot, after that unit has shot, "
            "if any models from the bearer's unit were destroyed as a result of those attacks, the bearer's unit "
            "can make a Surge move. To do so, roll one D6: the bearer's unit can be moved a number of inches up "
            "to the result, but the bearer's unit must finish that move as close as possible to the closest enemy "
            "unit (excluding AIRCRAFT). When doing so, those models can be moved within Engagement Range of that "
            "enemy unit. A unit cannot make a Surge move while it is Battle-shocked."
        ),
    )

    game._on_shooting_targets_selected_cursed_circlet(attacking_unit=attacker, target_units=[target])
    bearer = _bearer_model(target)
    assert bearer is not None
    bearer.wounds = 0
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game._on_unit_shooting_resolved_cursed_circlet(attacker_unit=attacker)

    assert list(game.decision_queue.list() or []) == []


def test_cursed_circlet_move_validation_uses_closest_non_aircraft_enemy():
    mover = _make_unit(
        "Ophydian Destroyers",
        "necron-cursed-circlet-mover",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    aircraft = _make_unit(
        "Doom Scythe",
        "enemy-aircraft",
        faction_name="Enemy",
        keywords=["AIRCRAFT", "VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    infantry = _make_unit(
        "Enemy Infantry",
        "enemy-infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[mover],
        enemy_units=[aircraft, infantry],
    )
    _set_unit_location(mover, x=0.0, y=0.0)
    _set_unit_location(aircraft, x=2.0, y=0.0)
    _set_unit_location(infantry, x=8.0, y=0.0)
    game.map.units = [mover, aircraft, infantry]
    game.rebuild_entity_registry()

    request, result = _make_cursed_circlet_move_request(
        mover,
        max_distance=3,
        destination=(3.0, 0.0, 0.0),
    )

    errors = _validate_move_unit(game, request, result)

    assert errors == ()


def test_cursed_circlet_move_validation_rejects_not_closing_on_closest_non_aircraft_enemy():
    mover = _make_unit(
        "Ophydian Destroyers",
        "necron-cursed-circlet-mover-invalid",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    aircraft = _make_unit(
        "Doom Scythe",
        "enemy-aircraft-invalid",
        faction_name="Enemy",
        keywords=["AIRCRAFT", "VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    infantry = _make_unit(
        "Enemy Infantry",
        "enemy-infantry-invalid",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _necron_army, _enemy_army, _player, _enemy_player = _build_game(
        necron_units=[mover],
        enemy_units=[aircraft, infantry],
    )
    _set_unit_location(mover, x=0.0, y=0.0)
    _set_unit_location(aircraft, x=2.0, y=0.0)
    _set_unit_location(infantry, x=8.0, y=0.0)
    game.map.units = [mover, aircraft, infantry]
    game.rebuild_entity_registry()

    request, result = _make_cursed_circlet_move_request(
        mover,
        max_distance=3,
        destination=(1.0, 0.0, 0.0),
    )

    errors = _validate_move_unit(game, request, result)

    assert errors
    assert "cursed circlet" in str(errors[0]).lower()
    assert "closest enemy unit" in str(errors[0]).lower()
