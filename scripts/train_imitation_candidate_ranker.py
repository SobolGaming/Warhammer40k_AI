#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.ml.imitation_training import (
    DEFAULT_DESCRIPTOR_BUNDLE_ID,
    DEFAULT_EVENT_POLICY_ID,
    DEFAULT_VERSION_ADAPTER_BOUNDARY_ID,
    LinearImitationTrainingConfig,
    train_linear_imitation_candidate_rankers,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train framework-free linear candidate rankers from relabeled DecisionRecords."
    )
    parser.add_argument("--records", required=True, help="Relabeled DecisionRecords JSON array.")
    parser.add_argument("--training-manifest", required=True, help="Training manifest JSON for the records corpus.")
    parser.add_argument("--models-root", default="models", help="Output models root.")
    parser.add_argument("--run-id", required=True, help="Stable lower-case run id used in artifact ids.")
    parser.add_argument(
        "--policy-bundle-id",
        default="",
        help="Output policy bundle id. Defaults to policy_bundle:<run-id>.",
    )
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1.0)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--split-salt", default="linear_imitation_split_v1")
    parser.add_argument("--hash-bucket-count", type=int, default=512)
    parser.add_argument("--event-policy-id", default=DEFAULT_EVENT_POLICY_ID)
    parser.add_argument("--descriptor-bundle-id", default=DEFAULT_DESCRIPTOR_BUNDLE_ID)
    parser.add_argument("--version-adapter-boundary-id", default=DEFAULT_VERSION_ADAPTER_BOUNDARY_ID)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_id = str(args.run_id or "").strip()
    policy_bundle_id = str(args.policy_bundle_id or "").strip() or f"policy_bundle:{run_id}"
    result = train_linear_imitation_candidate_rankers(
        LinearImitationTrainingConfig(
            records_path=Path(str(args.records)).expanduser().resolve(),
            training_manifest_path=Path(str(args.training_manifest)).expanduser().resolve(),
            models_root=Path(str(args.models_root)).expanduser().resolve(),
            run_id=run_id,
            policy_bundle_id=policy_bundle_id,
            epochs=max(1, int(args.epochs)),
            learning_rate=float(args.learning_rate),
            validation_ratio=float(args.validation_ratio),
            split_salt=str(args.split_salt),
            hash_bucket_count=max(8, int(args.hash_bucket_count)),
            event_policy_id=str(args.event_policy_id),
            descriptor_bundle_id=str(args.descriptor_bundle_id),
            version_adapter_boundary_id=str(args.version_adapter_boundary_id),
        )
    )
    print(json.dumps({
        "training_report_path": result["training_report_path"],
        "policy_bundle_id": result["policy_bundle_id"],
        "policy_bundle_path": result["policy_bundle_path"],
        "validation": result["validation"]["overall"],
        "trained_decision_type_count": result["trained_decision_type_count"],
        "total_weight_count": result["total_weight_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
