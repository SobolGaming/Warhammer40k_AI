from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.movement_distance import movement_distance_profile
from warhammer40k_ai.utility.movement_utils import compute_embark_candidates
from warhammer40k_ai.utility.unit_models import unit_group_models


class _Base:
    has_circular_base = True

    def __init__(self, x: float, y: float, *, radius: float = 0.5) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = 0.0
        self.facing = 0.0
        self.radius = [float(radius), float(radius)]

    def get_radius(self) -> float:
        return float(self.radius[0])


class _Model:
    def __init__(self, model_id: str, x: float, y: float) -> None:
        self.id = model_id
        self._id = model_id
        self.is_alive = True
        self.model_base = _Base(x, y)

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


class _Unit:
    def __init__(self, unit_id: str, model_ids: list[str], army: object) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.models = [_Model(model_id, float(index), 0.0) for index, model_id in enumerate(model_ids)]
        self.movement = 6.0
        self.round_state = SimpleNamespace(
            remained_stationary_this_round=False,
            reinforced_this_round=False,
            moved_this_round=True,
            advanced_this_round=False,
            fell_back_this_round=False,
            disembarked_this_round=False,
        )
        self._army = army

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def is_alive(self) -> bool:
        return True


def _attach_leader(bodyguard: _Unit, leader: _Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    bodyguard.get_attached_unit_members = lambda: [bodyguard, leader]  # type: ignore[method-assign]
    leader.get_attached_unit_root = lambda: bodyguard  # type: ignore[method-assign]


def test_unit_group_models_include_attached_members_when_pending_filtered() -> None:
    army = object()
    bodyguard = _Unit("unit:bodyguard", ["model:bodyguard"], army)
    leader = _Unit("unit:leader", ["model:leader"], army)
    pending = _Model("model:pending", 2.0, 0.0)
    pending._pending_placement = True
    leader.models.append(pending)
    _attach_leader(bodyguard, leader)

    assert [model.id for model in unit_group_models(bodyguard)] == [
        "model:bodyguard",
        "model:leader",
        "model:pending",
    ]
    assert [model.id for model in unit_group_models(bodyguard, include_pending=False)] == [
        "model:bodyguard",
        "model:leader",
    ]


def test_movement_distance_profile_accounts_for_attached_leader_models() -> None:
    army = object()
    bodyguard = _Unit("unit:bodyguard", ["model:bodyguard"], army)
    leader = _Unit("unit:leader", ["model:leader"], army)
    leader.models[0].model_base.x = 2.0
    _attach_leader(bodyguard, leader)

    def _effective_characteristic(model, characteristic: str, game_map=None):
        del game_map
        if characteristic == "movement" and model.id == "model:leader":
            return 8.0
        return 6.0

    bodyguard.get_effective_model_characteristic = _effective_characteristic  # type: ignore[attr-defined]

    profile = movement_distance_profile(
        bodyguard,
        [
            {"model_id": "model:bodyguard", "position": [3.0, 0.0, 0.0]},
            {"model_id": "model:leader", "position": [7.0, 0.0, 0.0]},
        ],
    )

    by_id = {entry.model_id: entry for entry in profile.entries}
    assert set(by_id) == {"model:bodyguard", "model:leader"}
    assert by_id["model:bodyguard"].distance == 3.0
    assert by_id["model:bodyguard"].normal_limit == 6.0
    assert by_id["model:leader"].distance == 5.0
    assert by_id["model:leader"].normal_limit == 8.0


def test_compute_embark_candidates_requires_every_attached_model_within_three() -> None:
    army = object()
    transport = _Unit("unit:transport", ["model:transport"], army)
    transport.is_transport = True
    transport.can_transport = lambda unit: unit is passenger  # type: ignore[attr-defined]
    passenger = _Unit("unit:passenger", ["model:passenger"], army)
    leader = _Unit("unit:leader", ["model:leader"], army)
    _attach_leader(passenger, leader)
    passenger.models[0].model_base.x = 2.0
    leader.models[0].model_base.x = 5.0
    game_map = SimpleNamespace(units=[transport, passenger])

    assert passenger not in compute_embark_candidates(transport, game_map)

    leader.models[0].model_base.x = 4.0

    assert passenger in compute_embark_candidates(transport, game_map)
