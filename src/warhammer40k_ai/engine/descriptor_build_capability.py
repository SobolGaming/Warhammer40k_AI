from __future__ import annotations

from ..roster.build_capability import compile_build_capability_profile
from ..roster.build_capability_schema import (
    BuildCapabilityExtensionGroup,
    BuildCapabilitySchema,
    DEFAULT_BUILD_CAPABILITY_SCHEMA,
)
from ..waha_helper import WahaHelper
from .descriptor_army_build import army_blueprint_for_army
from .descriptor_bundle import CompiledDescriptor, descriptor_id


def compile_build_capability_descriptor_for_army(
    army: object,
    *,
    rules_bundle_id: object,
    schema: BuildCapabilitySchema = DEFAULT_BUILD_CAPABILITY_SCHEMA,
    extension_groups: tuple[BuildCapabilityExtensionGroup | str, ...]
    | list[BuildCapabilityExtensionGroup | str]
    | None = None,
    waha_helper: WahaHelper | None = None,
) -> CompiledDescriptor | None:
    blueprint = army_blueprint_for_army(army)
    if blueprint is None:
        return None
    profile = compile_build_capability_profile(
        blueprint,
        rules_bundle_id=rules_bundle_id,
        schema=schema,
        extension_groups=extension_groups,
        waha_helper=waha_helper,
    )
    payload = profile.to_dict()
    return CompiledDescriptor(
        family="BuildCapabilityDescriptor",
        descriptor_id=descriptor_id("build_capability_descriptor", payload),
        payload=payload,
    )


__all__ = ["compile_build_capability_descriptor_for_army"]
