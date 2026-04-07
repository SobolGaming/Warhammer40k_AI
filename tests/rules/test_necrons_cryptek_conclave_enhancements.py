from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
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
                "M": "5",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _add_objective(game: Game, *, x: float, y: float, objective_id: str = "obj-1") -> None:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    objective = Objective(
        name=f"Objective {objective_id}",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game_state: False,
        location=point,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army.with_detachment("Necrons", "Cryptek Conclave")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_idx = 0
    game.current_player_index = 0
    game.battle_round_starting_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    necron_army.configure_rule_managers(force=True)
    return game, necron_army, enemy_army, necron_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _make_weapon(name: str = "Eldritch Lance"):
    return Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _make_ranged_profile(*, weapon_name: str = "Eldritch Lance", range_value: int = 24) -> WargearProfile:
    parent = Wargear(
        {
            "name": weapon_name,
            "type": "Ranged",
            "range": str(int(range_value)),
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return parent.profiles["default"]


def _apply_named_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
    points: int = 20,
) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Cryptek Conclave",
        points=points,
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


def test_cryptek_conclave_enhancement_descriptors_registered():
    expected = {
        "000010664002": ("Quantum Abacus", "targeted_stratagem_cp_refund_with_objective_bonus"),
        "000010664003": ("Atomic Disintegrators", "extend_technosorcerous_augmentation_choices"),
        "000010664004": ("Gauntlet of Compression", "bearer_unit_ranged_range_bonus"),
        "000010664005": ("Gravitic Bolas", "post_shoot_select_hit_enemy_unit_to_pin"),
    }

    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_quantum_abacus_refunds_cp_on_objective_bonus_and_stops_when_bearer_dies():
    game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Chronomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=2,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, cryptek)
    _set_unit_location(bodyguard, x=0.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    _add_objective(game, x=0.0, y=0.0)
    game.map.units = [cryptek, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000010664002",
        name="Quantum Abacus",
        description=(
            "NECRONS model only. Each time you select the bearer's unit as the target of a Stratagem, roll one D6, "
            "adding 1 if it is within range of one or more objectives: on a 4+, you gain 1CP."
        ),
    )

    necron_player.command_points = 2
    necron_player._pending_stratagem_target_unit_id = str(get_entity_id(bodyguard) or "")
    necron_player._pending_stratagem_name = "Test Stratagem"
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        ok = bool(necron_player.spend_command_points(1, reason="Stratagem: Test", source="stratagem"))
    assert ok
    assert int(necron_player.command_points or 0) == 2

    _set_unit_location(bodyguard, x=12.0, y=0.0)
    necron_player.command_points = 2
    necron_player._pending_stratagem_target_unit_id = str(get_entity_id(bodyguard) or "")
    necron_player._pending_stratagem_name = "Test Stratagem"
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        ok = bool(necron_player.spend_command_points(1, reason="Stratagem: Test", source="stratagem"))
    assert ok
    assert int(necron_player.command_points or 0) == 1

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    _set_unit_location(bodyguard, x=0.0, y=0.0)
    necron_player.command_points = 2
    necron_player._pending_stratagem_target_unit_id = str(get_entity_id(bodyguard) or "")
    necron_player._pending_stratagem_name = "Test Stratagem"
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        ok = bool(necron_player.spend_command_points(1, reason="Stratagem: Test", source="stratagem"))
    assert ok
    assert int(necron_player.command_points or 0) == 1


def test_atomic_disintegrators_adds_extra_technosorcerous_choices():
    game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Technomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit("Enemy Vehicle", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, cryptek)
    bodyguard_weapon = _make_weapon("Gauss Blaster")
    bodyguard.models[0].wargear = [bodyguard_weapon]
    game.map.units = [cryptek, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000010664003",
        name="Atomic Disintegrators",
        description=(
            "Cryptek model only. In your Shooting phase, each time the bearer's unit is selected to shoot, when "
            "selecting an ability for the Technosorcerous Augmentations Detachment rule, you can also select from the "
            "following abilities: [ANTI-MONSTER 5+], [ANTI-VEHICLE 5+]."
        ),
    )

    game._on_shooting_targets_selected_technosorcerous_augmentations(attacking_unit=bodyguard, target_units=[enemy])
    pending = list(game.decision_queue.list() or [])
    assert pending
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION
    choices = [str((opt.payload or {}).get("choice", "") or "") for opt in list(request.options or [])]
    assert choices == [
        "ANTI_INFANTRY_3",
        "ANTI_MOUNTED_4",
        "ASSAULT",
        "HEAVY",
        "IGNORES_COVER",
        "ANTI_MONSTER_5",
        "ANTI_VEHICLE_5",
    ]

    anti_vehicle_option_id = next(
        opt.option_id
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice", "") or "") == "ANTI_VEHICLE_5"
    )
    resolve_decision_command(game, request, anti_vehicle_option_id, player_id=necron_player.id)
    bonuses = bodyguard.get_model_weapon_keyword_bonuses(
        model=bodyguard.models[0],
        weapon_name="Gauss Blaster",
        attack_type="ranged",
    )
    assert ("VEHICLE", 5) in list(bonuses.get("anti_specs", []) or [])


def test_gauntlet_of_compression_adds_range_to_bearer_unit_while_bearer_lives():
    game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Chronomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, cryptek)
    game.map.units = [cryptek, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000010664004",
        name="Gauntlet of Compression",
        description=(
            "NECRONS model only. Add 6\" to the Range characteristic of ranged weapons equipped by models in the "
            "bearer's unit."
        ),
    )

    profile = _make_ranged_profile(weapon_name="Gauss Blaster", range_value=24)
    assert int(profile._effective_range_max(bodyguard.models[0]) or 0) == 30

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    assert int(profile._effective_range_max(bodyguard.models[0]) or 0) == 24


def test_gravitic_bolas_pins_non_titanic_unit_hit_by_bearer():
    game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
    cryptek = _make_unit(
        "Psychomancer",
        keywords=["CHARACTER", "CRYPTEK", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    infantry = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    titanic = _make_unit("Enemy Titanic", faction_name="Enemy", keywords=["TITANIC"], faction_keywords=["ENEMY"])
    necron_army.add_unit(cryptek)
    necron_army.add_unit(bodyguard)
    enemy_army.add_unit(infantry)
    enemy_army.add_unit(titanic)
    _attach_leader(bodyguard, cryptek)
    game.map.units = [cryptek, bodyguard, infantry, titanic]
    game.rebuild_entity_registry()

    _apply_named_enhancement(
        cryptek,
        enhancement_id="000010664005",
        name="Gravitic Bolas",
        description=(
            "Cryptek model only. In your Shooting phase, after the bearer has shot, select one enemy unit hit by one "
            "or more of those attacks (excluding TITANIC units); until the start of your next turn, that enemy unit "
            "is pinned. While a unit is pinned, subtract 2 from that unit's Move characteristic and subtract 2 from "
            "Charge rolls made for that unit."
        ),
    )

    bearer = _bearer_model(cryptek)
    assert bearer is not None
    game._on_unit_shooting_resolved_post_shoot_pinned(
        attacker_unit=bodyguard,
        hits_by_target={infantry: 1, titanic: 1},
        hit_models_by_target={infantry: {bearer}, titanic: {bearer}},
    )

    requests = list(game.decision_queue.list() or [])
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability_name", "") or "") == "Gravitic Bolas"
    assert str((request.context or {}).get("expires_phase", "") or "") == "COMMAND_PHASE"
    option_targets = {str((opt.payload or {}).get("target_unit_id", "") or "") for opt in list(request.options or [])}
    assert str(get_entity_id(infantry) or "") in option_targets
    assert str(get_entity_id(titanic) or "") not in option_targets

    target_option = next(
        opt for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(infantry) or "")
    )
    resolve_decision_command(game, request, target_option.option_id, player_id=necron_player.id)

    sr = dict(getattr(infantry, "special_rules", {}) or {})
    assert bool(sr.get("pinned_active", False))
    assert int(sr.get("pinned_move_penalty", 0) or 0) == -2
    assert int(sr.get("pinned_charge_penalty", 0) or 0) == -2
    assert str(sr.get("pinned_expires_phase", "") or "") == "COMMAND_PHASE"

    game._on_phase_start_pinned_cleanup(player=necron_player, phase=BattleRoundPhases.COMMAND_PHASE)
    cleared = dict(getattr(infantry, "special_rules", {}) or {})
    assert not bool(cleared.get("pinned_active", False))

    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    game._on_unit_shooting_resolved_post_shoot_pinned(
        attacker_unit=bodyguard,
        hits_by_target={infantry: 1},
        hit_models_by_target={infantry: {bearer}},
    )
    assert list(game.decision_queue.list() or []) == []
