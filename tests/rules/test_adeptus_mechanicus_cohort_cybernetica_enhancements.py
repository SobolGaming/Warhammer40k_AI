from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.dice import DiceCollection


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        leadership: int = 7,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS MECHANICUS"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
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
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            leadership=leadership,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_extra_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=3,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    admech_player = Player("AdMech", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, admech_army, enemy_army, admech_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="ADM",
        detachment="Cohort Cybernetica",
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def test_cohort_cybernetica_enhancement_descriptors_registered():
    necromechanic = get_enhancement_tool_descriptor(enhancement_id="000008572002")
    assert necromechanic is not None
    assert necromechanic.name == "Necromechanic"
    assert necromechanic.effect == "set_failed_save_attack_damage_to_zero"
    assert float(necromechanic.effect_params.get("range", 0) or 0) == 12.0

    lord = get_enhancement_tool_descriptor(enhancement_id="000008572003")
    assert lord is not None
    assert lord.name == "Lord of Machines"
    assert lord.effect == "leadership_test_then_hit_penalty_or_ineligible_to_shoot"
    assert float(lord.effect_params.get("range", 0) or 0) == 12.0

    emotionless = get_enhancement_tool_descriptor(enhancement_id="000008572004")
    assert emotionless is not None
    assert emotionless.name == "Emotionless Clarity"
    assert emotionless.effect == "auto_trigger_deadly_demise"
    assert float(emotionless.effect_params.get("range", 0) or 0) == 12.0

    arch_negator = get_enhancement_tool_descriptor(enhancement_id="000008572005")
    assert arch_negator is not None
    assert arch_negator.name == "Arch-negator"
    assert arch_negator.effect == "grant_bearer_ranged_anti_keywords"
    assert int(arch_negator.effect_params.get("anti_vehicle", 0) or 0) == 4


def test_necromechanic_sets_damage_to_zero_once_per_battle_round():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    game.turn = 2
    game.current_player_index = 0

    source = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE", "ADEPTUS MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    attacker = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(vehicle)
    enemy_army.add_unit(attacker)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(vehicle, 4.0, 0.0)
    _set_unit_position(attacker, 20.0, 0.0)
    game.map.units = [source, vehicle, attacker]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008572002", name="Necromechanic")

    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "0",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )

    target_model = vehicle.models[0]
    attacker_model = attacker.models[0]
    first_attack = {}
    first_save = profile._save_with_tracking(
        target_model,
        first_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(first_save.get("saved", True)) is False
    assert bool(first_attack.get("force_damage_zero", False)) is True
    first_damage = profile._damage_target_with_tracking(
        target_model,
        attacker_model,
        first_attack,
        roll_value=2,
        allow_rerolls=False,
    )
    assert int(first_damage.get("damage_applied", -1)) == 0

    second_attack = {}
    second_save = profile._save_with_tracking(
        target_model,
        second_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(second_save.get("saved", True)) is False
    assert bool(second_attack.get("force_damage_zero", False)) is False

    game.turn = 3
    third_attack = {}
    third_save = profile._save_with_tracking(
        target_model,
        third_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(third_save.get("saved", True)) is False
    assert bool(third_attack.get("force_damage_zero", False)) is True


def test_lord_of_machines_queues_vehicle_targets_only_and_is_optional():
    game, admech_army, enemy_army, _admech_player, enemy_player = _build_game()
    source = _make_unit("Tech-priest Dominus", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["ADEPTUS MECHANICUS"])
    enemy_vehicle = _make_unit("Enemy Vehicle", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    enemy_infantry = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(source)
    enemy_army.add_unit(enemy_vehicle)
    enemy_army.add_unit(enemy_infantry)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(enemy_vehicle, 8.0, 0.0)
    _set_unit_position(enemy_infantry, 8.0, 2.0)
    source._has_line_of_sight_to_target = lambda _model, _target, _map: True
    game.map.units = [source, enemy_vehicle, enemy_infantry]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008572003", name="Lord of Machines")

    game.current_player_index = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_opponent_shooting_phase_disrupt(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str((req.context or {}).get("ability", "") or "") == "opponent_shooting_phase_disrupt"
        and str((req.context or {}).get("ability_name", "") or "") == "Lord of Machines"
    ]
    assert pending
    request = pending[0]
    assert any(str((opt.payload or {}).get("action", "") or "") == "skip" for opt in list(request.options or []))
    target_ids = {
        str((opt.payload or {}).get("target_unit_id", "") or "")
        for opt in list(request.options or [])
        if (opt.payload or {}).get("target_unit_id")
    }
    assert str(get_entity_id(enemy_vehicle) or "") in target_ids
    assert str(get_entity_id(enemy_infantry) or "") not in target_ids


def test_lord_of_machines_leadership_test_pass_and_fail_outcomes():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    source = _make_unit("Tech-priest Dominus", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["ADEPTUS MECHANICUS"])
    pass_target = _make_unit("Pass Vehicle", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"], leadership=7)
    fail_target = _make_unit("Fail Vehicle", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"], leadership=7)
    admech_army.add_unit(source)
    enemy_army.add_unit(pass_target)
    enemy_army.add_unit(fail_target)
    game.map.units = [source, pass_target, fail_target]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008572003", name="Lord of Machines")
    bearer = _bearer_model(source)
    assert bearer is not None
    pass_target.pass_leadership_check = lambda: True
    fail_target.pass_leadership_check = lambda: False

    game.current_player_index = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    pass_request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Lord of Machines",
        player_id=admech_player.id,
        options=[
            DecisionOption.create(
                "Pass Vehicle",
                payload={
                    "target_unit_id": str(get_entity_id(pass_target) or ""),
                    "source_unit_id": str(get_entity_id(source) or ""),
                    "model_id": str(get_entity_id(bearer) or ""),
                },
            )
        ],
        context={
            "ability": "opponent_shooting_phase_disrupt",
            "ability_name": "Lord of Machines",
            "ability_key": "LORD_OF_MACHINES",
            "resolution_mode": "leadership_test",
            "required_target_keywords": ["VEHICLE"],
        },
    )
    pass_result = DecisionResult(
        decision_id=pass_request.decision_id,
        player_id=admech_player.id,
        option_id=pass_request.options[0].option_id,
    )
    _apply_choose_quarry(game, pass_request, pass_result)
    assert bool(pass_target.special_rules.get("shooting_phase_hit_penalty_active"))
    assert bool(pass_target.is_shooting_phase_ineligible(game)) is False

    fail_request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Lord of Machines",
        player_id=admech_player.id,
        options=[
            DecisionOption.create(
                "Fail Vehicle",
                payload={
                    "target_unit_id": str(get_entity_id(fail_target) or ""),
                    "source_unit_id": str(get_entity_id(source) or ""),
                    "model_id": str(get_entity_id(bearer) or ""),
                },
            )
        ],
        context={
            "ability": "opponent_shooting_phase_disrupt",
            "ability_name": "Lord of Machines",
            "ability_key": "LORD_OF_MACHINES",
            "resolution_mode": "leadership_test",
            "required_target_keywords": ["VEHICLE"],
        },
    )
    fail_result = DecisionResult(
        decision_id=fail_request.decision_id,
        player_id=admech_player.id,
        option_id=fail_request.options[0].option_id,
    )
    _apply_choose_quarry(game, fail_request, fail_result)
    assert bool(fail_target.special_rules.get("shooting_phase_ineligible_active"))
    assert bool(fail_target.is_shooting_phase_ineligible(game))
    assert str(fail_target.special_rules.get("shooting_phase_ineligible_owner", "") or "") == enemy_player.id


def test_emotionless_clarity_auto_triggers_deadly_demise_once_per_turn():
    game, admech_army, _enemy_army, _admech_player, _enemy_player = _build_game()
    game.turn = 2
    game.current_player_index = 1

    source = _make_unit("Tech-priest Manipulus", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["ADEPTUS MECHANICUS"])
    destroyed = _make_unit(
        "Kastelan Robot",
        keywords=["VEHICLE", "LEGIO CYBERNETICA", "ADEPTUS MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(destroyed)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(destroyed, 6.0, 0.0)
    game.map.units = [source, destroyed]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008572004", name="Emotionless Clarity")
    destroyed.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    destroyed_model = destroyed.models[0]

    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=1):
        with patch.object(destroyed, "_apply_deadly_demise_explosion") as explode:
            destroyed._trigger_deadly_demise(destroyed_model, game.map)
        assert explode.call_count == 1

    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=1):
        with patch.object(destroyed, "_apply_deadly_demise_explosion") as explode:
            destroyed._trigger_deadly_demise(destroyed_model, game.map)
        assert explode.call_count == 0

    game.turn = 3
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=1):
        with patch.object(destroyed, "_apply_deadly_demise_explosion") as explode:
            destroyed._trigger_deadly_demise(destroyed_model, game.map)
        assert explode.call_count == 1


def test_arch_negator_grants_anti_vehicle_to_bearer_ranged_weapons_only():
    game, admech_army, _enemy_army, _admech_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    source.models.append(_make_extra_model("Auxiliary Model", source))
    admech_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008572005", name="Arch-negator")

    bearer = _bearer_model(source)
    assert bearer is not None
    non_bearer = next(model for model in list(source.models or []) if model is not bearer)

    bearer_ranged = source.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer,
        weapon_name="Phosphor Serpenta",
    )
    bearer_anti_specs = {tuple(spec) for spec in list(bearer_ranged.get("anti_specs") or [])}
    assert ("VEHICLE", 4) in bearer_anti_specs

    bearer_melee = source.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=bearer,
        weapon_name="Omnissian Axe",
    )
    assert list(bearer_melee.get("anti_specs") or []) == []

    non_bearer_ranged = source.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=non_bearer,
        weapon_name="Phosphor Serpenta",
    )
    assert list(non_bearer_ranged.get("anti_specs") or []) == []
