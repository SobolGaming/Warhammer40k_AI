#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from warhammer40k_ai.rules import stratagem_descriptors as descriptor_module
from warhammer40k_ai.rules.stratagem_descriptors import StratagemToolDescriptor
from warhammer40k_ai.rules.stratagems import (
    GENERIC_TOOL_ACTION_EXCLUDED_STRATAGEM_NAMES,
    IMPLEMENTED_STRATAGEM_NAME_IDS,
    IMPLEMENTED_STRATAGEM_NAMES,
    REACTION_ONLY_STRATAGEM_NAMES,
)
from warhammer40k_ai.rules.tool_action_context import (
    GENERIC_DESCRIPTOR_BOUND_CONTEXT_KEYS,
    ToolActionProviderContract,
    bound_context_keys_required_for_tool_action,
    descriptor_requires_trigger_context,
)


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())


def _descriptor_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variable_name, value in vars(descriptor_module).items():
        if not variable_name.endswith("_STRATAGEM_DESCRIPTORS") or not isinstance(value, dict):
            continue
        for stratagem_id, descriptor in sorted(value.items(), key=lambda item: str(item[0])):
            if not isinstance(descriptor, StratagemToolDescriptor):
                continue
            rows.append(
                {
                    "descriptor_group": variable_name,
                    "stratagem_id": str(stratagem_id),
                    "descriptor": descriptor,
                }
            )
    rows.sort(
        key=lambda row: (
            str(row["descriptor_group"]),
            str(row["stratagem_id"]),
            str(getattr(row["descriptor"], "name", "")),
        )
    )
    return rows


def _implemented_descriptor(row: dict[str, Any]) -> bool:
    descriptor = row["descriptor"]
    name_u = str(getattr(descriptor, "name", "") or "").strip().upper()
    if name_u in IMPLEMENTED_STRATAGEM_NAMES:
        return True
    stratagem_id = str(row["stratagem_id"])
    for ids in IMPLEMENTED_STRATAGEM_NAME_IDS.values():
        if stratagem_id in set(ids):
            return True
    return False


def _descriptor_name_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        descriptor = row["descriptor"]
        name_u = str(getattr(descriptor, "name", "") or "").strip().upper()
        key = _normalize_name(name_u)
        if key:
            names[key] = name_u
    return names


def _context_provider_names(rows: list[dict[str, Any]]) -> set[str]:
    descriptor_names = _descriptor_name_map(rows)
    provider_names: set[str] = set()
    rules_dir = SRC_ROOT / "warhammer40k_ai" / "rules"
    for path in sorted(rules_dir.glob("stratagems*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise RuntimeError(f"Could not parse {path}") from exc
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            function_name = str(node.name)
            interesting = (
                function_name == "_phase_available_stratagem_context"
                or "tool_action_context" in function_name
                or ("tool_action" in function_name and ("build" in function_name or "can_use" in function_name))
            )
            if not interesting:
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Constant) or not isinstance(child.value, str):
                    continue
                name_u = descriptor_names.get(_normalize_name(child.value))
                if name_u:
                    provider_names.add(name_u)
    return provider_names


def _classify_row(row: dict[str, Any], provider_names: set[str]) -> dict[str, Any]:
    descriptor = row["descriptor"]
    stratagem = SimpleNamespace(name=descriptor.name, tool_descriptor=descriptor)
    contract = ToolActionProviderContract.inspect(stratagem, {})
    name_u = str(descriptor.name or "").strip().upper()
    trigger_bound = descriptor_requires_trigger_context(descriptor)
    bound_context_keys = bound_context_keys_required_for_tool_action(stratagem, {})
    provider_covered = name_u in provider_names
    generic_provider_covered = bool(bound_context_keys) and set(bound_context_keys).issubset(
        GENERIC_DESCRIPTOR_BOUND_CONTEXT_KEYS
    )
    explicitly_supported = name_u in GENERIC_TOOL_ACTION_EXCLUDED_STRATAGEM_NAMES or name_u in {
        "COMMAND RE-ROLL",
        "CORRUPT REALSPACE",
        "FIRE OVERWATCH",
        "NEW ORDERS",
    }

    if explicitly_supported:
        category = "explicit"
    elif trigger_bound:
        category = "trigger_window"
    elif bound_context_keys and provider_covered:
        category = "phase_context_provider"
    elif generic_provider_covered:
        category = "generic_phase_context_provider"
    elif bound_context_keys:
        category = "broad_phase_blocked_until_bound_context"
    else:
        category = "generic_broad_phase"

    return {
        "category": category,
        "descriptor_group": row["descriptor_group"],
        "stratagem_id": row["stratagem_id"],
        "name": descriptor.name,
        "implemented": _implemented_descriptor(row),
        "reaction_only_listed": name_u in REACTION_ONLY_STRATAGEM_NAMES,
        "trigger_bound": trigger_bound,
        "provider_covered": provider_covered,
        "generic_provider_covered": generic_provider_covered,
        "missing_context_keys": list(contract.missing_context_keys),
        "bound_context_keys": list(bound_context_keys),
        "timing": descriptor.timing,
        "target": descriptor.target,
        "effect": descriptor.effect,
    }


def build_audit(*, implemented_only: bool = True) -> dict[str, Any]:
    rows = _descriptor_rows()
    provider_names = _context_provider_names(rows)
    classified = [
        _classify_row(row, provider_names)
        for row in rows
        if not implemented_only or _implemented_descriptor(row)
    ]
    counts: dict[str, int] = {}
    for entry in classified:
        category = str(entry["category"])
        counts[category] = counts.get(category, 0) + 1
    unsafe = [
        entry
        for entry in classified
        if entry["category"] not in {
            "broad_phase_blocked_until_bound_context",
            "explicit",
            "generic_broad_phase",
            "generic_phase_context_provider",
            "phase_context_provider",
            "trigger_window",
        }
    ]
    return {
        "descriptor_count": len(classified),
        "context_provider_name_count": len(provider_names),
        "category_counts": dict(sorted(counts.items())),
        "unsafe_count": len(unsafe),
        "unsafe": unsafe,
        "entries": classified,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit descriptor-backed stratagem tool actions for broad headless context safety."
    )
    parser.add_argument(
        "--all-descriptors",
        action="store_true",
        help="Include descriptors whose stratagem names are not currently marked implemented.",
    )
    parser.add_argument("--json-output", type=Path, help="Write the full audit as JSON.")
    parser.add_argument(
        "--show-blocked",
        action="store_true",
        help="Print broad-phase descriptors blocked until a bound context provider exists.",
    )
    args = parser.parse_args(argv)

    audit = build_audit(implemented_only=not bool(args.all_descriptors))
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    print(f"descriptor_count={audit['descriptor_count']}")
    print(f"context_provider_name_count={audit['context_provider_name_count']}")
    print(f"unsafe_count={audit['unsafe_count']}")
    for category, count in audit["category_counts"].items():
        print(f"{category}={count}")

    if args.show_blocked:
        blocked = [
            entry
            for entry in audit["entries"]
            if entry["category"] == "broad_phase_blocked_until_bound_context"
        ]
        for entry in blocked:
            keys = ",".join(entry["bound_context_keys"])
            print(f"blocked\t{entry['name']}\t{entry['stratagem_id']}\t{keys}\t{entry['timing']}")

    return 1 if int(audit["unsafe_count"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
