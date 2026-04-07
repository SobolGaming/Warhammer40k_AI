from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


GROT_OILER_TEXT = (
    "Once per battle, at the end of your Movement phase, one model in the bearer's unit regains D3 lost wounds."
)
MEKANIAK_TEXT = (
    "At the end of your Movement phase, you can select one friendly Orks Vehicle model within 3\" of this model. "
    "That VEHICLE model regains up to D3 lost wounds, and, until the start of your next Movement phase, each time that "
    "VEHICLE model makes an attack, add 1 to the Hit roll. Each model can only be selected for this ability once per turn."
)
SAWBONEZ_TEXT = (
    "At the end of your Movement phase, select one friendly Beast Snagga Character model within 3\" of this model. "
    "That model is healed and regains up to 3 lost wounds. Each model can only be healed once per turn."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None, model_count: int = 1, wounds: str = "4"):
        self.id = str(name or "unit").lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [str(k).upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None, model_count: int = 1, wounds: str = "4") -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
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


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", detachment_type="Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    p1 = Player("Ork", PlayerControl.LOCAL, army=ork_army)
    p2 = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    game.map.units = list(ork_units or []) + list(enemy_units or [])
    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()
    return game, p1, p2


def _set_unit_positions(unit: Unit, base_x: float, base_y: float, *, spacing: float = 0.5) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(base_x) + (float(spacing) * float(idx)), float(base_y), 0.0, 0.0)


def _find_master_request(game: Game, *, source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for req in list(game.decision_queue.list() or []):
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "master_of_mechanisms":
            continue
        if source_id and str(ctx.get("source_unit_id", "") or "") != source_id:
            continue
        return req
    return None


def _option_for_model(request, model):
    model_id = str(get_entity_id(model) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_model_id", "") or "") == model_id:
            return option
    return None


def _prepare_movement_phase(game: Game, player: Player) -> None:
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = game.players.index(player)


def test_orks_repair_heal_rule_parser_supports_grot_oiler_mekaniak_and_sawbonez():
    grot_oiler = _make_unit(
        "Mek With Grot Oiler",
        abilities=[{"name": "Grot Oiler", "description": GROT_OILER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    mek = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    painboss = _make_unit(
        "Painboss",
        abilities=[{"name": "Sawbonez", "description": SAWBONEZ_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )

    grot_rule = grot_oiler.get_command_phase_vehicle_repair_hit_bonus_rule()
    mek_rule = mek.get_command_phase_vehicle_repair_hit_bonus_rule()
    saw_rule = painboss.get_command_phase_vehicle_repair_hit_bonus_rule()

    assert isinstance(grot_rule, dict)
    assert str(grot_rule.get("phase", "")) == "MOVEMENT_PHASE"
    assert str(grot_rule.get("selection_kind", "")) == "model"
    assert bool(grot_rule.get("target_in_source_unit", False)) is True
    assert bool(grot_rule.get("once_per_battle", False)) is True
    assert str(grot_rule.get("once_per_battle_scope", "")) == "unit"
    assert str(grot_rule.get("once_per_battle_key", "")) == "grot_oiler"

    assert isinstance(mek_rule, dict)
    assert str(mek_rule.get("phase", "")) == "MOVEMENT_PHASE"
    assert str(mek_rule.get("selection_kind", "")) == "model"
    assert bool(mek_rule.get("target_requires_vehicle", False)) is True
    assert int(mek_rule.get("hit_bonus", 0) or 0) == 1
    assert str(mek_rule.get("expires_phase", "")) == "MOVEMENT_PHASE"
    assert bool(mek_rule.get("limit_once_per_turn", False)) is True
    assert str(mek_rule.get("limit_scope", "")) == "model"

    assert isinstance(saw_rule, dict)
    assert str(saw_rule.get("phase", "")) == "MOVEMENT_PHASE"
    assert str(saw_rule.get("selection_kind", "")) == "model"
    assert int(saw_rule.get("heal_flat", 0) or 0) == 3
    assert bool(saw_rule.get("limit_once_per_turn", False)) is True
    assert str(saw_rule.get("limit_scope", "")) == "model"
    assert set(list(saw_rule.get("target_keywords", []) or [])) >= {"BEAST SNAGGA", "CHARACTER"}


def test_grot_oiler_heals_model_in_bearer_unit_and_is_once_per_battle():
    source = _make_unit(
        "Mek With Grot Oiler",
        abilities=[{"name": "Grot Oiler", "description": GROT_OILER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
        model_count=2,
        wounds="5",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, p1, _p2 = _build_game(ork_units=[source], enemy_units=[enemy])
    _set_unit_positions(source, 0.0, 0.0, spacing=4.0)
    _set_unit_positions(enemy, 30.0, 0.0)

    target_model = source.models[1]
    target_model.wounds = int(target_model.wounds) - 3
    before = int(target_model.wounds)

    _prepare_movement_phase(game, p1)
    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=source)
    assert request is not None
    option = _option_for_model(request, target_model)
    assert option is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(target_model.wounds) == before + 2
    assert bool(source.has_used_unit_once_per_battle("grot_oiler")) is True

    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert _find_master_request(game, source_unit=source) is None


def test_mekaniak_heals_vehicle_once_per_turn_and_hit_bonus_expires_next_movement_phase():
    source = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    vehicle = _make_unit(
        "Killa Kans",
        keywords=["ORKS", "VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
        wounds="6",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, p1, _p2 = _build_game(ork_units=[source, vehicle], enemy_units=[enemy])
    _set_unit_positions(source, 0.0, 0.0)
    _set_unit_positions(vehicle, 2.0, 0.0, spacing=0.6)
    _set_unit_positions(enemy, 30.0, 0.0)

    first_vehicle_model = vehicle.models[0]
    second_vehicle_model = vehicle.models[1]
    first_vehicle_model.wounds = int(first_vehicle_model.wounds) - 2
    second_vehicle_model.wounds = int(second_vehicle_model.wounds) - 1

    _prepare_movement_phase(game, p1)
    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=source)
    assert request is not None
    option = _option_for_model(request, first_vehicle_model)
    assert option is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    vehicle_sr = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(vehicle_sr.get("master_of_mechanisms_hit_bonus_active", False)) is True
    assert int(vehicle_sr.get("master_of_mechanisms_hit_bonus", 0) or 0) == 1
    assert str(vehicle_sr.get("master_of_mechanisms_expires_phase", "")) == "MOVEMENT_PHASE"
    assert str(vehicle_sr.get("master_of_mechanisms_hit_bonus_model_id", "")) == str(get_entity_id(first_vehicle_model))

    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    next_request = _find_master_request(game, source_unit=source)
    assert next_request is not None
    assert _option_for_model(next_request, first_vehicle_model) is None
    assert _option_for_model(next_request, second_vehicle_model) is not None

    game.turn = 3
    game._on_phase_start_master_of_mechanisms_cleanup(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    vehicle_sr_after_command = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(vehicle_sr_after_command.get("master_of_mechanisms_hit_bonus_active", False)) is True

    game._on_phase_start_master_of_mechanisms_cleanup(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    vehicle_sr_after_move = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(vehicle_sr_after_move.get("master_of_mechanisms_hit_bonus_active", False)) is False
    assert "master_of_mechanisms_hit_bonus_model_id" not in vehicle_sr_after_move


def test_sawbonez_heals_beast_snagga_character_once_per_turn():
    source = _make_unit(
        "Painboss",
        abilities=[{"name": "Sawbonez", "description": SAWBONEZ_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    beast_snagga_character = _make_unit(
        "Beastboss",
        keywords=["ORKS", "BEAST SNAGGA", "CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
        wounds="8",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, p1, _p2 = _build_game(ork_units=[source, beast_snagga_character], enemy_units=[enemy])
    _set_unit_positions(source, 0.0, 0.0)
    _set_unit_positions(beast_snagga_character, 2.0, 0.0)
    _set_unit_positions(enemy, 30.0, 0.0)

    target_model = beast_snagga_character.models[0]
    target_model.wounds = int(target_model.wounds) - 5
    before = int(target_model.wounds)

    _prepare_movement_phase(game, p1)
    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=source)
    assert request is not None
    option = _option_for_model(request, target_model)
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(target_model.wounds) == before + 3

    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    next_request = _find_master_request(game, source_unit=source)
    assert next_request is None or _option_for_model(next_request, target_model) is None


def test_movement_end_repair_heal_negative_wrong_phase():
    source = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    vehicle = _make_unit("Trukk", keywords=["ORKS", "VEHICLE"], faction_keywords=["ORKS"], wounds="8")
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, p1, _p2 = _build_game(ork_units=[source, vehicle], enemy_units=[enemy])
    _set_unit_positions(source, 0.0, 0.0)
    _set_unit_positions(vehicle, 2.0, 0.0)
    _set_unit_positions(enemy, 30.0, 0.0)
    vehicle.models[0].wounds = int(vehicle.models[0].wounds) - 1

    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    assert _find_master_request(game, source_unit=source) is None


def test_mekaniak_negative_out_of_range_wrong_type_and_no_lost_wounds():
    source = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    vehicle_out_of_range = _make_unit("Out Trukk", keywords=["ORKS", "VEHICLE"], faction_keywords=["ORKS"], wounds="8")
    infantry_wrong_type = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"], wounds="3")
    vehicle_undamaged = _make_unit("Full Trukk", keywords=["ORKS", "VEHICLE"], faction_keywords=["ORKS"], wounds="8")
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, p1, _p2 = _build_game(
        ork_units=[source, vehicle_out_of_range, infantry_wrong_type, vehicle_undamaged],
        enemy_units=[enemy],
    )
    _set_unit_positions(source, 0.0, 0.0)
    _set_unit_positions(vehicle_out_of_range, 4.1, 0.0)
    _set_unit_positions(infantry_wrong_type, 2.0, 1.0)
    _set_unit_positions(vehicle_undamaged, 2.5, 0.0)
    _set_unit_positions(enemy, 30.0, 0.0)

    game._on_phase_start_master_of_mechanisms(player=p1, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=source)
    assert request is None
