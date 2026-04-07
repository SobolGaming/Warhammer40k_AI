from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _validate_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        wounds: int = 4,
        toughness: int = 4,
        objective_control: int = 1,
        base_size: str = "32mm",
        model_count: int = 1,
    ) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        unit_label = "Test Model" if int(model_count) == 1 else "Test Models"
        cost_label = "model" if int(model_count) == 1 else "models"
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} {unit_label}"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} {cost_label}", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    wounds: int = 4,
    toughness: int = 4,
    objective_control: int = 1,
    base_size: str = "32mm",
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            objective_control=objective_control,
            base_size=base_size,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sm_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", sm_control, army=sm_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _find_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == ability_key:
            return request
    return None


def _make_ranged_profile(*, weapon_name: str = "Test Rifle", range_value: int = 24, strength: int = 4):
    parent = Wargear(
        {
            "name": weapon_name,
            "type": "Ranged",
            "range": str(int(range_value)),
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
        }
    )
    return parent.profiles["default"]


class _DummyMeleeWargear:
    def is_melee(self):
        return True


class _DummyMeleeProfile:
    def __init__(self):
        self.parent_wargear = _DummyMeleeWargear()


def test_marshal_pious_fervour_grants_master_crafted_power_weapon_attacks_bonus() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    marshal = _actual_unit("Marshal", datasheet_id="000002796")
    enemy_one = _mock_unit("Enemy One", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_two = _mock_unit("Enemy Two", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_three = _mock_unit("Enemy Three", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_four = _mock_unit("Enemy Four", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(marshal)
    for enemy in (enemy_one, enemy_two, enemy_three, enemy_four):
        enemy_army.add_unit(enemy)

    _deploy(marshal, 0.0, 0.0)
    _deploy(enemy_one, 5.0, 0.0)
    _deploy(enemy_two, 0.0, 5.5)
    _deploy(enemy_three, -5.8, 0.0)
    _deploy(enemy_four, 15.0, 0.0)
    game.map.units = [marshal, enemy_one, enemy_two, enemy_three, enemy_four]

    marshal_model = marshal.models[0]
    weapon = next(wg for wg in list(marshal_model.wargear or []) if str(getattr(wg, "name", "") or "") == "Master-crafted power weapon")
    profile = weapon.profiles["default"]

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game._on_fight_unit_selected_pious_fervour(unit=marshal, selecting_player=sm_player)

    bonus, reasons = marshal_model.get_temporary_weapon_attacks_bonus("Master-crafted power weapon")
    assert int(bonus or 0) == 3
    assert any("Pious Fervour" in str(reason or "") for reason in list(reasons or []))

    attack_result = SimpleNamespace(attacks_rolled=0, attacks_dice_rolls=[], attacks_special_modifiers=[])
    count_info = profile._resolve_attack_count(
        attacker=marshal_model,
        target=enemy_one,
        attack_result=attack_result,
        game_map=game.map,
        publish_roll_event=False,
    )
    base_attacks = int(profile.attacks.stat_average()) if hasattr(profile.attacks, "stat_average") else int(profile.attacks or 0)
    assert int(count_info.num_attacks or 0) == int(base_attacks) + 3


def test_murderfang_murder_maker_aura_grants_dynamic_wulfen_fight_on_death() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    murderfang = _actual_unit("Murderfang", datasheet_id="000000314")
    wulfen = _mock_unit(
        "Friendly Wulfen",
        keywords=["INFANTRY", "WULFEN"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
    )
    enemy = _mock_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(murderfang)
    sm_army.add_unit(wulfen)
    enemy_army.add_unit(enemy)

    _deploy(murderfang, 0.0, 0.0)
    _deploy(wulfen, 20.0, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [murderfang, wulfen, enemy]
    game.phase = BattleRoundPhases.FIGHT_PHASE

    assert wulfen.get_melee_fight_on_death_after_attacks_rule(model=wulfen.models[0]) is None

    _deploy(wulfen, 4.0, 0.0)
    rule = wulfen.get_melee_fight_on_death_after_attacks_rule(model=wulfen.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "murder-maker" in str(rule.get("source", "") or "").lower()

    wulfen.round_state.fought_this_phase = False
    wulfen._last_destroyed_by_weapon_profile = _DummyMeleeProfile()
    destroyed_model = wulfen.models[0]
    destroyed_model._wounds = 0
    destroyed_model.wounds = 0

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=4):
        wulfen._handle_model_destroyed(destroyed_model, game.map)

    pending = list(getattr(wulfen, "_melee_fight_on_death_pending_models", []) or [])
    assert destroyed_model in pending


def test_nephilim_jetfighter_lightning_fast_manoeuvres_applies_fly_only_wound_penalty() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    nephilim = _actual_unit("Nephilim Jetfighter", datasheet_id="000000239")
    fly_attacker = _mock_unit("Fly Attacker", keywords=["INFANTRY", "FLY"], faction_keywords=["ENEMY"])
    ground_attacker = _mock_unit("Ground Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(nephilim)
    enemy_army.add_unit(fly_attacker)
    enemy_army.add_unit(ground_attacker)

    fly_attacker.models[0].keywords = ["FLY"]
    ground_attacker.models[0].keywords = []

    target_toughness = int(nephilim.models[0].toughness or 0)
    profile = _make_ranged_profile(strength=target_toughness)

    ground_result = profile._wound_target_with_tracking(
        nephilim,
        ground_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    fly_result = profile._wound_target_with_tracking(
        nephilim,
        fly_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(ground_result.get("wound", False)) is True
    assert bool(fly_result.get("wound", False)) is False
    assert any("Lightning-fast Manoeuvres" in str(mod or "") for mod in list(fly_result.get("modifiers", []) or []))


def test_njal_tempests_wrath_marks_hit_enemy_and_reduces_ranged_weapon_range_until_cleanup() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    njal = _actual_unit("Njal Stormcaller", datasheet_id="000000292")
    enemy_infantry = _mock_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_monster = _mock_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], toughness=9, wounds=10)

    sm_army.add_unit(njal)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_monster)
    _deploy(njal, 0.0, 0.0)
    _deploy(enemy_infantry, 10.0, 0.0)
    _deploy(enemy_monster, 12.0, 0.0)
    game.map.units = [njal, enemy_infantry, enemy_monster]
    game.rebuild_entity_registry()

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    spec = njal.model_post_shoot_stormwracked_specs(njal.models[0])[0]
    weapon_key = str(spec.get("weapon_key", "") or "")
    game._on_unit_shooting_resolved_post_shoot_stormwracked(
        attacker_unit=njal,
        hits_by_target={enemy_infantry: 1, enemy_monster: 1},
        hit_models_by_target_weapon={
            enemy_infantry: {weapon_key: [njal.models[0]]},
            enemy_monster: {weapon_key: [njal.models[0]]},
        },
    )

    request = _find_request(game, "post_shoot_stormwracked")
    assert request is not None
    option_labels = [str(opt.label or "") for opt in list(request.options or [])]
    assert option_labels == ["Enemy Infantry"]

    target_option = request.options[0]
    result = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    target_sr = dict(getattr(enemy_infantry, "special_rules", {}) or {})
    assert bool(target_sr.get("stormwracked_active")) is True
    assert int(target_sr.get("stormwracked_range_penalty", 0) or 0) == 6
    assert int(target_sr.get("stormwracked_range_minimum", 0) or 0) == 12

    profile_24 = _make_ranged_profile(range_value=24)
    profile_16 = _make_ranged_profile(range_value=16)
    assert int(profile_24._effective_range_max(enemy_infantry.models[0]) or 0) == 18
    assert int(profile_16._effective_range_max(enemy_infantry.models[0]) or 0) == 12

    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_stormwracked_cleanup(player=sm_player, phase=game.phase)

    assert bool(getattr(enemy_infantry, "special_rules", {}).get("stormwracked_active", False)) is False
    assert int(profile_24._effective_range_max(enemy_infantry.models[0]) or 0) == 24


def test_njal_tempests_wrath_validation_rejects_monster_target() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    njal = _actual_unit("Njal Stormcaller", datasheet_id="000000292")
    enemy_monster = _mock_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], toughness=9, wounds=10)

    sm_army.add_unit(njal)
    enemy_army.add_unit(enemy_monster)
    game.map.units = [njal, enemy_monster]
    game.rebuild_entity_registry()

    option = DecisionOption.create(
        "Enemy Monster",
        payload={"target_unit_id": get_entity_id(enemy_monster)},
    )
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Tempest's Wrath: choose a target.",
        player_id=sm_player.id,
        options=[option],
        context={
            "ability": "post_shoot_stormwracked",
            "ability_name": "Tempest's Wrath (Psychic)",
            "exclude_keywords_any": ["MONSTER", "VEHICLE"],
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=sm_player.id,
        option_id=option.option_id,
        payload=dict(option.payload or {}),
    )

    errors = tuple(_validate_choose_quarry(game, request, result))
    assert errors
    assert "MONSTER" in str(errors[0])
