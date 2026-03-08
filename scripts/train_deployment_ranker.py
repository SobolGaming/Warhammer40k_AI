#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from warhammer40k_ai.engine.deployment_ranker import DeploymentCandidateRanker
from warhammer40k_ai.engine.deployment_ranker_training import train_deployment_ranker_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a linear deployment candidate ranker from a deployment ranking dataset.",
    )
    parser.add_argument("--input", required=True, help="Input deployment ranking dataset JSON path.")
    parser.add_argument("--output", required=True, help="Output deployment ranker model JSON path.")
    parser.add_argument("--epochs", type=int, default=120, help="Gradient descent epochs.")
    parser.add_argument("--learning-rate", type=float, default=0.05, help="Gradient descent learning rate.")
    parser.add_argument("--l2-weight", type=float, default=1e-4, help="L2 regularization coefficient.")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic seed for weight initialization.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    dataset = json.loads(input_path.read_text(encoding="utf-8"))
    model = train_deployment_ranker_model(
        dict(dataset or {}),
        epochs=max(1, int(args.epochs)),
        learning_rate=float(args.learning_rate),
        l2_weight=max(0.0, float(args.l2_weight)),
        seed=int(args.seed),
    )
    ranker = DeploymentCandidateRanker(model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ranker.to_json_file(output_path)
    payload = model.to_dict()
    metrics = dict(payload.get("training_metrics", {}) or {})
    print(f"Wrote deployment ranker model: {output_path}")
    print(json.dumps(metrics, sort_keys=True))


if __name__ == "__main__":
    main()
