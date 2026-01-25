import types
import pytest

from warhammer40k_ai.units.unit import Unit
import warhammer40k_ai.units.unit as unit_module


class _ModelStub:
    def __init__(self, name: str, kind: str, wounds: int = 1, base_wounds: int = 1):
        self.name = name
        self._horrors_kind = kind
        self._last_damage_source_kind = None
        self._pending_placement = False
        self._pending_placement_source = None
        self.parent_unit = None
        self._base_wounds = int(base_wounds)
        self._wounds = int(wounds)

    @property
    def is_alive(self) -> bool:
        return self._wounds > 0

    @property
    def wounds(self) -> int:
        return self._wounds

    @wounds.setter
    def wounds(self, value: int) -> None:
        self._wounds = int(value)

    @property
    def is_max_health(self) -> bool:
        return self._wounds >= self._base_wounds

    def heal(self, amount: int) -> None:
        self._wounds = min(self._base_wounds, self._wounds + int(amount or 0))

    def set_parent_unit(self, unit) -> None:
        self.parent_unit = unit

    def die(self, game_map=None) -> None:
        self._wounds = 0


def _make_horrors_unit(origin: str, state: str, models, lost=None):
    unit = Unit.__new__(Unit)
    unit.models = list(models or [])
    unit.models_lost = list(lost or [])
    for m in unit.models + unit.models_lost:
        try:
            m.set_parent_unit(unit)
        except Exception:
            m.parent_unit = unit
    unit._horrors_origin = origin
    unit._horrors_state = state
    unit._pending_horrors_split = []
    unit._attack_resolution_depth = 0
    unit._ability_cache = {}
    unit.parent_army = None
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.can_be_attached_to = []
    unit.attached_to = None
    unit.attached_leaders = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = types.SimpleNamespace()
    unit.starting_model_count = len(unit.models) + len(unit.models_lost)
    unit.starting_total_wounds = sum(getattr(m, "_base_wounds", 1) for m in unit.models + unit.models_lost)
    unit._request_pending_placement_decision = lambda *args, **kwargs: None
    return unit


def test_split_ignores_non_attack_damage():
    model = _ModelStub("Pink Horror", "pink")
    model._last_damage_source_kind = "non_attack"
    unit = _make_horrors_unit("pink", "pink", [model])
    unit._attack_resolution_depth = 1

    unit._maybe_queue_horrors_split(model)

    assert unit._pending_horrors_split == []


def test_split_spawns_on_attack(monkeypatch):
    model = _ModelStub("Pink Horror", "pink")
    model._last_damage_source_kind = "attack"
    unit = _make_horrors_unit("pink", "pink", [model])
    unit._attack_resolution_depth = 1

    spawned = [_ModelStub("Blue Horror", "blue"), _ModelStub("Blue Horror", "blue")]
    calls = []

    def _spawn(kind, count, *, from_split=True):
        calls.append((kind, count, from_split))
        return spawned

    unit._spawn_horrors_models = _spawn
    placements = []
    unit._request_pending_placement_decision = lambda *args, **kwargs: placements.append(True)

    monkeypatch.setattr(unit_module, "get_roll", lambda _d: 6)

    unit._maybe_queue_horrors_split(model)
    unit._resolve_pending_horrors_split(game_map=None)

    assert calls == [("blue", 2, True)]
    assert all(m._pending_placement for m in spawned)
    assert len(unit.models) == 3
    assert placements


def test_split_triggers_on_hazardous(monkeypatch):
    model = _ModelStub("Blue Horror", "blue")
    model._last_damage_source_kind = "hazardous"
    unit = _make_horrors_unit("blue", "blue", [model])
    unit._attack_resolution_depth = 0

    spawned = [_ModelStub("Brimstone Horror", "brimstone")]
    unit._spawn_horrors_models = lambda kind, count, *, from_split=True: spawned

    monkeypatch.setattr(unit_module, "get_roll", lambda _d: 6)

    unit._maybe_queue_horrors_split(model)
    unit._resolve_pending_horrors_split(game_map=None)

    assert len(unit.models) == 2
    assert spawned[0]._pending_placement is True


def test_reanimation_skips_pink_after_swap():
    alive = _ModelStub("Blue Horror", "blue")
    lost_pink = _ModelStub("Pink Horror", "pink", wounds=0)
    lost_blue = _ModelStub("Blue Horror", "blue", wounds=0)
    unit = _make_horrors_unit("pink", "blue", [alive], lost=[lost_pink, lost_blue])

    unit.apply_reanimation_protocols(1, game_map=None, is_human=False, provider=None)

    assert lost_blue in unit.models
    assert lost_pink in unit.models_lost
    assert getattr(lost_blue, "_pending_placement", False) is True
