#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.roster.muster_manifest import (
    build_mustering_manifest,
    load_muster_records,
    save_mustering_manifest,
    validate_mustering_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a mustering corpus manifest from MusterRecord JSON artifacts."
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="Input MusterRecord JSON path. Repeat to merge multiple files.",
    )
    parser.add_argument("--output", required=True, help="Output mustering manifest JSON path.")
    parser.add_argument("--corpus-id", required=True, help="Stable corpus id for the manifest.")
    parser.add_argument("--source-tag", required=True, help="Data source tag for this manifest.")
    parser.add_argument("--rules-bundle-id", action="append", default=[], help="Repeatable rules bundle filter.")
    parser.add_argument(
        "--capability-schema-id",
        action="append",
        default=[],
        help="Repeatable capability schema filter.",
    )
    parser.add_argument(
        "--field-distribution-id",
        action="append",
        default=[],
        help="Repeatable tournament field distribution filter.",
    )
    parser.add_argument(
        "--event-policy-id",
        action="append",
        default=[],
        help="Repeatable event policy filter.",
    )
    parser.add_argument(
        "--policy-bundle-id",
        action="append",
        default=[],
        help="Repeatable policy bundle filter.",
    )
    parser.add_argument(
        "--controller-bundle-id",
        action="append",
        default=[],
        help="Repeatable controller bundle filter.",
    )
    parser.add_argument("--faction", action="append", default=[], help="Repeatable primary faction filter.")
    parser.add_argument(
        "--detachment-type",
        action="append",
        default=[],
        help="Repeatable primary detachment type filter.",
    )
    parser.add_argument(
        "--faction-tag",
        action="append",
        default=[],
        help="Repeatable faction tag filter.",
    )
    parser.add_argument(
        "--detachment-tag",
        action="append",
        default=[],
        help="Repeatable detachment tag filter.",
    )
    parser.add_argument(
        "--record-kind",
        action="append",
        default=[],
        help="Repeatable record kind filter.",
    )
    parser.add_argument(
        "--army-blueprint-hash",
        action="append",
        default=[],
        help="Repeatable army blueprint hash filter.",
    )
    parser.add_argument(
        "--build-capability-profile-id",
        action="append",
        default=[],
        help="Repeatable build capability profile filter.",
    )
    args = parser.parse_args()

    records = []
    for input_path in list(args.input or []):
        records.extend(load_muster_records(Path(input_path).expanduser().resolve()))

    manifest = build_mustering_manifest(
        records,
        corpus_id=str(args.corpus_id),
        source_tag=str(args.source_tag),
        rules_bundle_ids=list(args.rules_bundle_id or []),
        capability_schema_ids=list(args.capability_schema_id or []),
        field_distribution_ids=list(args.field_distribution_id or []),
        event_policy_ids=list(args.event_policy_id or []),
        policy_bundle_ids=list(args.policy_bundle_id or []),
        controller_bundle_ids=list(args.controller_bundle_id or []),
        factions=list(args.faction or []),
        detachment_types=list(args.detachment_type or []),
        faction_tags=list(args.faction_tag or []),
        detachment_tags=list(args.detachment_tag or []),
        record_kinds=list(args.record_kind or []),
        army_blueprint_hashes=list(args.army_blueprint_hash or []),
        build_capability_profile_ids=list(args.build_capability_profile_id or []),
    ).to_dict()
    errors = validate_mustering_manifest(manifest)
    if errors:
        raise ValueError(f"Mustering manifest validation failed: {'; '.join(errors)}")

    output_path = Path(args.output).expanduser().resolve()
    save_mustering_manifest(manifest, output_path)
    print(f"Mustering manifest written: {output_path}")
    print(f"Total records: {manifest['total_records']}")
    print(
        json.dumps(
            {
                "record_kind_counts": manifest["record_kind_counts"],
                "rules_bundle_ids": manifest["rules_bundle_ids"],
                "field_distribution_ids": manifest["field_distribution_ids"],
                "event_policy_ids": manifest["event_policy_ids"],
                "policy_bundle_ids": manifest["policy_bundle_ids"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
