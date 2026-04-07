from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        movement: str = "5",
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
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
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
    faction_name: str = "Orks",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    movement: str = "5",
    toughness: str = "5",
    wounds: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        faction_name=faction_name,
        model_count=model_count,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
        movement=movement,
        toughness=toughness,
        wounds=wounds,
    )
    return Unit(datasheet)


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


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


class _MeleeWargear:
    def __init__(self, name: str = "Choppa") -> None:
        self.name = name

    def is_melee(self) -> bool:
        return True

    def is_ranged(self) -> bool:
        return False


def _melee_profile(*, description: str = "") -> WargearProfile:
    return WargearProfile(
        "Choppa",
        {
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=_MeleeWargear(),
    )


def _make_war_horde_army() -> Army:
    army = Army.with_detachment("Orks", "War Horde")
    army.faction_id = "ORK"
    return army


def test_follow_me_ladz_grants_move_bonus_while_leading():
    army = _make_war_horde_army()
    bodyguard = _make_unit(
        "Boyz",
        "orks-bodyguard",
        keywords=["Infantry"],
        faction_keywords=["ORKS"],
        movement="5",
    )
    leader = _make_unit(
        "Boss",
        "orks-leader",
        keywords=["Character", "Infantry"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
        movement="5",
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)

    leader.attach_to_unit(bodyguard)
    _apply_enhancement(army, leader, "Follow Me Ladz")

    assert bodyguard.models[0].movement == 7
    assert leader.models[0].movement == 7

    leader.detach_from_unit()

    assert bodyguard.models[0].movement == 5
    assert leader.models[0].movement == 5


def test_kunnin_but_brutal_allows_fallback_shoot_and_charge_while_leading():
    army = _make_war_horde_army()
    bodyguard = _make_unit(
        "Boyz",
        "orks-bodyguard-2",
        keywords=["Infantry"],
        faction_keywords=["ORKS"],
    )
    leader = _make_unit(
        "Boss",
        "orks-leader-2",
        keywords=["Character", "Infantry"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)

    leader.attach_to_unit(bodyguard)
    _apply_enhancement(army, leader, "Kunnin' But Brutal")

    assert bodyguard.has_fell_back_and_shoot() is True
    assert bodyguard.can_charge_after_fall_back() is True

    leader.detach_from_unit()

    assert bodyguard.has_fell_back_and_shoot() is False
    assert bodyguard.can_charge_after_fall_back() is False


def test_headwoppas_killchoppa_grants_devastating_wounds_to_bearer():
    army = _make_war_horde_army()
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    leader = _make_unit(
        "Boss",
        "orks-leader-3",
        keywords=["Character", "Infantry"],
        faction_keywords=["ORKS"],
    )
    target = _make_unit(
        "Target",
        "enemy-target",
        faction_name="Enemy",
        keywords=["Infantry"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(leader)
    enemy_army.add_unit(target)

    _apply_enhancement(army, leader, "Headwoppa's Killchoppa")

    attacker = leader.models[0]
    profile = _melee_profile()
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        target,
        attacker,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert attack_instance.get("bonus_devastating_wounds") is True

    extra_profile = _melee_profile(description="Extra Attacks")
    extra_attack_instance = {"_aura_attack_mods": _aura_stub()}
    extra_profile._hit_target_with_tracking(
        target,
        attacker,
        extra_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not extra_attack_instance.get("bonus_devastating_wounds")


def test_supa_cybork_body_grants_fnp_4():
    army = _make_war_horde_army()
    leader = _make_unit(
        "Boss",
        "orks-leader-4",
        keywords=["Character", "Infantry"],
        faction_keywords=["ORKS"],
    )
    army.add_unit(leader)

    _apply_enhancement(army, leader, "Supa-Cybork Body")

    assert (4, None) in leader.has_feel_no_pain()
