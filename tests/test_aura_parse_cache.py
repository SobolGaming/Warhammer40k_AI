from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.utility.aura_effects import (
    _cached_parse_aura_spec,
    _parse_simple_plus_one_aura,
    clear_aura_parse_cache,
)
from warhammer40k_ai.utility.regex_hotspot_metrics import (
    disable as disable_regex_hotspot_metrics,
    enable as enable_regex_hotspot_metrics,
    reset as reset_regex_hotspot_metrics,
    snapshot as snapshot_regex_hotspot_metrics,
)


def _ability(name: str, description: str):
    return SimpleNamespace(name=name, description=description, parameter="")


def test_cached_parse_aura_spec_runs_parser_once_per_key() -> None:
    clear_aura_parse_cache()
    disable_regex_hotspot_metrics()
    reset_regex_hotspot_metrics()
    enable_regex_hotspot_metrics(reset=True)

    ability = _ability(
        "Beacons of Rage (Aura)",
        'While a friendly WORLD EATERS unit is within 6" of this unit, each time a model in that unit makes a melee attack, add 1 to the Hit roll.',
    )
    first = _cached_parse_aura_spec("_parse_simple_plus_one_aura", ability, _parse_simple_plus_one_aura)
    second = _cached_parse_aura_spec("_parse_simple_plus_one_aura", ability, _parse_simple_plus_one_aura)
    counts = snapshot_regex_hotspot_metrics()

    assert first == second
    assert int(counts.get("aura_effects:_parse_simple_plus_one_aura", 0)) == 1

    disable_regex_hotspot_metrics()
    reset_regex_hotspot_metrics()
    clear_aura_parse_cache()

