from types import SimpleNamespace


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


def test_has_super_heavy_walker_uses_cache_and_respects_invalidation():
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

    call_count = 0
    original_find = unit._find_ability_with_patterns

    def _counting_find(patterns, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_find(patterns, *args, **kwargs)

    unit._find_ability_with_patterns = _counting_find

    assert unit.has_super_heavy_walker() is True
    assert unit.has_super_heavy_walker() is True
    assert call_count == 1

    unit._invalidate_ability_cache()
    assert unit.has_super_heavy_walker() is True
    assert call_count == 2


def test_iter_conditioned_text_segments_uses_state_not_stale_text_cache():
    leader = _make_unit(name="Leader")
    bodyguard = SimpleNamespace(
        name="Test Bodyguard",
        keywords=["TEST BODYGUARD"],
        faction_keywords=[],
    )
    text = (
        "If this model is attached to an Test Bodyguard unit during the Declare Battle Formations step, "
        "this model has the Scouts 6\" ability."
    )

    leader.attached_to = bodyguard
    first = leader._iter_conditioned_text_segments(text)
    assert first

    leader.attached_to = None
    second = leader._iter_conditioned_text_segments(text)
    assert second == []

    leader.attached_to = bodyguard
    third = leader._iter_conditioned_text_segments(text)
    assert third
