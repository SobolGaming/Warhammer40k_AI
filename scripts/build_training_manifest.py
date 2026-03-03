#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from warhammer40k_ai.engine.training_manifest import (
    PRE_ML_BASELINE_GATE_PROFILE_ID,
    build_training_manifest,
    validate_gate_profile_compliance,
    validate_training_manifest,
)


def _load_document(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_records(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(item or {}) for item in document]
    if isinstance(document, dict):
        if isinstance(document.get("records"), list):
            return [dict(item or {}) for item in list(document.get("records", []) or [])]
        return [dict(document)]
    raise ValueError("Input must be a decision record object, list, or object with a records list.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a training data manifest from DecisionRecords.")
    parser.add_argument("--input", required=True, help="Input decision records JSON path.")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    parser.add_argument("--source-tag", required=True, help="Data source tag (human, heuristic, self_play, mixed).")
    parser.add_argument("--min-tier3-records", type=int, default=10000, help="Minimum Tier3 pretraining gate.")
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

    records = _extract_records(_load_document(input_path))
    manifest = build_training_manifest(
        records,
        source_tag=str(args.source_tag),
        min_tier3_records=int(args.min_tier3_records),
    ).to_dict()
    errors = validate_training_manifest(manifest)
    if errors:
        raise ValueError(f"Manifest validation failed: {'; '.join(errors)}")
    gate_failures = validate_gate_profile_compliance(manifest)
    if args.enforce_gate_profile and gate_failures:
        raise ValueError(f"Gate profile enforcement failed: {'; '.join(gate_failures)}")

    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"Manifest written: {output_path}")
    print(f"Total records: {manifest['total_records']}")
    print(json.dumps(manifest["gate_requirements"], sort_keys=True))


if __name__ == "__main__":
    main()
