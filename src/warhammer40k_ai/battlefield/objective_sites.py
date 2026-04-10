from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from shapely.geometry import Polygon

from .control_queries import (
    compute_player_objective_control,
    control_region_centroid,
    control_region_shape,
    max_radius_for_polygon,
    serialize_polygon_geometry,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..engine.game import Game


@dataclass
class ScoreSource:
    score_source_id: str
    kind: str = "OBJECTIVE_CONTROL"
    label: str = ""
    objective_id: str = ""
    points_value: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self, controller_player: object | None) -> bool:
        return controller_player is not None

    def score_value(self, controller_player: object | None) -> int:
        if not self.is_active(controller_player):
            return 0
        return int(self.points_value or 0)

    def to_state_entry(
        self,
        *,
        objective_id: str,
        objective_site_id: str,
        controller_player_id: str,
    ) -> dict[str, Any]:
        return {
            "score_source_id": str(self.score_source_id or ""),
            "kind": str(self.kind or "OBJECTIVE_CONTROL"),
            "objective_id": str(objective_id or self.objective_id or ""),
            "objective_site_id": str(objective_site_id or ""),
            "label": str(self.label or ""),
            "controller_player_id": str(controller_player_id or ""),
            "points_value": int(self.points_value or 0),
            "metadata": dict(self.metadata or {}),
        }


@dataclass
class ControlRegion:
    region_id: str
    kind: str
    center_x: float
    center_y: float
    center_z: float = 0.0
    radius: float = 0.0
    footprint: Polygon | None = None
    feature_key: str = ""
    feature_label: str = ""
    terrain_area_id: str = ""
    layout_slot_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def centroid(self, *, game_state: object | None = None) -> tuple[float, float, float]:
        return control_region_centroid(self, game_state=game_state)

    def shape(self, *, game_state: object | None = None):
        return control_region_shape(self, game_state=game_state)

    def to_state_entry(self, *, objective_id: str, objective_site_id: str) -> dict[str, Any]:
        center = self.centroid()
        entry = {
            "region_id": str(self.region_id or ""),
            "kind": str(self.kind or ""),
            "objective_id": str(objective_id or ""),
            "objective_site_id": str(objective_site_id or ""),
            "center": [float(center[0]), float(center[1]), float(center[2])],
            "radius": float(self.radius or 0.0),
            "metadata": dict(self.metadata or {}),
        }
        footprint = serialize_polygon_geometry(self.footprint)
        if footprint is not None:
            entry["footprint"] = footprint
        if self.feature_key:
            entry["feature_key"] = str(self.feature_key)
        if self.feature_label:
            entry["feature_label"] = str(self.feature_label)
        if self.terrain_area_id:
            entry["terrain_area_id"] = str(self.terrain_area_id)
        if self.layout_slot_id:
            entry["layout_slot_id"] = str(self.layout_slot_id)
        return entry


class ObjectiveSite:
    """Runtime objective site that separates geometry, control, and scoring."""

    def __init__(self, x: float, y: float, z: float = 0.0, control_radius: float = 3.0) -> None:
        self._id = str(uuid.uuid4())
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.control_radius = float(control_radius)
        self.site_kind = "MARKER"
        self.geometry_kind = "MARKER"
        self.footprint: Polygon | None = None
        self.feature_key = ""
        self.feature_label = ""
        self.terrain_area_id = ""
        self.layout_slot_id = ""
        self.metadata: dict[str, Any] = {}
        self.controlling_player = None
        self.terraformed_by = None
        self.cleansed_by = None
        self.is_hazard: bool = False
        self.removed = False
        self.sticky_controller = None
        self.sticky_source = None
        self.sticky_minimum_control: int = 0
        self.space_marines_vanguard_deadly_prize_sources: dict[str, str] = {}
        self.worldblight_controller = None
        self.worldblight_source = None
        self.control_region = ControlRegion(
            region_id=f"region:site:{self._id}",
            kind="OBJECTIVE_CONTROL_RADIUS",
            center_x=self.x,
            center_y=self.y,
            center_z=self.z,
            radius=self.control_radius,
        )
        self.score_sources: list[ScoreSource] = [
            ScoreSource(
                score_source_id=f"score_source:site:{self._id}",
                kind="OBJECTIVE_CONTROL",
                label="Objective Control",
                points_value=0,
            )
        ]

    @property
    def id(self) -> str:
        return self._id

    @classmethod
    def marker(
        cls,
        *,
        x: float,
        y: float,
        z: float = 0.0,
        control_radius: float = 3.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ObjectiveSite":
        site = cls(x=x, y=y, z=z, control_radius=control_radius)
        site.metadata = dict(metadata or {})
        return site

    @classmethod
    def terrain_footprint(
        cls,
        *,
        footprint: Polygon,
        z: float = 0.0,
        feature_key: str | None = None,
        feature_label: str | None = None,
        terrain_area_id: str | None = None,
        layout_slot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ObjectiveSite":
        centroid = footprint.centroid
        query_radius = max_radius_for_polygon(footprint)
        site = cls(x=float(centroid.x), y=float(centroid.y), z=z, control_radius=query_radius)
        site.site_kind = "TERRAIN_FOOTPRINT"
        site.geometry_kind = "POLYGON_FOOTPRINT"
        site.footprint = footprint
        site.feature_key = str(feature_key or "")
        site.feature_label = str(feature_label or "")
        site.terrain_area_id = str(terrain_area_id or "")
        site.layout_slot_id = str(layout_slot_id or "")
        site.metadata = dict(metadata or {})
        site.control_region = ControlRegion(
            region_id=f"region:site:{site.id}",
            kind="OBJECTIVE_CONTROL_FOOTPRINT",
            center_x=site.x,
            center_y=site.y,
            center_z=site.z,
            radius=query_radius,
            footprint=footprint,
            feature_key=site.feature_key,
            feature_label=site.feature_label,
            terrain_area_id=site.terrain_area_id,
            layout_slot_id=site.layout_slot_id,
        )
        site.score_sources = [
            ScoreSource(
                score_source_id=f"score_source:site:{site.id}",
                kind="OBJECTIVE_CONTROL",
                label="Objective Footprint Control",
                points_value=0,
            )
        ]
        return site

    @classmethod
    def keyed_feature(
        cls,
        *,
        feature_key: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        control_radius: float = 0.0,
        fallback_footprint: Polygon | None = None,
        feature_label: str | None = None,
        terrain_area_id: str | None = None,
        layout_slot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ObjectiveSite":
        if fallback_footprint is not None:
            centroid = fallback_footprint.centroid
            x = float(centroid.x)
            y = float(centroid.y)
            control_radius = max_radius_for_polygon(fallback_footprint)
        site = cls(x=x, y=y, z=z, control_radius=control_radius)
        site.site_kind = "KEYED_FEATURE"
        site.geometry_kind = "KEYED_FEATURE"
        site.footprint = fallback_footprint
        site.feature_key = str(feature_key or "")
        site.feature_label = str(feature_label or "")
        site.terrain_area_id = str(terrain_area_id or "")
        site.layout_slot_id = str(layout_slot_id or "")
        site.metadata = dict(metadata or {})
        site.control_region = ControlRegion(
            region_id=f"region:site:{site.id}",
            kind="OBJECTIVE_CONTROL_KEYED_FEATURE",
            center_x=site.x,
            center_y=site.y,
            center_z=site.z,
            radius=site.control_radius,
            footprint=fallback_footprint,
            feature_key=site.feature_key,
            feature_label=site.feature_label,
            terrain_area_id=site.terrain_area_id,
            layout_slot_id=site.layout_slot_id,
        )
        site.score_sources = [
            ScoreSource(
                score_source_id=f"score_source:site:{site.id}",
                kind="OBJECTIVE_CONTROL",
                label="Objective Feature Control",
                points_value=0,
            )
        ]
        return site

    def bind_objective(self, objective_id: str, objective_name: str | None = None, *, points_value: int = 0) -> None:
        objective_key = str(objective_id or "").strip()
        if not objective_key:
            return
        if self.control_region.region_id.startswith("region:site:"):
            self.control_region.region_id = f"region:objective:{objective_key}"
        for source in list(self.score_sources or []):
            if str(source.score_source_id or "").startswith("score_source:site:"):
                source.score_source_id = f"score_source:objective:{objective_key}"
            if not str(source.objective_id or "").strip():
                source.objective_id = objective_key
            if objective_name and not str(source.label or "").strip():
                source.label = str(objective_name)
            if int(source.points_value or 0) == 0 and int(points_value or 0) > 0:
                source.points_value = int(points_value)

    def centroid(self, *, game_state: object | None = None) -> tuple[float, float, float]:
        return self.control_region.centroid(game_state=game_state)

    def primary_score_source(self) -> ScoreSource:
        if not self.score_sources:
            self.score_sources = [
                ScoreSource(
                    score_source_id=f"score_source:site:{self.id}",
                    kind="OBJECTIVE_CONTROL",
                    label="Objective Control",
                )
            ]
        return self.score_sources[0]

    def set_sticky_control(
        self,
        player,
        source: str | None = None,
        *,
        minimum_control: int | None = None,
    ) -> None:
        self.sticky_controller = player
        self.sticky_source = source
        if minimum_control is None:
            self.sticky_minimum_control = 0
        else:
            self.sticky_minimum_control = max(0, int(minimum_control or 0))
        self.controlling_player = player

    def to_state_entry(self, *, objective_id: str) -> dict[str, Any]:
        center = self.centroid()
        geometry = {
            "kind": str(self.geometry_kind or ""),
            "position": [float(center[0]), float(center[1]), float(center[2])],
            "control_radius": float(self.control_radius or 0.0),
            "feature_key": str(self.feature_key or ""),
            "feature_label": str(self.feature_label or ""),
            "terrain_area_id": str(self.terrain_area_id or ""),
            "layout_slot_id": str(self.layout_slot_id or ""),
        }
        footprint = serialize_polygon_geometry(self.footprint)
        if footprint is not None:
            geometry["footprint"] = footprint
        controller_player_id = str(getattr(self.controlling_player, "id", "") or "")
        return {
            "objective_id": str(objective_id or ""),
            "objective_site_id": str(self.id or ""),
            "site_kind": str(self.site_kind or ""),
            "position": [float(center[0]), float(center[1]), float(center[2])],
            "control_radius": float(self.control_radius or 0.0),
            "controller_player_id": controller_player_id,
            "sticky_controller_player_id": str(getattr(self.sticky_controller, "id", "") or ""),
            "sticky_minimum_control": int(self.sticky_minimum_control or 0),
            "removed": bool(self.removed),
            "geometry": geometry,
            "control_region": self.control_region.to_state_entry(
                objective_id=str(objective_id or ""),
                objective_site_id=str(self.id or ""),
            ),
            "score_sources": [
                source.to_state_entry(
                    objective_id=str(objective_id or ""),
                    objective_site_id=str(self.id or ""),
                    controller_player_id=controller_player_id,
                )
                for source in list(self.score_sources or [])
            ],
        }

    def update_control(self, game_state: "Game") -> None:
        prev_controller = self.controlling_player
        prev_sticky = self.sticky_controller
        prev_worldblight = self.worldblight_controller
        prev_worldblight_source = self.worldblight_source
        prev_removed = bool(self.removed)

        if bool(self.removed):
            self.controlling_player = None
            self.sticky_controller = None
            self.sticky_source = None
            self.sticky_minimum_control = 0
            self.space_marines_vanguard_deadly_prize_sources = {}
            self.worldblight_controller = None
            self.worldblight_source = None
            return

        player_oc = compute_player_objective_control(game_state, self.control_region)

        if any(int(oc or 0) > 0 for oc in player_oc.values()):
            max_oc = max(int(oc or 0) for oc in player_oc.values())
            max_players = [player for player, oc in player_oc.items() if int(oc or 0) == max_oc]
            self.controlling_player = max_players[0] if len(max_players) == 1 else None
        else:
            self.controlling_player = None

        sticky_owner = self.sticky_controller
        if sticky_owner is not None and sticky_owner in player_oc:
            sticky_oc = max(
                int(player_oc.get(sticky_owner, 0) or 0),
                int(self.sticky_minimum_control or 0),
            )
            opponent_max = 0
            for player, oc in player_oc.items():
                if player is sticky_owner:
                    continue
                opponent_max = max(opponent_max, int(oc or 0))
            allow_break = True
            if self.sticky_source in {"corrupt_realspace", "space_marines_vanguard_deadly_prize", "vigilance_eternal"}:
                allow_break = bool(getattr(game_state, "_corrupt_realspace_check", False))
            if opponent_max > sticky_oc and allow_break:
                self.sticky_controller = None
                self.sticky_source = None
                self.sticky_minimum_control = 0
            else:
                self.controlling_player = sticky_owner

        if self.worldblight_controller is not None and self.controlling_player is not self.worldblight_controller:
            self.worldblight_controller = None
            self.worldblight_source = None

        if (
            prev_controller is not self.controlling_player
            or prev_sticky is not self.sticky_controller
            or prev_worldblight is not self.worldblight_controller
            or prev_worldblight_source != self.worldblight_source
            or prev_removed != bool(self.removed)
        ):
            event_system = getattr(game_state, "event_system", None)
            if event_system is not None and hasattr(event_system, "publish"):
                event_system.publish(
                    "objective_control_changed",
                    objective=self,
                    previous_controller=prev_controller,
                    controller=self.controlling_player,
                    sticky_controller=self.sticky_controller,
                    worldblight_controller=self.worldblight_controller,
                    worldblight_source=self.worldblight_source,
                    removed=bool(self.removed),
                )

        oc_summary = {getattr(player, "name", str(player)): oc for player, oc in player_oc.items() if int(oc or 0) > 0}
        if oc_summary:
            logger.info(
                "ObjectiveSite (%0.1f, %0.1f) OC values: %s -> controlled by %s",
                self.x,
                self.y,
                oc_summary,
                getattr(self.controlling_player, "name", "None") if self.controlling_player else "None",
            )
        else:
            owner = getattr(self.controlling_player, "name", "None") if self.controlling_player else "None"
            logger.info("ObjectiveSite (%0.1f, %0.1f) controlled by %s (no models in range)", self.x, self.y, owner)


ObjectivePoint = ObjectiveSite


class ObjectiveCategory(Enum):
    PRIMARY = auto()
    SECONDARY = auto()
    SECRET = auto()


class Objective:
    def __init__(
        self,
        name: str,
        category: ObjectiveCategory,
        points: int,
        description: str,
        conditions: callable,
        location: object | None = None,
    ) -> None:
        self._id = str(uuid.uuid4())
        self.name = name
        self.category = category
        self.points = points
        self.description = description
        self.conditions = conditions
        self.location = location
        self.completed = False
        if isinstance(self.location, ObjectiveSite):
            self.location.bind_objective(self._id, self.name, points_value=int(self.points or 0))

    @property
    def id(self) -> str:
        return self._id

    def check_completion(self, game_state: "Game") -> bool:
        self.completed = bool(self.conditions(game_state))
        return self.completed

    def __repr__(self):
        status = "Completed" if self.completed else "Incomplete"
        return f"{self.name} ({self.category.name}): {status} - {self.points} points"


def resolve_objective_site(objective: object) -> object | None:
    if objective is None:
        return None
    if isinstance(objective, ObjectiveSite):
        return objective
    location = getattr(objective, "location", None)
    if location is not None:
        return location
    return objective


def resolve_objective_id(objective: object) -> str:
    site = resolve_objective_site(objective)
    objective_id = str(getattr(objective, "id", "") or "").strip()
    if objective_id:
        return objective_id
    return str(getattr(site, "id", "") or "")


__all__ = [
    "ControlRegion",
    "Objective",
    "ObjectiveCategory",
    "ObjectivePoint",
    "ObjectiveSite",
    "ScoreSource",
    "resolve_objective_id",
    "resolve_objective_site",
]
