from __future__ import annotations

import pytest

from warhammer40k_ai.units.unit import Unit


@pytest.mark.parametrize(
    ("characteristic", "private_attr", "raw_attr", "value"),
    (
        ("movement", "_movement", "_movement_raw", 6),
        ("toughness", "_toughness", "_toughness_raw", 5),
        ("save", "_save", "_save_raw", 3),
        ("leadership", "_leadership", "_leadership_raw", 7),
        ("objective_control", "_objective_control", "_objective_control_raw", 2),
    ),
)
def test_get_effective_model_characteristic_prefers_private_backing_fields(
    monkeypatch: pytest.MonkeyPatch,
    characteristic: str,
    private_attr: str,
    raw_attr: str,
    value: int,
) -> None:
    """
    Regression guard for recursive property lookups:
    base characteristic resolution must not read public model properties when private backing values exist.
    """

    unit = Unit.__new__(Unit)
    unit.has_siege_crawler = lambda: False

    def _collect_modifiers(_unit, _model, ckey, *, base_val, base_raw, game_map=None):
        assert ckey == characteristic
        assert int(base_val) == int(value)
        assert str(base_raw) == str(value)
        return [], 0, game_map

    monkeypatch.setattr(Unit, "_collect_characteristic_modifiers", staticmethod(_collect_modifiers))

    class ModelDouble:
        pass

    def _forbidden_property_access(_self):
        raise AssertionError(f"Unexpected public property read: {characteristic}")

    setattr(ModelDouble, characteristic, property(_forbidden_property_access))
    model = ModelDouble()
    setattr(model, private_attr, int(value))
    setattr(model, raw_attr, str(value))

    resolved = Unit.get_effective_model_characteristic(unit, model, characteristic)
    assert int(resolved) == int(value)
