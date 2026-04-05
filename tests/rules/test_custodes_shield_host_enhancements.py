from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Adeptus Custodes",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "5",
        wounds: str = "4",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Adeptus Custodes",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    toughness: str = "5",
    wounds: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True


def _build_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army("Adeptus Custodes", "Shield Host")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    game.attacker_index = 0
    game.defender_index = 1
    game.current_player_index = 0
    game.turn = 1
    return game, custodes_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AC",
        detachment="Shield Host",
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _enhancement_bearer_model(unit: Unit):
    sr = getattr(unit, "special_rules", {}) or {}
    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            return model
    return unit.models[0] if list(getattr(unit, "models", []) or []) else None


def _reset_model_wounds(model) -> None:
    model._wounds = int(getattr(model, "_base_wounds", 0) or 0)


def _melee_profile(*, attacks: int = 2, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": str(int(strength)),
            "AP": "-1",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


def _ranged_profile(*, attacks: int = 1, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Gun",
        {
            "range": "24",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


def _attack_result_stub(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=str(getattr(attacker, "name", "Attacker") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "Target") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
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
        crit_hit_threshold=None,
        crit_hit_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def test_shield_host_enhancement_descriptors_registered() -> None:
    castellan = get_enhancement_tool_descriptor(enhancement_id="000008395003")
    assert castellan is not None
    assert castellan.name == "Castellan's Mark"
    assert castellan.effect == "redeploy_units"

    hall = get_enhancement_tool_descriptor(enhancement_id="000008395004")
    assert hall is not None
    assert hall.name == "From the Hall of Armouries"
    assert hall.effect == "add_strength_and_damage_to_bearer_melee_weapons"

    panoptispex = get_enhancement_tool_descriptor(enhancement_id="000008395005")
    assert panoptispex is not None
    assert panoptispex.name == "Panoptispex"
    assert panoptispex.effect == "grant_ignores_cover_to_bearer_led_unit_ranged_weapons"


def test_castellans_mark_redeploy_filters_to_custodes_and_excludes_anathema() -> None:
    game, custodes_player, enemy_player = _build_game()
    source_bodyguard = _make_unit(
        "Custodian Guard",
        "ac-cm-bodyguard",
        keywords=["INFANTRY", "ADEPTUS CUSTODES", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Shield-Captain",
        "ac-cm-leader",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES", "SHIELD-CAPTAIN"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[source_bodyguard.get_datasheet_id()],
    )
    other_custodes = _make_unit(
        "Custodian Wardens",
        "ac-cm-other",
        keywords=["INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    anathema = _make_unit(
        "Witchseekers",
        "ac-cm-anathema",
        keywords=["INFANTRY", "ADEPTUS CUSTODES", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-cm",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (source_bodyguard, leader, other_custodes, anathema):
        custodes_player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    leader.attach_to_unit(source_bodyguard)
    _deploy_unit(source_bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(other_custodes, 4.0, 0.0)
    _deploy_unit(anathema, 8.0, 0.0)
    _deploy_unit(enemy, 20.0, 0.0)
    game.map.units = [source_bodyguard, leader, other_custodes, anathema, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008395003", enhancement_name="Castellan's Mark")
    has_redeploy, count, can_place_in_reserves = leader.has_redeploy()
    assert has_redeploy is True
    assert int(count) == 2
    assert can_place_in_reserves is True

    cache = dict(getattr(leader, "_ability_cache", {}) or {})
    assert list(cache.get("redeploy_filters", []) or []) == ["ADEPTUS CUSTODES"]
    assert list(cache.get("redeploy_excluded_keywords", []) or []) == ["ANATHEMA PSYKANA"]

    game.execute_redeploy_units_phase()
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "aeldari_guileful_strategist"
        and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Castellan's Mark"
        and str(getattr(req, "player_id", "") or "") == str(custodes_player.id)
    )

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    source_root_id = str(get_entity_id(source_bodyguard.get_attached_unit_root()) or "")
    other_root_id = str(get_entity_id(other_custodes.get_attached_unit_root()) or "")
    anathema_root_id = str(get_entity_id(anathema.get_attached_unit_root()) or "")
    assert source_root_id in target_ids
    assert other_root_id in target_ids
    assert anathema_root_id not in target_ids

    for target_id in (source_root_id, other_root_id):
        actions = {
            str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == target_id
        }
        assert "battlefield" in actions
        assert "strategic_reserves" in actions


def test_from_the_hall_of_armouries_applies_bearer_melee_strength_and_damage() -> None:
    game, custodes_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Shield-Captain",
        "ac-hall-bearer",
        model_count=2,
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES", "SHIELD-CAPTAIN"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy",
        "enemy-hall",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
        wounds="10",
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(enemy, 2.0, 0.0)
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer_unit,
        enhancement_id="000008395004",
        enhancement_name="From the Hall of Armouries",
    )
    bearer = _enhancement_bearer_model(bearer_unit)
    assert bearer is not None
    non_bearer = next(model for model in bearer_unit.models if model is not bearer)
    profile = _melee_profile(attacks=2, strength=4, damage=1)

    bearer_wound = profile._wound_target_with_tracking(
        enemy,
        bearer,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    non_bearer_wound = profile._wound_target_with_tracking(
        enemy,
        non_bearer,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(bearer_wound.get("wound", False))
    assert bool(non_bearer_wound.get("wound", False)) is False

    enemy_model = enemy.models[0]
    _reset_model_wounds(enemy_model)
    bearer_damage = profile._damage_target_with_tracking(
        enemy_model,
        bearer,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    _reset_model_wounds(enemy_model)
    non_bearer_damage = profile._damage_target_with_tracking(
        enemy_model,
        non_bearer,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(bearer_damage.get("damage_applied", 0) or 0) == 2
    assert int(non_bearer_damage.get("damage_applied", 0) or 0) == 1


def test_panoptispex_grants_ignores_cover_only_while_bearer_is_leading() -> None:
    game, custodes_player, enemy_player = _build_game()
    bodyguard = _make_unit(
        "Custodian Guard",
        "ac-pano-bodyguard",
        keywords=["INFANTRY", "ADEPTUS CUSTODES", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Shield-Captain",
        "ac-pano-leader",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES", "SHIELD-CAPTAIN"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    solo = _make_unit(
        "Shield-Captain Solo",
        "ac-pano-solo",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES", "SHIELD-CAPTAIN"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy",
        "enemy-pano",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (bodyguard, leader, solo):
        custodes_player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    leader.attach_to_unit(bodyguard)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(solo, 4.0, 0.0)
    _deploy_unit(enemy, 8.0, 0.0)
    game.map.units = [bodyguard, leader, solo, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008395005", enhancement_name="Panoptispex")
    _apply_enhancement(solo, enhancement_id="000008395005", enhancement_name="Panoptispex")

    profile = _ranged_profile()

    attack_with_leader = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        bodyguard.models[0],
        attack_with_leader,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_with_leader.get("ignores_cover", False))

    attack_solo = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        solo.models[0],
        attack_solo,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_solo.get("ignores_cover", False)) is False
