from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
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
        datasheet_id: str,
        faction_name: str = "Chaos Space Marines",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        toughness: str = "4",
        wounds: str = "4",
        save: str = "3",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Chaos Space Marines",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    toughness: str = "4",
    wounds: str = "4",
    save: str = "3",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army("Chaos Space Marines", "Fellhammer Siege-host")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, csm_player, enemy_player


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True


def _apply_fellhammer_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    enhancement_name: str,
    description: str = "",
) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CSM",
        detachment="Fellhammer Siege-host",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _ranged_profile(*, name: str = "Test Gun", strength: int = 4, damage: int = 2) -> WargearProfile:
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


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


def _enhancement_bearer_model(unit: Unit):
    sr = getattr(unit, "special_rules", {}) or {}
    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            return model
    return unit.models[0] if list(getattr(unit, "models", []) or []) else None


def test_fellhammer_enhancement_descriptors_registered() -> None:
    bastion = get_enhancement_tool_descriptor(enhancement_id="000008976002")
    assert bastion is not None
    assert bastion.name == "Bastion Plate"
    assert bastion.effect == "failed_save_damage_set_zero_for_bearer_unit"

    artifice = get_enhancement_tool_descriptor(enhancement_id="000008976003")
    assert artifice is not None
    assert artifice.name == "Iron Artifice"
    assert artifice.effect == "grant_bearer_weapon_anti_vehicle_and_fortification"

    enmity = get_enhancement_tool_descriptor(enhancement_id="000008976004")
    assert enmity is not None
    assert enmity.name == "Ironbound Enmity"
    assert enmity.effect == "bearer_wound_roll_bonus_while_within_objective_range"

    tracer = get_enhancement_tool_descriptor(enhancement_id="000008976005")
    assert tracer is not None
    assert tracer.name == "Warp Tracer"
    assert tracer.effect == "post_shoot_select_hit_enemy_loses_cover"


def test_bastion_plate_sets_failed_save_damage_zero_once_per_battle_round() -> None:
    game, csm_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Chaos Lord",
        "csm-bastion-bearer",
        keywords=["CHAOS LORD", "HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        save="3",
    )
    attacker_unit = _make_unit(
        "Enemy Shooters",
        "enemy-bastion-attacker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(attacker_unit)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(attacker_unit, 12.0, 0.0)
    game.map.units = [bearer_unit, attacker_unit]
    game.rebuild_entity_registry()

    _apply_fellhammer_enhancement(
        bearer_unit,
        enhancement_id="000008976002",
        enhancement_name="Bastion Plate",
        description=(
            "CHAOS LORD model only (excluding JUMP PACK models). Once per battle round, when a saving throw is "
            "failed for the bearer's unit, you can change the Damage characteristic of that attack to 0."
        ),
    )
    profile = _ranged_profile(strength=6, damage=2)
    target_model = bearer_unit.models[0]

    csm_player.set_next_optional_decision("FIRST_FAILED_SAVE_DAMAGE_ZERO", True)
    first_attack: dict = {}
    first_save = profile._save_with_tracking(
        target_model,
        first_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert first_save["saved"] is False
    assert first_attack.get("force_damage_zero") is True

    csm_player.set_next_optional_decision("FIRST_FAILED_SAVE_DAMAGE_ZERO", True)
    second_attack: dict = {}
    second_save = profile._save_with_tracking(
        target_model,
        second_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert second_save["saved"] is False
    assert second_attack.get("force_damage_zero") is not True

    game.turn = 2
    csm_player.set_next_optional_decision("FIRST_FAILED_SAVE_DAMAGE_ZERO", True)
    third_attack: dict = {}
    third_save = profile._save_with_tracking(
        target_model,
        third_attack,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert third_save["saved"] is False
    assert third_attack.get("force_damage_zero") is True


def test_iron_artifice_grants_bearer_anti_vehicle_and_fortification_keywords() -> None:
    _game, csm_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Warpsmith",
        "csm-iron-artifice-bearer",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="4",
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        "enemy-vehicle",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        toughness="10",
    )
    enemy_fort = _make_unit(
        "Enemy Fortification",
        "enemy-fortification",
        faction_name="Enemy",
        keywords=["FORTIFICATION"],
        faction_keywords=["ENEMY"],
        toughness="10",
    )
    csm_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy_vehicle)
    enemy_player.army.add_unit(enemy_fort)

    _apply_fellhammer_enhancement(
        bearer_unit,
        enhancement_id="000008976003",
        enhancement_name="Iron Artifice",
        description=(
            "HERETIC ASTARTES INFANTRY model only. The bearer's weapons have the [ANTI-VEHICLE 4+] and "
            "[ANTI-FORTIFICATION 4+] abilities."
        ),
    )
    bearer_model = bearer_unit.models[0]
    profile = _ranged_profile(name="Infernal Bolt", strength=4, damage=1)

    vehicle_attack = {"_aura_attack_mods": _aura_stub()}
    vehicle_hit = profile._hit_target_with_tracking(
        enemy_vehicle,
        bearer_model,
        vehicle_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert vehicle_hit["hit"] is True
    vehicle_wound = profile._wound_target_with_tracking(
        enemy_vehicle,
        bearer_model,
        vehicle_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert vehicle_wound["wound"] is True
    assert vehicle_attack.get("crit_wound") is True

    fort_attack = {"_aura_attack_mods": _aura_stub()}
    fort_hit = profile._hit_target_with_tracking(
        enemy_fort,
        bearer_model,
        fort_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert fort_hit["hit"] is True
    fort_wound = profile._wound_target_with_tracking(
        enemy_fort,
        bearer_model,
        fort_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert fort_wound["wound"] is True
    assert fort_attack.get("crit_wound") is True


def test_ironbound_enmity_applies_only_while_bearer_within_objective_range() -> None:
    _game, csm_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Chaos Lord",
        "csm-ironbound-bearer",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="4",
    )
    target = _make_unit(
        "Enemy Target",
        "enemy-ironbound-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    csm_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(target)
    bearer_model = bearer_unit.models[0]

    _apply_fellhammer_enhancement(
        bearer_unit,
        enhancement_id="000008976004",
        enhancement_name="Ironbound Enmity",
        description=(
            "HERETIC ASTARTES model only. Each time the bearer makes an attack while within range of an objective "
            "marker, add 1 to the Wound roll."
        ),
    )
    profile = _ranged_profile(name="Bolter", strength=4, damage=1)

    bearer_unit.is_within_any_objective_range = lambda game_map=None: True
    with_bonus = profile._wound_target_with_tracking(
        target,
        bearer_model,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert with_bonus["wound"] is True
    assert any("Ironbound Enmity" in m for m in list(with_bonus.get("modifiers", []) or []))

    bearer_unit.is_within_any_objective_range = lambda game_map=None: False
    without_bonus = profile._wound_target_with_tracking(
        target,
        bearer_model,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert without_bonus["wound"] is False
    assert not any("Ironbound Enmity" in m for m in list(without_bonus.get("modifiers", []) or []))


def test_warp_tracer_marks_hit_target_as_no_cover_until_end_of_phase() -> None:
    game, csm_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    bearer_unit = _make_unit(
        "Chaos Lord",
        "csm-warp-tracer-bearer",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit(
        "Enemy Target",
        "enemy-warp-tracer-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(target)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(target, 8.0, 0.0)
    game.map.units = [bearer_unit, target]
    game.rebuild_entity_registry()

    _apply_fellhammer_enhancement(
        bearer_unit,
        enhancement_id="000008976005",
        enhancement_name="Warp Tracer",
        description=(
            "HERETIC ASTARTES model only. In your Shooting phase, after the bearer has shot, select one enemy unit "
            "hit by one or more of those attacks. Until the end of the phase, that enemy unit cannot have the Benefit "
            "of Cover."
        ),
    )

    bearer_model = _enhancement_bearer_model(bearer_unit)
    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=bearer_unit,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={target: {"infernal_bolter": {bearer_model}}},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "") or "") == "post_shoot_no_cover"

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False))

    target_sr = getattr(target, "special_rules", {}) or {}
    assert bool(target_sr.get("post_shoot_no_cover_active", False))


def test_warp_tracer_only_triggers_for_targets_hit_by_bearer() -> None:
    game, csm_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    bearer_unit = _make_unit(
        "Chaos Lord",
        "csm-warp-tracer-bearer-filter",
        model_count=2,
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit(
        "Enemy Target",
        "enemy-warp-tracer-filter-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(target)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(target, 8.0, 0.0)
    game.map.units = [bearer_unit, target]
    game.rebuild_entity_registry()

    _apply_fellhammer_enhancement(
        bearer_unit,
        enhancement_id="000008976005",
        enhancement_name="Warp Tracer",
        description=(
            "HERETIC ASTARTES model only. In your Shooting phase, after the bearer has shot, select one enemy unit "
            "hit by one or more of those attacks. Until the end of the phase, that enemy unit cannot have the Benefit "
            "of Cover."
        ),
    )
    bearer_model = _enhancement_bearer_model(bearer_unit)
    non_bearer_model = next(
        model for model in list(getattr(bearer_unit, "models", []) or []) if model is not bearer_model
    )

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=bearer_unit,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={target: {"infernal_bolter": {non_bearer_model}}},
    )
    assert list(game.decision_queue.list() or []) == []

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=bearer_unit,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={target: {"infernal_bolter": {bearer_model}}},
    )
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
