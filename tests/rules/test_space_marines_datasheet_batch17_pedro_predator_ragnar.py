from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id is not None:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()


def _find_confirm_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() == str(ability_key).strip().lower():
            return request
    return None


def _resolve_yes(game: Game, request, player: Player) -> None:
    option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            option_id = getattr(option, "option_id", None)
            break
    assert option_id is not None
    resolve_decision_command(game, request, option_id, player_id=player.id)


def test_pedro_kantor_oath_of_rynn_can_trigger_in_opponent_command_phase() -> None:
    game, sm_army, _enemy_army, sm_player, enemy_player = _build_game()
    pedro = _actual_unit("Pedro Kantor", datasheet_id="000002713")
    sm_army.add_unit(pedro)
    _deploy(pedro, 0.0, 0.0)
    game.map.units = [pedro]
    game.rebuild_entity_registry()

    game.current_player_index = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_oath_of_rynn(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = _find_confirm_request(game, "oath_of_rynn")
    assert request is not None
    assert getattr(request, "player_id", None) == sm_player.id

    _resolve_yes(game, request, sm_player)

    weapon_names = [str(getattr(wargear, "name", "") or "").strip() for wargear in list(pedro.models[0].wargear or [])]
    weapon_names = [name for name in weapon_names if name]
    assert weapon_names
    for weapon_name in weapon_names:
        bonus, reasons = pedro.models[0].get_temporary_weapon_attacks_bonus(weapon_name)
        assert int(bonus or 0) == 1
        assert any("oath of rynn" in str(reason or "").lower() for reason in list(reasons or []))

    game.turn = 2
    game._on_phase_start_oath_of_rynn(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert _find_confirm_request(game, "oath_of_rynn") is None


def test_predator_destructor_destructor_uses_actual_datasheet_rule() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    predator = _actual_unit("Predator Destructor", datasheet_id="000002715")
    infantry_target = _mock_unit("Infantry Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    vehicle_target = _mock_unit("Vehicle Target", keywords=["VEHICLE"], faction_keywords=["ENEMY"])

    sm_army.add_unit(predator)
    enemy_army.add_unit(infantry_target)
    enemy_army.add_unit(vehicle_target)

    _deploy(predator, 0.0, 0.0)
    _deploy(infantry_target, 12.0, 0.0)
    _deploy(vehicle_target, 18.0, 0.0)
    game.map.units = [predator, infantry_target, vehicle_target]
    game.rebuild_entity_registry()

    predator_model = predator.models[0]
    weapon = next(
        wargear
        for wargear in list(predator_model.wargear or [])
        if "destructor" in str(getattr(wargear, "name", "") or "").lower()
        or "autocannon" in str(getattr(wargear, "name", "") or "").lower()
    )
    profile = weapon.profiles["default"]

    ap_vs_infantry = profile.get_effective_ap(predator_model, infantry_target)
    ap_vs_vehicle = profile.get_effective_ap(predator_model, vehicle_target)

    assert int(ap_vs_infantry or 0) == int(ap_vs_vehicle or 0) - 1


def test_ragnar_blackmane_battle_lust_grants_frostfang_attacks_on_charge() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    ragnar = _actual_unit("Ragnar Blackmane", datasheet_id="000000285")
    enemy = _mock_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(ragnar)
    enemy_army.add_unit(enemy)
    _deploy(ragnar, 0.0, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [ragnar, enemy]
    game.rebuild_entity_registry()

    ragnar._apply_charge_end_model_weapon_attacks_bonuses()

    ragnar_model = ragnar.models[0]
    bonus, reasons = ragnar_model.get_temporary_weapon_attacks_bonus("Frostfang")
    assert int(bonus or 0) == 2
    assert any("battle-lust" in str(reason or "").lower() for reason in list(reasons or []))

    weapon = next(wargear for wargear in list(ragnar_model.wargear or []) if str(getattr(wargear, "name", "") or "") == "Frostfang")
    profile = weapon.profiles["default"]
    attack_result = SimpleNamespace(attacks_rolled=0, attacks_dice_rolls=[], attacks_special_modifiers=[])
    count_info = profile._resolve_attack_count(
        attacker=ragnar_model,
        target=enemy,
        attack_result=attack_result,
        game_map=game.map,
        publish_roll_event=False,
    )
    base_attacks = int(profile.attacks.stat_average()) if hasattr(profile.attacks, "stat_average") else int(profile.attacks or 0)
    assert int(count_info.num_attacks or 0) == int(base_attacks) + 2


def test_ragnar_blackmane_war_howl_grants_blood_claws_full_melee_wound_rerolls() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    blood_claws = _actual_unit("Blood Claws")
    ragnar = _actual_unit("Ragnar Blackmane", datasheet_id="000000285")
    enemy = _mock_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    _attach_leader(blood_claws, ragnar)
    sm_army.add_unit(blood_claws)
    sm_army.add_unit(ragnar)
    enemy_army.add_unit(enemy)

    _deploy(blood_claws, 0.0, 0.0)
    _deploy(ragnar, 0.0, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [blood_claws, ragnar, enemy]
    game.rebuild_entity_registry()

    blood_claw_mods = blood_claws.get_model_wound_reroll_modifiers(
        model=blood_claws.models[0],
        attack_type="melee",
        target=enemy,
    )
    assert bool(blood_claw_mods.get("reroll_wound_full", False))
    assert any("war howl" in str(reason or "").lower() for reason in list(blood_claw_mods.get("reroll_wound_full_reasons", ()) or ()))

    ragnar_mods = blood_claws.get_model_wound_reroll_modifiers(
        model=ragnar.models[0],
        attack_type="melee",
        target=enemy,
    )
    assert bool(ragnar_mods.get("reroll_wound_full", False))
