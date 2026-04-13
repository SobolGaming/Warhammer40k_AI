from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


DOCTRINA_IMPERATIVES_TEXT = "Doctrina Imperatives."


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        save: int = 3,
        wounds: int = 4,
        inv_sv: int = 7,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(int(inv_sv)),
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    save: int = 3,
    wounds: int = 4,
    inv_sv: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            save=save,
            wounds=wounds,
            inv_sv=inv_sv,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Eradication Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, admech_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ADM",
        detachment="Eradication Cohort",
        points=0,
        description="",
    ).apply_to_unit(unit)


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


def _ranged_profile(*, range_value: int = 24, strength: str = "4", ap: str = "0") -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": str(range_value),
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile(*, attacks: str = "1", damage: str = "1", strength: str = "8", ap: str = "-2") -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_eradication_cohort_enhancement_descriptors_registered():
    expected = {
        "000010747002": (
            "Belicosa-Class Capacitor Vanes",
            "treat_conqueror_and_protector_imperatives_as_active_for_bearer_unit",
        ),
        "000010747003": (
            "Martial Signatum Amplificator",
            "grant_skitarii_keyword_to_bearer_unit",
        ),
        "000010747004": (
            "Omnicogitator",
            "add_ranged_range_and_strength_to_bearer_unit",
        ),
        "000010747005": (
            "Omnissiah's Fury",
            "add_melee_attacks_ap_and_damage_to_bearer_melee_weapons",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_belicosa_class_capacitor_vanes_enables_both_imperatives_for_bearer_unit():
    game, admech_army, enemy_army = _build_game()
    leader = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010747002", enhancement_name="Belicosa-Class Capacitor Vanes")

    doctrina_mgr = admech_army.doctrina_imperatives
    active_keys = doctrina_mgr.get_active_imperative_keys_for_unit(bodyguard, game=game)
    assert "PROTECTOR" in active_keys
    assert "CONQUEROR" in active_keys

    from warhammer40k_ai.units import wargear as wargear_mod

    hit_seq = iter([1, 5])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(hit_seq)
    try:
        hit_result = _ranged_profile()._hit_target_with_tracking(
            enemy,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    wound_seq = iter([1, 4])
    wargear_mod.get_roll = lambda _spec: next(wound_seq)
    try:
        wound_result = _melee_profile()._wound_target_with_tracking(
            enemy,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result.get("reroll") == 5
    assert wound_result.get("reroll") == 4


def test_martial_signatum_amplificator_grants_skitarii_keyword_to_bearer_unit():
    game, admech_army, enemy_army = _build_game()
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Kataphron Destroyers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010747003", enhancement_name="Martial Signatum Amplificator")

    assert bodyguard.has_any_keyword("SKITARII") is True
    assert admech_army.doctrina_imperatives.select_imperative("PROTECTOR", battle_round=1) is True

    from warhammer40k_ai.units import wargear as wargear_mod

    hit_seq = iter([1, 5])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(hit_seq)
    try:
        hit_result = _ranged_profile()._hit_target_with_tracking(
            enemy,
            bodyguard.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result.get("reroll") == 5


def test_omnicogitator_adds_range_and_strength_to_ranged_weapons_in_bearer_unit():
    game, admech_army, enemy_army = _build_game()
    leader = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Kataphron Breachers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010747004", enhancement_name="Omnicogitator")

    profile = _ranged_profile(range_value=24, strength="4")
    mgr = admech_army.adeptus_mechanicus_detachments
    range_bonus, strength_bonus, source = mgr.eradication_omnicogitator_ranged_bonuses(
        bodyguard.models[0],
        weapon_profile=profile,
    )
    assert int(range_bonus) == 6
    assert int(strength_bonus) == 1
    assert str(source or "") == "Omnicogitator"
    assert int(profile._effective_range_max(bodyguard.models[0])) == 30

    wound_result = profile._wound_target_with_tracking(
        enemy,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Omnicogitator" in str(reason or "") for reason in list(wound_result.get("modifiers", []) or []))


def test_omnissiahs_fury_applies_only_to_bearer_melee_weapons():
    game, admech_army, enemy_army = _build_game()
    leader = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        save=7,
        wounds=40,
        inv_sv=7,
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010747005", enhancement_name="Omnissiah's Fury")
    profile = _melee_profile(attacks="1", damage="1", strength="8", ap="-2")

    assert int(profile.get_effective_ap(leader.models[0], enemy)) == -3
    assert int(profile.get_effective_ap(bodyguard.models[0], enemy)) == -2

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        bearer_result = profile.attack(enemy, leader.models[0], game_map=game.map)
        other_result = profile.attack(enemy, bodyguard.models[0], game_map=game.map)

    assert int(bearer_result.attacks_rolled or 0) == 3
    assert int(other_result.attacks_rolled or 0) == 1
    assert any(
        "Enhancement bearer +1D" in str(effect or "")
        for dmg in list(bearer_result.damage_results or [])
        for effect in list((dmg or {}).get("special_effects", []) or [])
    )
    assert not any(
        "Enhancement bearer +1D" in str(effect or "")
        for dmg in list(other_result.damage_results or [])
        for effect in list((dmg or {}).get("special_effects", []) or [])
    )
