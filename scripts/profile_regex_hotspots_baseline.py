from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from warhammer40k_ai.utility.aura_effects import (
    _parse_add_oc_aura,
    _parse_full_hit_reroll_aura,
    _parse_reroll_ones_aura,
    _parse_simple_plus_one_aura,
    _parse_strength_aura,
    _parse_toughness_aura,
)
from warhammer40k_ai.utility.profiling_controller import ProfilingController
from warhammer40k_ai.utility.regex_hotspot_metrics import enable, snapshot


def _ability(name: str, description: str):
    return SimpleNamespace(name=name, description=description)


def _build_sample_abilities() -> list:
    return [
        _ability(
            "Beacons of Rage (Aura)",
            'While a friendly WORLD EATERS unit is within 6" of this unit, each time a model in that unit makes a melee attack, add 1 to the Hit roll.',
        ),
        _ability(
            "Arch-Contaminator (Aura)",
            'While a friendly DEATH GUARD unit is within 6" of this model, you can re-roll Wound rolls of 1.',
        ),
        _ability(
            "Aura of Command (Aura)",
            'While a friendly ADEPTUS ASTARTES unit is within 6" of this model, each time a model in that unit makes an attack, you can re-roll the Hit roll.',
        ),
        _ability(
            "Objective Aura (Aura)",
            'While a friendly HERETIC ASTARTES unit is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit.',
        ),
        _ability(
            "Might of the Warp (Aura)",
            'While a friendly LEGIONES DAEMONICA unit is within 6" of this model, add 1 to the Strength characteristic of weapons equipped by models in that unit.',
        ),
        _ability(
            "Warp Bulwark (Aura)",
            'While a friendly LEGIONES DAEMONICA unit is within 6" of this model, add 1 to the Toughness characteristic of models in that unit.',
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture cProfile baseline for regex hotspot parsers.")
    parser.add_argument("--iterations", type=int, default=10000, help="Number of parse loop iterations.")
    parser.add_argument("--label", type=str, default="regex_hotspot_baseline", help="Output profile label.")
    args = parser.parse_args()

    enable(reset=True)
    prof = ProfilingController(out_dir="profiles", sort_by="tottime", lines=120)

    abilities = _build_sample_abilities()
    iterations = max(1, int(args.iterations or 1))

    prof.enable()
    for _ in range(iterations):
        for ability in abilities:
            _parse_simple_plus_one_aura(ability)
            _parse_reroll_ones_aura(ability)
            _parse_full_hit_reroll_aura(ability)
            _parse_add_oc_aura(ability)
            _parse_strength_aura(ability)
            _parse_toughness_aura(ability)
    prof.disable()

    txt_path, prof_path = prof.dump(label=str(args.label or "regex_hotspot_baseline"), write_binary_prof=True)
    counts = snapshot()

    print(f"profile_text={txt_path}")
    if prof_path is not None:
        print(f"profile_binary={prof_path}")
    print(f"regex_hotspot_keys={len(counts)}")
    for key, value in sorted(counts.items(), key=lambda item: (-int(item[1]), item[0])):
        print(f"{key}={int(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
