from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 2,
        leadership: int = 7,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
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
    faction_name: str = "Imperial Agents",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 2,
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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army.with_detachment("Imperial Agents", "Ordo Hereticus Purgation Force")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_army, enemy_army, ia_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="AOI",
        detachment="Ordo Hereticus Purgation Force",
        detachment_id="000009130",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _attack_profile(*, is_ranged: bool = True, damage: str = "2") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun" if is_ranged else "Test Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "2",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]
    bodyguard.get_attached_unit_models = lambda: list(bodyguard.models) + list(leader.models)
    leader.get_attached_unit_root = lambda: bodyguard
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    assert bearer_id
    return next(
        model
        for model in list(getattr(unit, "models", []) or [])
        if str(get_entity_id(model) or "") == bearer_id
    )


def test_ordo_hereticus_enhancement_descriptors_registered():
    ignis = get_enhancement_tool_descriptor(enhancement_id="000009130002")
    witch_hunter = get_enhancement_tool_descriptor(enhancement_id="000009130005")

    assert ignis is not None
    assert ignis.name == "Ignis Judicium"
    assert tuple(ignis.effect_params.get("weapon_keywords", ()) or ()) == (
        "DEVASTATING WOUNDS",
        "MELTA 1",
        "PRECISION",
    )

    assert witch_hunter is not None
    assert witch_hunter.name == "Witch Hunter"
    assert tuple(witch_hunter.effect_params.get("required_target_keywords", ()) or ()) == ("PSYKER",)


def test_ignis_judicium_grants_bearer_ranged_keywords_and_half_range_melta_only_to_bearer():
    game, ia_army, enemy_army, _ia_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Inquisitor",
        keywords=["INFANTRY", "CHARACTER", "INQUISITOR"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ia_army.add_unit(bearer_unit)
    enemy_army.add_unit(target)
    _deploy_unit(game, bearer_unit, 0.0, 0.0)
    _deploy_unit(game, target, 12.0, 0.0)

    _apply_enhancement(
        bearer_unit,
        enhancement_id="000009130002",
        enhancement_name="Ignis Judicium",
        description="The bearer's ranged weapons have [DEVASTATING WOUNDS], [MELTA 1] and [PRECISION].",
    )

    bearer_model = _bearer_model(bearer_unit)
    other_model = next(model for model in list(bearer_unit.models or []) if model is not bearer_model)

    bearer_bonuses = bearer_unit.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_name="Test Gun",
    )
    assert bool(bearer_bonuses.get("devastating_wounds", False)) is True
    assert bool(bearer_bonuses.get("precision", False)) is True
    assert int(bearer_bonuses.get("melta_bonus", 0) or 0) == 1

    other_bonuses = bearer_unit.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=other_model,
        weapon_name="Test Gun",
    )
    assert other_bonuses == {}

    profile = _attack_profile(is_ranged=True, damage="2")
    attack_instance = {"_aura_attack_mods": _aura_stub(), "below_half_distance": True}
    profile._hit_target_with_tracking(
        target,
        bearer_model,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    damage_result = profile._damage_target_with_tracking(
        target.models[0],
        bearer_model,
        attack_instance,
        allow_rerolls=False,
    )
    assert any("Ignis Judicium [MELTA 1]" in str(entry) for entry in list(damage_result.get("special_effects", []) or []))


def test_witch_hunter_rerolls_hits_only_while_bearer_is_leading_and_target_is_psyker():
    game, ia_army, enemy_army, _ia_player, _enemy_player = _build_game()
    bodyguard = _make_unit(
        "Inquisitorial Agents",
        keywords=["INFANTRY", "INQUISITORIAL AGENTS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        model_count=2,
    )
    leader = _make_unit(
        "Ministorum Priest",
        keywords=["INFANTRY", "CHARACTER", "MINISTORUM PRIEST"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    solo_leader = _make_unit(
        "Solo Priest",
        keywords=["INFANTRY", "CHARACTER", "MINISTORUM PRIEST"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    psyker_target = _make_unit(
        "Enemy Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    non_psyker_target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (bodyguard, leader, solo_leader):
        ia_army.add_unit(unit)
    for unit in (psyker_target, non_psyker_target):
        enemy_army.add_unit(unit)
    _deploy_unit(game, bodyguard, 0.0, 0.0)
    _deploy_unit(game, leader, 0.0, 0.0)
    _deploy_unit(game, solo_leader, 2.0, 0.0)
    _deploy_unit(game, psyker_target, 12.0, 0.0)
    _deploy_unit(game, non_psyker_target, 14.0, 0.0)
    _attach_leader(bodyguard, leader)

    _apply_enhancement(
        leader,
        enhancement_id="000009130005",
        enhancement_name="Witch Hunter",
        description="While the bearer is leading a unit, each time a model in that unit makes an attack that targets a PSYKER unit, you can re-roll the Hit roll.",
    )
    _apply_enhancement(
        solo_leader,
        enhancement_id="000009130005",
        enhancement_name="Witch Hunter",
        description="While the bearer is leading a unit, each time a model in that unit makes an attack that targets a PSYKER unit, you can re-roll the Hit roll.",
    )

    profile = _attack_profile(is_ranged=True)

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        led_result = profile._hit_target_with_tracking(
            psyker_target,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        assert int(led_result.get("reroll", 0) or 0) == 5
        assert any("Witch Hunter" in str(effect) for effect in list(led_result.get("special_effects", []) or []))

        non_psyker_result = profile._hit_target_with_tracking(
            non_psyker_target,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        assert "reroll" not in non_psyker_result

        solo_result = profile._hit_target_with_tracking(
            psyker_target,
            solo_leader.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        assert "reroll" not in solo_result
