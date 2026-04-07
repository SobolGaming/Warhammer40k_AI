from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_CHOOSE_QUARRY,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
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
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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
    wounds: int = 4,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
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
        wounds=6,
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
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Data-Psalm Conclave")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
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
        detachment="Data-Psalm Conclave",
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


def _find_benediction_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "data_psalm_benediction"
    ]


def _find_autosermon_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "data_psalm_autosermon"
    ]


def _find_battleshock_clear_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "start_any_phase_clear_battleshock"
    ]


def _choose_option_by_payload_field(game: Game, request, *, player_id: str, field: str, value: str) -> None:
    wanted = str(value or "")
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get(field, "") or "") == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _choose_benediction(game: Game, request, *, player_id: str, choice_key: str) -> None:
    wanted = str(choice_key or "").strip().upper()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _attack_result_stub() -> AttackResult:
    return AttackResult(
        weapon_name="Test Weapon",
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="",
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _melee_profile(*, damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(name="Power Blades", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_data_psalm_enhancement_descriptors_registered():
    locum = get_enhancement_tool_descriptor(enhancement_id="000008564002")
    assert locum is not None
    assert locum.name == "Mechanicus Locum"
    assert locum.effect == "clear_battleshock_for_friendly_unit_in_range"

    mantle = get_enhancement_tool_descriptor(enhancement_id="000008564003")
    assert mantle is not None
    assert mantle.name == "Mantle of the Gnosticarch"
    assert mantle.effect == "set_allocated_damage_to_value"
    assert int(mantle.effect_params.get("set_damage_to", 0) or 0) == 1

    autosermon = get_enhancement_tool_descriptor(enhancement_id="000008564004")
    assert autosermon is not None
    assert autosermon.name == "Data-blessed Autosermon"
    assert autosermon.effect == "activate_other_data_psalm_benediction_for_bearer_unit"

    temporcopia = get_enhancement_tool_descriptor(enhancement_id="000008564005")
    assert temporcopia is not None
    assert temporcopia.name == "Temporcopia"
    assert temporcopia.effect == "grant_fights_first_to_bearer_unit"


def test_mechanicus_locum_sets_bearer_leadership_and_clears_battleshock_once():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        leadership=7,
    )
    target = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(target, 6.0, 0.0)
    _set_unit_position(enemy, 24.0, 0.0)
    game.map.units = [source, target, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008564002", name="Mechanicus Locum")

    bearer = _bearer_model(source)
    assert bearer is not None
    assert int(getattr(bearer, "leadership", 0) or 0) == 6

    target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    assert bool(target.is_battle_shocked())

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_start_optional_abilities(player=admech_player, phase=game.phase)
    requests = _find_battleshock_clear_requests(game)
    assert len(requests) == 1
    request = requests[0]

    _choose_option_by_payload_field(
        game,
        request,
        player_id=admech_player.id,
        field="unit_id",
        value=str(get_entity_id(target) or ""),
    )
    assert bool(target.is_battle_shocked()) is False

    ability_key = str((request.context or {}).get("ability_key", "") or "")
    assert bool(source.has_used_unit_once_per_battle(ability_key))

    target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    game._on_phase_start_optional_abilities(player=admech_player, phase=game.phase)
    assert _find_battleshock_clear_requests(game) == []


def test_mantle_of_the_gnosticarch_sets_damage_to_one_for_bearer_only():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=6,
    )
    source.models.append(_make_extra_model("Assistant", source))
    attacker_unit = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(source)
    enemy_army.add_unit(attacker_unit)
    game.map.units = [source, attacker_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008564003", name="Mantle of the Gnosticarch")

    bearer = _bearer_model(source)
    assert bearer is not None
    non_bearer = next(model for model in list(source.models or []) if model is not bearer)
    attacker_model = attacker_unit.models[0]
    profile = _melee_profile(damage="3")

    before_bearer = int(bearer.wounds)
    profile._damage_target_with_tracking(
        bearer,
        attacker_model,
        {"below_half_distance": False, "mortal_wound": False},
        game_map=None,
    )
    assert int(before_bearer - bearer.wounds) == 1

    before_non_bearer = int(non_bearer.wounds)
    profile._damage_target_with_tracking(
        non_bearer,
        attacker_model,
        {"below_half_distance": False, "mortal_wound": False},
        game_map=None,
    )
    assert int(before_non_bearer - non_bearer.wounds) == 3


def test_temporcopia_grants_fights_first_to_bearers_unit():
    game, admech_army, _enemy_army, _admech_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008564005", name="Temporcopia")
    assert bool(source.has_fight_first())


def test_data_blessed_autosermon_queues_choice_applies_other_benediction_and_is_once_per_battle():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    other_cult = _make_unit(
        "Fulgurite Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(source)
    admech_army.add_unit(other_cult)
    enemy_army.add_unit(enemy)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(other_cult, 2.0, 0.0)
    _set_unit_position(enemy, 2.5, 0.0)
    game.map.units = [source, other_cult, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008564004", name="Data-blessed Autosermon")

    admech_army.on_battle_round_start(1)
    benediction_request = _find_benediction_requests(game)[0]
    _choose_benediction(
        game,
        benediction_request,
        player_id=admech_player.id,
        choice_key="PANEGYRIC_PROCESSION",
    )

    admech_army.adeptus_mechanicus_detachments.on_command_phase_start(game=game, player=admech_player)
    autosermon_requests = _find_autosermon_requests(game)
    assert len(autosermon_requests) == 1
    autosermon_request = autosermon_requests[0]
    choices = {
        str((opt.payload or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(autosermon_request.options or [])
        if (opt.payload or {}).get("choice_key")
    }
    assert choices == {"CITATION_IN_SAVAGERY"}

    _choose_option_by_payload_field(
        game,
        autosermon_request,
        player_id=admech_player.id,
        field="choice_key",
        value="CITATION_IN_SAVAGERY",
    )
    once_key = str((autosermon_request.context or {}).get("ability_key", "") or "data_blessed_autosermon")
    assert bool(source.has_used_unit_once_per_battle(once_key))

    source.round_state.charged_this_round = True
    other_cult.round_state.charged_this_round = True
    profile = _melee_profile(damage="1")
    source_model = source.models[0]
    other_model = other_cult.models[0]

    source_attack_result = _attack_result_stub()
    source_attack_info = profile._resolve_attack_count(
        enemy,
        source_model,
        source_attack_result,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(source_attack_info.num_attacks or 0) == 3

    other_attack_result = _attack_result_stub()
    other_attack_info = profile._resolve_attack_count(
        enemy,
        other_model,
        other_attack_result,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(other_attack_info.num_attacks or 0) == 2

    game.turn = 2
    admech_army.adeptus_mechanicus_detachments.on_command_phase_start(game=game, player=admech_player)
    assert _find_autosermon_requests(game) == []
