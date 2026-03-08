#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.engine.deployment_ranker_training import (
    DEFAULT_DEPLOYMENT_RANKING_DECISION_TYPES,
    build_deployment_ranking_dataset,
    extract_records_from_document,
)


def _parse_csv_arg(value: str) -> list[str]:
    values: list[str] = []
    for raw in str(value or "").split(","):
        token = str(raw or "").strip()
        if not token:
            continue
        values.append(token)
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deployment imitation/ranking dataset from DecisionRecords.",
    )
    parser.add_argument("--input", required=True, help="Input DecisionRecords JSON path.")
    parser.add_argument("--output", required=True, help="Output dataset JSON path.")
    parser.add_argument(
        "--decision-types",
        default=",".join(DEFAULT_DEPLOYMENT_RANKING_DECISION_TYPES),
        help="Comma-separated decision types to include.",
    )
    parser.add_argument(
        "--feature-keys",
        default="",
        help="Optional comma-separated numeric metadata keys. Defaults to canonical deployment ranking keys.",
    )
    parser.add_argument(
        "--minimum-legal-candidates",
        type=int,
        default=2,
        help="Skip decisions with fewer legal candidates than this threshold.",
    )
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Include records where valid=false. By default only valid records are used.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    records = extract_records_from_document(json.loads(input_path.read_text(encoding="utf-8")))
    dataset = build_deployment_ranking_dataset(
        records,
        decision_types=_parse_csv_arg(args.decision_types),
        feature_keys=_parse_csv_arg(args.feature_keys),
        require_valid=not bool(args.include_invalid),
        minimum_legal_candidates=max(2, int(args.minimum_legal_candidates)),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    print(f"Wrote deployment ranking dataset: {output_path}")
    print(f"Decisions: {int(dataset.get('total_rank_decisions', 0) or 0)}")
    print(f"Candidates: {int(dataset.get('total_candidate_rows', 0) or 0)}")


if __name__ == "__main__":
    main()
