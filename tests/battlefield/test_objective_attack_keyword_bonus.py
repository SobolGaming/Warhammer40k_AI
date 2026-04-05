from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


def _make_profile(*, weapon_type: str = "Ranged"):
    parent = SimpleNamespace(
        name="Test Gun",
        is_melee=lambda: weapon_type.lower() == "melee",
        is_ranged=lambda: weapon_type.lower() == "ranged",
    )
    data = {
        "range": "24" if weapon_type.lower() == "ranged" else "Melee",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _make_unit_with_ability(keyword: str, *, attack_type: str = "ranged") -> Unit:
    unit = Unit.__new__(Unit)
    unit.name = "Attacker Unit"
    atype = str(attack_type or "ranged").strip().lower()
    unit.possible_abilities = [
        SimpleNamespace(
            name="Objective Targeting",
            description=(
                f"Each time this model makes a {atype} attack that targets a unit that is within range of one or more "
                f"objective markers, that attack has the [{keyword}] ability."
            ),
        )
    ]
    unit.models = []
    unit.special_rules = {}
    unit.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
    unit.keywords = []
    unit.faction_keywords = []
    unit.get_parent_army = lambda: SimpleNamespace(
        player=SimpleNamespace(game=None, name="P1", id="P1", has_control=lambda: False)
    )
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_models_for_wound_allocation = lambda: list(unit.models)
    unit.is_battle_shocked = lambda: False
    unit.is_in_reserves = lambda: False
    unit.is_alive = lambda: True
    unit.has_stealth = lambda: False
    unit.has_first_prince_tzeentch_defense = lambda: False
    unit.has_advance_and_shoot = lambda: False
    return unit


def _make_target(*, keywords=None, toughness: int = 4):
    kw_list = list(keywords or [])

    def _has_keyword(value: str) -> bool:
        key = str(value or "").strip().lower()
        return any(key == str(k or "").strip().lower() for k in kw_list)

    target = SimpleNamespace(
        name="Target Unit",
        is_vehicle=False,
        is_monster=False,
        models=[SimpleNamespace(is_alive=True)],
        toughness=int(toughness),
        has_keyword=_has_keyword,
        has_any_keyword=_has_keyword,
    )
    target.get_attached_unit_root = lambda: target
    target.is_battle_shocked = lambda: False
    target.is_in_reserves = lambda: False
    return target


def test_objective_attack_keyword_ignores_cover_applies():
    unit = _make_unit_with_ability("IGNORES COVER")
    unit._target_within_objective_range = lambda _target, _game_map=None: True

    attacker = SimpleNamespace(name="Attacker", parent_unit=unit, _id="attacker-model-1")
    target = _make_target()
    profile = _make_profile()
    attack_instance = {}

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        profile._hit_target_with_tracking(target, attacker, attack_instance)

    assert attack_instance.get("ignores_cover") is True

    unit._target_within_objective_range = lambda _target, _game_map=None: False
    attack_instance = {}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        profile._hit_target_with_tracking(target, attacker, attack_instance)

    assert not attack_instance.get("ignores_cover", False)


def test_objective_attack_keyword_lethal_hits_applies():
    unit = _make_unit_with_ability("LETHAL HITS")
    unit._target_within_objective_range = lambda _target, _game_map=None: True

    attacker = SimpleNamespace(name="Attacker", parent_unit=unit, _id="attacker-model-1")
    target = _make_target()
    profile = _make_profile()
    attack_instance = {}

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        hit_result = profile._hit_target_with_tracking(target, attacker, attack_instance)

    assert attack_instance.get("lethal_hit") is True
    assert "Lethal Hits" in hit_result.get("special_effects", [])


def test_objective_attack_keyword_lance_applies():
    unit = _make_unit_with_ability("LANCE", attack_type="melee")
    unit._target_within_objective_range = lambda _target, _game_map=None: True
    unit.round_state.charged_this_round = True

    attacker = SimpleNamespace(name="Attacker", parent_unit=unit, _id="attacker-model-1")
    target = _make_target()
    profile = _make_profile(weapon_type="Melee")
    attack_instance = {}

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 3]):
        profile._hit_target_with_tracking(target, attacker, attack_instance)
        wound_result = profile._wound_target_with_tracking(target, attacker, attack_instance)

    assert wound_result.get("wound") is True

    unit._target_within_objective_range = lambda _target, _game_map=None: False
    attack_instance = {}
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 3]):
        profile._hit_target_with_tracking(target, attacker, attack_instance)
        wound_result = profile._wound_target_with_tracking(target, attacker, attack_instance)

    assert wound_result.get("wound") is False


def test_objective_attack_keyword_anti_applies():
    unit = _make_unit_with_ability("ANTI-VEHICLE 4+")
    unit._target_within_objective_range = lambda _target, _game_map=None: True

    attacker = SimpleNamespace(name="Attacker", parent_unit=unit, _id="attacker-model-1")
    target = _make_target(keywords=["VEHICLE"], toughness=8)
    profile = _make_profile(weapon_type="Ranged")
    attack_instance = {}

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 4]):
        profile._hit_target_with_tracking(target, attacker, attack_instance)
        wound_result = profile._wound_target_with_tracking(target, attacker, attack_instance)

    assert wound_result.get("wound") is True
    assert any("Anti-VEHICLE 4+" in s for s in wound_result.get("special_effects", []))
