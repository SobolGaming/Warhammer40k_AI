from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        datasheet_id: str,
        faction_name: str = "Adeptus Custodes",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "5",
        wounds: str = "6",
        save: str = "3",
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
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "5",
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
    wounds: str = "6",
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
            attached_to=attached_to,
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
    custodes_army = Army.with_detachment("Adeptus Custodes", "Talons Of The Emperor")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, custodes_player, enemy_player


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AC",
        detachment="Talons Of The Emperor",
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


def _ranged_profile(*, strength: int = 4, damage: int = 2) -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Gun",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile(*, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "2+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
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
    )


def test_talons_enhancement_descriptors_registered() -> None:
    aegis = get_enhancement_tool_descriptor(enhancement_id="000008921002")
    assert aegis is not None
    assert aegis.name == "Aegis Projector"
    assert aegis.effect == "set_failed_save_damage_to_zero"

    champion = get_enhancement_tool_descriptor(enhancement_id="000008921003")
    assert champion is not None
    assert champion.name == "Champion of the Imperium"
    assert champion.effect == "increase_bearer_talons_aura_range"

    gift = get_enhancement_tool_descriptor(enhancement_id="000008921004")
    assert gift is not None
    assert gift.name == "Gift of Terran Artifice"
    assert gift.effect == "add_wound_roll_bonus_to_bearer_melee_attacks"

    radiant = get_enhancement_tool_descriptor(enhancement_id="000008921005")
    assert radiant is not None
    assert radiant.name == "Radiant Mantle"
    assert radiant.effect == "subtract_hit_roll_when_attacker_within_range"


def test_aegis_projector_sets_first_failed_save_damage_to_zero_once_per_turn() -> None:
    game, custodes_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Shield-Captain",
        "ac-aegis-bearer",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
        save="3",
    )
    attacker_unit = _make_unit(
        "Enemy Shooter",
        "enemy-aegis-attacker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(attacker_unit)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(attacker_unit, 10.0, 0.0)
    game.map.units = [bearer_unit, attacker_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000008921002", enhancement_name="Aegis Projector")
    target_model = bearer_unit.models[0]
    attacker_model = attacker_unit.models[0]
    profile = _ranged_profile(strength=6, damage=2)

    attack_instance = {}
    save_result = profile._save_with_tracking(
        target_model,
        attack_instance,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result["saved"] is False
    assert attack_instance.get("force_damage_zero") is True

    damage_result = profile._damage_target_with_tracking(
        target_model,
        attacker_model,
        attack_instance,
        roll_value=2,
        allow_rerolls=False,
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 0

    second_attack = {}
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


def test_champion_of_the_imperium_increases_revered_companions_aura_to_nine() -> None:
    game, custodes_player, enemy_player = _build_game()
    anathema_source = _make_unit(
        "Vigilators",
        "ac-champion-source-a",
        keywords=["INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodes_target = _make_unit(
        "Custodian Guard",
        "ac-champion-target-c",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    non_anathema_source = _make_unit(
        "Custodian Wardens",
        "ac-champion-source-c",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    anathema_attacker = _make_unit(
        "Prosecutors",
        "ac-champion-attacker-a",
        keywords=["INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-champion",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (anathema_source, custodes_target, non_anathema_source, anathema_attacker):
        custodes_player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(anathema_source, 0.0, 0.0)
    _deploy_unit(custodes_target, 8.0, 0.0)
    _deploy_unit(non_anathema_source, 0.0, 10.0)
    _deploy_unit(anathema_attacker, 8.0, 10.0)
    _deploy_unit(enemy, 20.0, 10.0)
    game.map.units = [anathema_source, custodes_target, non_anathema_source, anathema_attacker, enemy]
    game.rebuild_entity_registry()

    mgr = custodes_player.army.adeptus_custodes_detachments

    fnp_value, _condition, _source = mgr.revered_companions_null_aegis_fnp(custodes_target)
    assert int(fnp_value) == 0
    hit_bonus, _source = mgr.revered_companions_deadly_unity_hit_bonus(anathema_attacker.models[0], enemy)
    assert int(hit_bonus) == 0

    _apply_enhancement(
        anathema_source,
        enhancement_id="000008921003",
        enhancement_name="Champion of the Imperium",
    )
    _apply_enhancement(
        non_anathema_source,
        enhancement_id="000008921003",
        enhancement_name="Champion of the Imperium",
    )

    fnp_value, condition, source = mgr.revered_companions_null_aegis_fnp(custodes_target)
    assert int(fnp_value) == 5
    assert "psychic" in str(condition or "").lower()
    assert "revered companions" in str(source or "").lower()

    hit_bonus, source = mgr.revered_companions_deadly_unity_hit_bonus(anathema_attacker.models[0], enemy)
    assert int(hit_bonus) == 1
    assert "revered companions" in str(source or "").lower()


def test_gift_of_terran_artifice_applies_bearer_melee_wound_bonus_only() -> None:
    game, custodes_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Shield-Captain",
        "ac-gift-bearer",
        model_count=2,
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Tough Unit",
        "enemy-gift",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(enemy, 2.0, 0.0)
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        bearer_unit,
        enhancement_id="000008921004",
        enhancement_name="Gift of Terran Artifice",
    )
    bearer = _enhancement_bearer_model(bearer_unit)
    assert bearer is not None
    non_bearer = next(model for model in list(bearer_unit.models or []) if model is not bearer)

    profile = _melee_profile(strength=4, damage=1)
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


def test_radiant_mantle_applies_hit_penalty_only_within_twelve() -> None:
    game, custodes_player, enemy_player = _build_game()
    target_unit = _make_unit(
        "Custodian Guard",
        "ac-radiant-target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_attacker = _make_unit(
        "Enemy Shooter",
        "enemy-radiant-attacker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(enemy_attacker)
    _deploy_unit(target_unit, 0.0, 0.0)
    _deploy_unit(enemy_attacker, 10.0, 0.0)
    game.map.units = [target_unit, enemy_attacker]
    game.rebuild_entity_registry()

    _apply_enhancement(target_unit, enhancement_id="000008921005", enhancement_name="Radiant Mantle")
    profile = _ranged_profile(strength=4, damage=1)

    in_range = profile._hit_target_with_tracking(
        target_unit,
        enemy_attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(in_range.get("hit", False)) is False

    _deploy_unit(enemy_attacker, 20.0, 0.0)
    out_of_range = profile._hit_target_with_tracking(
        target_unit,
        enemy_attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(out_of_range.get("hit", False))
