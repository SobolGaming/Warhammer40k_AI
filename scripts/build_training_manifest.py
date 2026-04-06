#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.engine.training_manifest import (
    PRE_ML_BASELINE_GATE_PROFILE_ID,
    build_training_manifest,
    load_training_records,
    save_training_manifest,
    validate_gate_profile_compliance,
    validate_training_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a training data manifest from DecisionRecords.")
    parser.add_argument("--input", required=True, help="Input decision records JSON path.")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    parser.add_argument("--source-tag", required=True, help="Data source tag (human, heuristic, self_play, mixed).")
    parser.add_argument("--min-tier3-records", type=int, default=10000, help="Minimum Tier3 pretraining gate.")
    parser.add_argument("--rules-bundle-id", action="append", default=[], help="Repeatable rules bundle filter.")
    parser.add_argument(
        "--descriptor-bundle-id",
        action="append",
        default=[],
        help="Repeatable descriptor-bundle filter.",
    )
    parser.add_argument(
        "--mission-descriptor-id",
        action="append",
        default=[],
        help="Repeatable mission descriptor filter.",
    )
    parser.add_argument(
        "--objective-descriptor-id",
        action="append",
        default=[],
        help="Repeatable objective descriptor filter (matches any requested objective descriptor).",
    )
    parser.add_argument(
        "--terrain-descriptor-id",
        action="append",
        default=[],
        help="Repeatable terrain descriptor filter (matches any requested terrain descriptor).",
    )
    parser.add_argument(
        "--deployment-descriptor-id",
        action="append",
        default=[],
        help="Repeatable deployment descriptor filter.",
    )
    parser.add_argument(
        "--army-build-descriptor-id",
        action="append",
        default=[],
        help="Repeatable army-build descriptor filter.",
    )
    parser.add_argument(
        "--tool-descriptor-id",
        action="append",
        default=[],
        help="Repeatable tool descriptor filter (matches any requested tool descriptor).",
    )
    parser.add_argument(
        "--enforce-gate-profile",
        action="store_true",
        help=(
            "Fail with non-zero exit when the canonical training-data gate profile "
            f"({PRE_ML_BASELINE_GATE_PROFILE_ID}) is not met."
        ),
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    records = load_training_records(input_path)
    manifest = build_training_manifest(
        records,
        source_tag=str(args.source_tag),
        min_tier3_records=int(args.min_tier3_records),
        rules_bundle_ids=list(args.rules_bundle_id or []),
        descriptor_bundle_ids=list(args.descriptor_bundle_id or []),
        mission_descriptor_ids=list(args.mission_descriptor_id or []),
        objective_descriptor_ids=list(args.objective_descriptor_id or []),
        terrain_descriptor_ids=list(args.terrain_descriptor_id or []),
        deployment_descriptor_ids=list(args.deployment_descriptor_id or []),
        army_build_descriptor_ids=list(args.army_build_descriptor_id or []),
        tool_descriptor_ids=list(args.tool_descriptor_id or []),
    ).to_dict()
    errors = validate_training_manifest(manifest)
    if errors:
        raise ValueError(f"Manifest validation failed: {'; '.join(errors)}")
    gate_failures = validate_gate_profile_compliance(manifest)
    if args.enforce_gate_profile and gate_failures:
        raise ValueError(f"Gate profile enforcement failed: {'; '.join(gate_failures)}")

    save_training_manifest(manifest, output_path)
    print(f"Manifest written: {output_path}")
    print(f"Total records: {manifest['total_records']}")
    print(json.dumps(manifest["gate_requirements"], sort_keys=True))


if __name__ == "__main__":
    main()
