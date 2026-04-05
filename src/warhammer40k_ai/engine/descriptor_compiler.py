from __future__ import annotations

from .descriptor_army_build import compile_army_build_descriptor
from .descriptor_bundle import CompiledDescriptor, CompiledDescriptorBundle, descriptor_bundle_id
from .descriptor_deployment import compile_deployment_descriptor
from .descriptor_mission import compile_mission_descriptor
from .descriptor_objectives import compile_objective_descriptors
from .descriptor_terrain import compile_terrain_descriptors
from .descriptor_tools import compile_tool_descriptors


def compile_descriptor_bundle(game: object) -> CompiledDescriptorBundle:
    mission_descriptor = compile_mission_descriptor(game)
    objective_descriptors = compile_objective_descriptors(game)
    terrain_descriptors = compile_terrain_descriptors(game)
    deployment_descriptor = compile_deployment_descriptor(game)
    army_build_descriptor = compile_army_build_descriptor(game)
    tool_descriptors = compile_tool_descriptors(game)

    bundle_id = descriptor_bundle_id(
        mission_descriptor_id=mission_descriptor.descriptor_id,
        objective_descriptor_ids=[descriptor.descriptor_id for descriptor in objective_descriptors],
        terrain_descriptor_ids=[descriptor.descriptor_id for descriptor in terrain_descriptors],
        deployment_descriptor_id=deployment_descriptor.descriptor_id,
        army_build_descriptor_id=army_build_descriptor.descriptor_id,
        tool_descriptor_ids=[descriptor.descriptor_id for descriptor in tool_descriptors],
    )
    return CompiledDescriptorBundle(
        mission_descriptor=mission_descriptor,
        objective_descriptors=tuple(objective_descriptors),
        terrain_descriptors=tuple(terrain_descriptors),
        deployment_descriptor=deployment_descriptor,
        army_build_descriptor=army_build_descriptor,
        tool_descriptors=tuple(tool_descriptors),
        bundle_id=bundle_id,
    )


__all__ = [
    "CompiledDescriptor",
    "CompiledDescriptorBundle",
    "compile_descriptor_bundle",
]
