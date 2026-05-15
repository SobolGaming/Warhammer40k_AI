from __future__ import annotations


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


def test_trait_index_updates_on_structure_invalidation() -> None:
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
    assert unit.has_super_heavy_walker() is True
    index_before = unit._get_cached_ability_trait_index()
    generation_before = int(index_before.get("generation", -1))

    unit.possible_abilities = []
    unit._invalidate_ability_cache()

    index_after = unit._get_cached_ability_trait_index()
    generation_after = int(index_after.get("generation", -1))
    assert generation_after > generation_before
    assert unit.has_super_heavy_walker() is False


def test_activity_invalidation_bumps_only_activity_generation() -> None:
    unit = _make_unit(name="Infantry")
    structure_before = int(getattr(unit, "_ability_structure_generation", 0) or 0)
    activity_before = int(getattr(unit, "_ability_activity_generation", 0) or 0)

    unit._invalidate_ability_activity_cache()

    structure_after = int(getattr(unit, "_ability_structure_generation", 0) or 0)
    activity_after = int(getattr(unit, "_ability_activity_generation", 0) or 0)
    assert structure_after == structure_before
    assert activity_after == activity_before + 1


def test_activity_state_signature_uses_generation_token_until_generation_changes(monkeypatch) -> None:
    unit = _make_unit(name="Infantry")
    original = unit._ability_activity_unit_signature
    calls = {"count": 0}

    def counted_signature(value):
        calls["count"] += 1
        return original(value)

    monkeypatch.setattr(unit, "_ability_activity_unit_signature", counted_signature)

    first = unit._ability_activity_state_signature()
    second = unit._ability_activity_state_signature()
    assert first == second
    assert calls["count"] == 0

    unit._invalidate_ability_activity_cache()
    third = unit._ability_activity_state_signature()
    assert third != first
    assert calls["count"] == 0


def test_firing_deck_uses_trait_value_index() -> None:
    unit = _make_unit(
        name="Transport",
        abilities=[
            {
                "name": "Firing Deck",
                "description": "Firing Deck 12",
                "type": "Abilities",
                "parameter": None,
            }
        ],
    )
    found, value = unit.has_firing_deck()
    assert found is True
    assert value == 12


def test_find_ability_with_patterns_uses_indexed_fast_path() -> None:
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

    def _explode():
        raise AssertionError("Fallback scanner should not run for indexed super-heavy pattern.")

    unit._iter_active_possible_abilities = _explode
    found, value = unit._find_ability_with_patterns(["super-heavy walker"])
    assert found is True
    assert value is None
