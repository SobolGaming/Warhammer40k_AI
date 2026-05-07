#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.roster.roster_synthesis import RosterSynthesisSeed, synthesize_rosters
from warhammer40k_ai.waha_helper import WahaHelper


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synthesize deterministic 10th-edition army rosters from seed constraints."
    )
    parser.add_argument("--max-points", type=int, required=True, help="Required roster point cap.")
    parser.add_argument(
        "--max-under-cap-allowance",
        type=int,
        default=None,
        help="Optional maximum unused points allowed before no-solution diagnostics are returned.",
    )
    parser.add_argument("--faction", default=None, help="Optional faction constraint.")
    parser.add_argument("--chapter", default=None, help="Optional Space Marines chapter constraint.")
    parser.add_argument("--detachment", default=None, help="Optional detachment constraint.")
    parser.add_argument(
        "--style",
        action="append",
        default=[],
        help="Soft style text/tag. Repeat or pass a phrase such as 'melee offensive daemonkin'.",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Optional longer soft style description.",
    )
    parser.add_argument(
        "--include-unit",
        action="append",
        default=[],
        help="Hard required unit name. Repeat for multiple required units.",
    )
    parser.add_argument(
        "--exclude-unit",
        action="append",
        default=[],
        help="Hard excluded unit name. Repeat for multiple excluded units.",
    )
    parser.add_argument(
        "--daemonic-allegiance",
        action="append",
        default=[],
        help=(
            "Required Daemonic Allegiance selection in 'Unit Name=KEYWORD' form. "
            "Repeat for multiple units, e.g. 'Soul Grinder=TZEENTCH'."
        ),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of ranked legal candidates to return.",
    )
    parser.add_argument("--random-seed", type=int, default=None, help="Optional deterministic tie-break seed.")
    parser.add_argument(
        "--rules-bundle-id",
        default="rules_bundle:10th_local_wahapedia",
        help="Rules bundle provenance id recorded in the report.",
    )
    parser.add_argument(
        "--rules-data-dir",
        default="wahapedia_data",
        help="Local Wahapedia data directory.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for synthesis_report.json, candidate blueprints, and army-list text exports.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    helper = WahaHelper(str(Path(args.rules_data_dir).expanduser()))
    seed = RosterSynthesisSeed(
        max_points=args.max_points,
        max_under_cap_allowance=args.max_under_cap_allowance,
        faction=args.faction,
        chapter=args.chapter,
        detachment=args.detachment,
        style_tags=tuple(args.style or []),
        description_text=args.description,
        include_units=tuple(args.include_unit or []),
        exclude_units=tuple(args.exclude_unit or []),
        daemonic_allegiances=tuple(args.daemonic_allegiance or []),
    )
    report = synthesize_rosters(
        seed,
        waha_helper=helper,
        rules_bundle_id=args.rules_bundle_id,
        top_k=args.top_k,
        random_seed=args.random_seed,
        output_dir=str(output_dir),
    )
    print(f"Synthesis report written: {output_dir / 'synthesis_report.json'}")
    print(f"Candidates: {len(report.candidates)}")
    if report.best_candidate is not None:
        candidate = report.best_candidate
        print(
            "Best candidate: "
            f"{candidate.army_blueprint.faction} / {candidate.army_blueprint.primary_detachment_type} "
            f"{candidate.points}/{seed.max_points} points"
        )
        if candidate.export_path:
            print(f"Army list export: {candidate.export_path}")
    if report.diagnostics:
        print(json.dumps({"diagnostics": list(report.diagnostics)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
