#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine.semantic_diff import classify_semantic_diff


def _bundle_from_namespace(prefix: str, args: argparse.Namespace) -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id=getattr(args, f"{prefix}_core_rules_id"),
        rules_commentary_id=getattr(args, f"{prefix}_rules_commentary_id"),
        mission_pack_id=getattr(args, f"{prefix}_mission_pack_id"),
        terrain_pack_id=getattr(args, f"{prefix}_terrain_pack_id"),
        dataslate_id=getattr(args, f"{prefix}_dataslate_id"),
        points_id=getattr(args, f"{prefix}_points_id"),
        faction_pack_id=getattr(args, f"{prefix}_faction_pack_id"),
        detachment_pack_id=getattr(args, f"{prefix}_detachment_pack_id"),
    )


def _add_bundle_args(parser: argparse.ArgumentParser, prefix: str, label: str) -> None:
    parser.add_argument(f"--{prefix}-core-rules-id", required=True, help=f"{label} core rules id")
    parser.add_argument(f"--{prefix}-rules-commentary-id", required=True, help=f"{label} rules commentary id")
    parser.add_argument(f"--{prefix}-mission-pack-id", required=True, help=f"{label} mission pack id")
    parser.add_argument(f"--{prefix}-terrain-pack-id", required=True, help=f"{label} terrain pack id")
    parser.add_argument(f"--{prefix}-dataslate-id", required=True, help=f"{label} dataslate id")
    parser.add_argument(f"--{prefix}-points-id", required=True, help=f"{label} points id")
    parser.add_argument(f"--{prefix}-faction-pack-id", required=True, help=f"{label} faction pack id")
    parser.add_argument(f"--{prefix}-detachment-pack-id", required=True, help=f"{label} detachment pack id")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify semantic diff between two rules bundles.")
    _add_bundle_args(parser, "source", "Source bundle")
    _add_bundle_args(parser, "target", "Target bundle")
    args = parser.parse_args()

    source_bundle = _bundle_from_namespace("source", args)
    target_bundle = _bundle_from_namespace("target", args)
    diff = classify_semantic_diff(source_bundle, target_bundle)
    print(json.dumps(diff.to_dict(), indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
