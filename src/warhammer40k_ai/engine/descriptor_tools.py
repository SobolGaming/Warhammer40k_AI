from __future__ import annotations

from ..rules.enhancement_descriptors import (
    EnhancementToolDescriptor,
    get_enhancement_tool_descriptor,
)
from ..rules.stratagem_descriptors import (
    StratagemToolDescriptor,
    get_stratagem_tool_descriptor,
)
from .descriptor_bundle import CompiledDescriptor, descriptor_id, iter_players, iter_units, json_safe, safe_float, safe_int


def enhancement_tool_payload(descriptor: EnhancementToolDescriptor) -> dict[str, object]:
    return json_safe(
        {
            "tool_type": "ENHANCEMENT",
            "tool_id": str(descriptor.enhancement_id or ""),
            "name": str(descriptor.name or ""),
            "timing": str(descriptor.timing or ""),
            "target": str(descriptor.target or ""),
            "duration": str(descriptor.duration or ""),
            "effect": str(descriptor.effect or ""),
            "range_in": safe_float(descriptor.range_in, 0.0) if descriptor.range_in is not None else None,
            "once_per_battle": bool(descriptor.once_per_battle),
            "effect_params": json_safe(dict(descriptor.effect_params or {})),
        }
    )


def stratagem_tool_payload(descriptor: StratagemToolDescriptor) -> dict[str, object]:
    return json_safe(
        {
            "tool_type": "STRATAGEM",
            "tool_id": str(descriptor.stratagem_id or ""),
            "name": str(descriptor.name or ""),
            "timing": str(descriptor.timing or ""),
            "target": str(descriptor.target or ""),
            "duration": str(descriptor.duration or ""),
            "effect": str(descriptor.effect or ""),
            "cp_cost": safe_int(descriptor.cp_cost, 0),
            "range_in": safe_float(descriptor.range_in, 0.0) if descriptor.range_in is not None else None,
            "once_per_battle_round": bool(descriptor.once_per_battle_round),
            "effect_params": json_safe(dict(descriptor.effect_params or {})),
        }
    )


def compile_tool_descriptors(game: object) -> tuple[CompiledDescriptor, ...]:
    tool_descriptors: dict[str, CompiledDescriptor] = {}
    for unit in iter_units(game):
        enhancement = getattr(unit, "enhancement", None)
        if enhancement is None:
            continue
        enhancement_id = str(getattr(enhancement, "id", "") or "")
        enhancement_name = str(getattr(enhancement, "name", "") or "")
        descriptor = get_enhancement_tool_descriptor(
            enhancement_id=enhancement_id,
            name=enhancement_name,
        )
        if descriptor is None:
            continue
        payload = enhancement_tool_payload(descriptor)
        payload_tool_id = str(payload.get("tool_id", "") or "")
        compiled_id = (
            f"tool_descriptor:enhancement:{payload_tool_id}"
            if payload_tool_id
            else descriptor_id("tool_descriptor", payload)
        )
        tool_descriptors[compiled_id] = CompiledDescriptor(
            family="ToolDescriptor",
            descriptor_id=compiled_id,
            payload=payload,
        )

    for player in iter_players(game):
        stratagem_manager = getattr(player, "stratagems", None)
        available = list(getattr(stratagem_manager, "available", []) or [])
        for stratagem in available:
            descriptor = getattr(stratagem, "tool_descriptor", None)
            if descriptor is None:
                descriptor = get_stratagem_tool_descriptor(
                    stratagem_id=str(getattr(stratagem, "id", "") or ""),
                    name=str(getattr(stratagem, "name", "") or ""),
                )
            if descriptor is None:
                continue
            payload = stratagem_tool_payload(descriptor)
            payload_tool_id = str(payload.get("tool_id", "") or "")
            compiled_id = (
                f"tool_descriptor:stratagem:{payload_tool_id}"
                if payload_tool_id
                else descriptor_id("tool_descriptor", payload)
            )
            tool_descriptors[compiled_id] = CompiledDescriptor(
                family="ToolDescriptor",
                descriptor_id=compiled_id,
                payload=payload,
            )

    return tuple(tool_descriptors[key] for key in sorted(tool_descriptors.keys()))


__all__ = ["compile_tool_descriptors", "enhancement_tool_payload", "stratagem_tool_payload"]
