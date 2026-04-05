from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.hazardous import (
    apply_hazardous_roll_modifier,
    hazardous_fail_on_values,
    is_hazardous_failure,
)


def _make_profile(description: str):
    wargear_data = {
        "name": "Test Weapon",
        "type": "Ranged",
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": description,
    }
    wargear = Wargear(wargear_data)
    return list(wargear.profiles.values())[0]


def test_overcharge_keyword_detected():
    profile = _make_profile("hazardous, overcharge")
    assert profile.is_overcharge() is True


def test_overcharge_hazardous_modifier_applies():
    profile = _make_profile("hazardous, overcharge")
    assert hazardous_fail_on_values(profile) == [1, 2, 3]
    assert apply_hazardous_roll_modifier(profile, 3) == 1
    assert is_hazardous_failure(profile, 3) is True
    assert is_hazardous_failure(profile, 4) is False


def test_non_overcharge_hazardous_unchanged():
    profile = _make_profile("hazardous")
    assert hazardous_fail_on_values(profile) == [1]
    assert apply_hazardous_roll_modifier(profile, 3) == 3
    assert is_hazardous_failure(profile, 1) is True
    assert is_hazardous_failure(profile, 2) is False
