from __future__ import annotations

from warhammer40k_ai.units.model import Model


class _FakeModel:
    name = "Fake Model"
    id = "fake-model"

    def __init__(self, parent_unit):
        self.parent_unit = parent_unit


class _PreRemovingParent:
    def __init__(self):
        self.models = []
        self.remove_calls = 0

    def _handle_model_destroyed(self, *, model, game_map=None):
        self.models.remove(model)

    def remove_model(self, model, fleed=False, game_map=None):
        self.remove_calls += 1
        raise AssertionError("die() should not remove a model that was removed by a destruction hook")


class _NormalParent:
    def __init__(self):
        self.models = []
        self.removed = []

    def _handle_model_destroyed(self, *, model, game_map=None):
        return None

    def remove_model(self, model, fleed=False, game_map=None):
        self.models.remove(model)
        self.removed.append((model, fleed, game_map))


def test_die_does_not_double_remove_when_destruction_hook_removed_model():
    parent = _PreRemovingParent()
    model = _FakeModel(parent)
    parent.models.append(model)

    Model.die(model, game_map=None)

    assert parent.models == []
    assert parent.remove_calls == 0


def test_die_removes_model_after_destruction_hook_when_still_present():
    parent = _NormalParent()
    model = _FakeModel(parent)
    parent.models.append(model)

    Model.die(model, game_map="map")

    assert parent.models == []
    assert parent.removed == [(model, False, "map")]
