from __future__ import annotations

from types import SimpleNamespace

import pytest

import warhammer40k_ai.utility.aura_effects as aura_effects
import warhammer40k_ai.units.unit_mixins.positioning_mixin as positioning_mixin


class _MockDatasheet:
    def __init__(self, *, name: str = "Test Unit", abilities=None):
        self.name = name
        self.id = f"{name}-id"
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
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


def _make_unit(*, name: str = "Test Unit", abilities=None):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name=name, abilities=abilities))


def test_aura_parse_cache_hit_avoids_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    ability = SimpleNamespace(
        name="Beacons of Rage (Aura)",
        description='While a friendly WORLD EATERS unit is within 6" of this unit, each time a model in that unit makes a melee attack, add 1 to the Hit roll.',
        parameter="",
    )
    aura_effects.clear_aura_parse_cache()
    _ = aura_effects._cached_parse_aura_spec(
        "_parse_simple_plus_one_aura",
        ability,
        aura_effects._parse_simple_plus_one_aura,
    )

    def _raise(*_args, **_kwargs):
        raise AssertionError("Regex function should not be called on cached parse hit.")

    monkeypatch.setattr(aura_effects.re, "search", _raise)
    monkeypatch.setattr(aura_effects.re, "sub", _raise)

    out = aura_effects._cached_parse_aura_spec(
        "_parse_simple_plus_one_aura",
        ability,
        aura_effects._parse_simple_plus_one_aura,
    )
    assert isinstance(out, dict)
    assert out.get("hit_bonus") == 1


def test_indexed_find_ability_cache_hit_avoids_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    unit = _make_unit(
        name="Chaos Knight",
        abilities=[
            {
                "name": "Super-heavy Walker",
                "description": "This model has the Super-heavy Walker ability.",
                "type": "Abilities",
                "parameter": None,
            }
        ],
    )
    first_found, first_value = unit._find_ability_with_patterns(["super-heavy walker"])
    assert first_found is True
    assert first_value is None

    def _raise(*_args, **_kwargs):
        raise AssertionError("Regex function should not be called on indexed cache hit.")

    monkeypatch.setattr(positioning_mixin.re, "search", _raise)
    monkeypatch.setattr(positioning_mixin.re, "compile", _raise)

    second_found, second_value = unit._find_ability_with_patterns(["super-heavy walker"])
    assert second_found is True
    assert second_value is None

