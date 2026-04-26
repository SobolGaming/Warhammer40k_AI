#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from warhammer40k_ai.ml.llm_agents import llm_training_examples_from_records


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        records = payload.get("records", [])
    else:
        records = payload
    if not isinstance(records, list):
        raise ValueError("Input must be a DecisionRecord list or an object with a records list.")
    return [dict(record or {}) for record in records if isinstance(record, dict)]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build JSONL supervised examples for LLM domain agents from DecisionRecords."
    )
    parser.add_argument("--input", required=True, help="DecisionRecord JSON list or report containing records.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    input_path = Path(str(args.input)).expanduser()
    output_path = Path(str(args.output)).expanduser()
    examples = llm_training_examples_from_records(_load_records(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
    print(f"Wrote {len(examples)} LLM training examples to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

