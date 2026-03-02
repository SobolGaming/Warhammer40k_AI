#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from warhammer40k_ai.engine.relabel import relabel_decision_records
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine.semantic_diff import classify_semantic_diff


def _load_document(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_records(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(item or {}) for item in document]
    if isinstance(document, dict):
        if isinstance(document.get("records"), list):
            return [dict(item or {}) for item in list(document.get("records", []) or [])]
        return [dict(document)]
    raise ValueError("Input JSON must be a record object, a list of records, or an object with a 'records' list.")


def _replace_records(document: Any, relabeled_records: list[dict[str, Any]]) -> Any:
    if isinstance(document, list):
        return relabeled_records
    if isinstance(document, dict):
        if isinstance(document.get("records"), list):
            output = dict(document)
            output["records"] = relabeled_records
            return output
        if len(relabeled_records) != 1:
            raise ValueError("Single-record object input produced multiple relabeled records.")
        return relabeled_records[0]
    raise ValueError("Unsupported JSON document shape for output.")


def _build_target_bundle(args: argparse.Namespace) -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id=args.core_rules_id,
        rules_commentary_id=args.rules_commentary_id,
        mission_pack_id=args.mission_pack_id,
        terrain_pack_id=args.terrain_pack_id,
        dataslate_id=args.dataslate_id,
        points_id=args.points_id,
        faction_pack_id=args.faction_pack_id,
        detachment_pack_id=args.detachment_pack_id,
    )


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in list(records or []):
        status = str(record.get("relabel_status", "") or "UNKNOWN")
        counts[status] = int(counts.get(status, 0) or 0) + 1
    return {key: counts[key] for key in sorted(counts.keys())}


def main() -> None:
    parser = argparse.ArgumentParser(description="Relabel DecisionRecords for a target rules bundle.")
    parser.add_argument("--input", required=True, help="Input JSON file (record, list, or {records:[...]}).")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--core-rules-id", default="unknown_core_rules")
    parser.add_argument("--rules-commentary-id", default="unknown_rules_commentary")
    parser.add_argument("--mission-pack-id", default="unknown_mission_pack")
    parser.add_argument("--terrain-pack-id", default="unknown_terrain_pack")
    parser.add_argument("--dataslate-id", default="unknown_dataslate")
    parser.add_argument("--points-id", default="unknown_points")
    parser.add_argument("--faction-pack-id", default="unknown_faction_pack")
    parser.add_argument("--detachment-pack-id", default="unknown_detachment_pack")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    document = _load_document(input_path)
    records = _extract_records(document)
    target_bundle = _build_target_bundle(args)
    relabeled_records = relabel_decision_records(
        records,
        target_rules_bundle=target_bundle,
    )
    output_document = _replace_records(document, relabeled_records)
    output_path.write_text(
        json.dumps(output_document, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )

    counts = _status_counts(relabeled_records)
    print(f"Relabeled records: {len(relabeled_records)}")
    print(f"Target rules bundle id: {target_bundle.rules_bundle_id}")
    print(json.dumps(counts, sort_keys=True))
    if records:
        source_bundle = RulesetBundle.from_dict(dict(records[0].get("rules_bundle", {}) or {}))
        diff = classify_semantic_diff(source_bundle, target_bundle)
        print(json.dumps(diff.training_scope.to_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
