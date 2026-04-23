import unittest

from types import SimpleNamespace

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import RuinsTerrain
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.constants import RUINS_FLOOR_THICKNESS
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _ModelStub:
    def __init__(self, *, wounds: int, base_wounds: int, name: str):
        self.name = name
        self._base_wounds = base_wounds
        self._wounds = wounds
        self.parent_unit = None

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


class _MockDatasheet:
    def __init__(self, name: str, datasheet_id: str, *, model_count: int = 1):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Necrons"}
        self.keywords = []
        self.faction_keywords = ["NECRONS"]
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "4",
                "Sv": "3",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "Reanimation Protocols",
                "description": (
                    "At the end of your Command phase, this unit activates its Reanimation Protocols "
                    "and reanimates D3 wounds."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_game_unit(*, name: str, datasheet_id: str, model_count: int = 2):
    ds = _MockDatasheet(name=name, datasheet_id=datasheet_id, model_count=model_count)
    unit = Unit(ds)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game_with_unit(unit, *, local: bool):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army = Army.with_detachment("Necrons", "Awakened Dynasty")
    army.faction_id = "NEC"
    army.add_unit(unit)
    control = PlayerControl.LOCAL if local else PlayerControl.REMOTE
    player = Player("P1", control=control, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    game.map.units = [unit]
    game.rebuild_entity_registry()
    return game, player


class TestReanimationProtocols(unittest.TestCase):
    def _make_unit(self, models, lost=None):
        u = Unit.__new__(Unit)
        u.models = list(models or [])
        u.models_lost = list(lost or [])
        for m in u.models + u.models_lost:
            try:
                m.set_parent_unit(u)
            except Exception:
                m.parent_unit = u
        u.deployed = True
        u.reserve_status = "deployed"
        u.embarked_in = None
        u.can_be_attached_to = []
        u.attached_to = None
        u.attached_leaders = []
        u._ability_cache = {}
        u.status_effects = []
        u.special_rules = {}
        u.round_state = SimpleNamespace()
        u.starting_model_count = len(u.models) + len(u.models_lost)
        u.starting_total_wounds = sum(m._base_wounds for m in (u.models + u.models_lost))
        return u

    def test_reanimation_heals_wounded_before_return(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=3, base_wounds=3, name="Model 2")
        lost = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        unit = self._make_unit([m1, m2], lost=[lost])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 3)
        self.assertEqual(len(unit.models), 2)
        self.assertEqual(len(unit.models_lost), 1)

    def test_reanimation_returns_models_when_full(self):
        m1 = _ModelStub(wounds=3, base_wounds=3, name="Model 1")
        lost1 = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        lost2 = _ModelStub(wounds=0, base_wounds=3, name="Lost 2")
        unit = self._make_unit([m1], lost=[lost1, lost2])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(len(unit.models), 2)
        self.assertEqual(len(unit.models_lost), 1)
        returned = [m for m in unit.models if m is not m1]
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0].wounds, 2)

    def test_reanimation_heal_then_return(self):
        m1 = _ModelStub(wounds=2, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=3, base_wounds=3, name="Model 2")
        lost1 = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        unit = self._make_unit([m1, m2], lost=[lost1])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 3)
        self.assertEqual(len(unit.models), 3)
        self.assertEqual(len(unit.models_lost), 0)
        returned = [m for m in unit.models if m is lost1]
        self.assertEqual(returned[0].wounds, 1)

    def test_reanimation_skips_embarked_units(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        unit = self._make_unit([m1], lost=[])
        unit.embarked_in = object()

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 1)

    def test_reanimation_skips_units_in_reserves(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        unit = self._make_unit([m1], lost=[])
        unit.reserve_status = "reserves"

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 1)

    def test_reanimation_uses_provider_only_with_choices(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=1, base_wounds=3, name="Model 2")
        unit = self._make_unit([m1, m2], lost=[])
        calls = []

        def provider(_unit, eligible, ctx):
            calls.append((eligible, ctx))
            return eligible[1]

        unit.apply_reanimation_protocols(1, game_map=None, is_human=True, provider=provider)

        self.assertEqual(len(calls), 1)
        self.assertEqual(m2.wounds, 2)
        self.assertEqual(m1.wounds, 1)


def test_reanimation_provider_path_emits_allocate_damage_request():
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE

    unit = _make_game_unit(name="Warriors", datasheet_id="necron_reanim_local", model_count=2)
    first, second = unit.models[0], unit.models[1]
    first.wounds = 3
    second.wounds = 2

    game, _player = _build_game_with_unit(unit, local=False)
    captured = []

    def _capture(request):
        captured.append(request)
        game.decision_queue.add(request)

    def _apply(command):
        payload = dict(getattr(command, "payload", {}) or {})
        request = game.decision_queue.get(str(payload.get("decision_id", "") or ""))
        option_id = str(payload.get("option_id", "") or "")
        option = next(
            opt for opt in list(getattr(request, "options", []) or []) if str(getattr(opt, "option_id", "") or "") == option_id
        )
        resolved_payload = dict(getattr(option, "payload", {}) or {})
        apply_result = SimpleNamespace(ok=True, value=resolved_payload)
        setattr(request, "_resolved_decision_value", resolved_payload)
        setattr(request, "_resolved_decision_apply_result", apply_result)
        game.decision_queue.pop(request.decision_id)
        return SimpleNamespace(value=apply_result)

    def _provider(_unit, eligible, ctx):
        assert str((ctx or {}).get("selection_kind", "") or "") == "reanimation_restore_wound"
        return eligible[1]

    game.request_decision = _capture
    game.apply_command = _apply
    game.map.reanimation_allocation_provider = _provider

    result = unit.apply_reanimation_protocols(
        1,
        game_map=game.map,
        is_human=True,
        provider=game.map.reanimation_allocation_provider,
    )

    assert result == {"healed": 1, "returned": 0}
    assert int(first.wounds or 0) == 3
    assert int(second.wounds or 0) == 3
    requests = [
        req
        for req in captured
        if str(getattr(req, "decision_type", "") or "") == DECISION_ALLOCATE_DAMAGE
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "reanimation_restore_wound"
    ]
    assert len(requests) == 1
    option_model_ids = [
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(requests[0].options or [])
    ]
    assert option_model_ids == [str(get_entity_id(first) or ""), str(get_entity_id(second) or "")]


def test_reanimation_return_model_emits_allocate_damage_request_and_resolves_same_request():
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    unit = _make_game_unit(name="Warriors", datasheet_id="necron_reanim_return", model_count=3)
    lost_first = unit.models[1]
    lost_second = unit.models[2]
    lost_first_id = str(get_entity_id(lost_first) or "")
    lost_second_id = str(get_entity_id(lost_second) or "")
    unit.remove_model(lost_first)
    unit.remove_model(lost_second)

    game, player = _build_game_with_unit(unit, local=False)
    captured = []
    original_request = game.request_decision

    def _auto_resolve(request):
        captured.append(request)
        original_request(request)
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("model_id", "") or "") == lost_first_id
        )
        applied = resolve_decision_command(game, request, option.option_id, player_id=player.id)
        assert getattr(applied, "ok", False) is True

    game.request_decision = _auto_resolve

    result = unit.apply_reanimation_protocols(
        1,
        game_map=game.map,
        is_human=False,
        provider=None,
    )

    assert result == {"healed": 0, "returned": 1}
    assert lost_first in list(unit.models or [])
    assert lost_second in list(unit.models_lost or [])
    requests = [
        req
        for req in captured
        if str(getattr(req, "decision_type", "") or "") == DECISION_ALLOCATE_DAMAGE
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "reanimation_return_model"
    ]
    assert len(requests) == 1
    option_model_ids = [
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(requests[0].options or [])
    ]
    assert option_model_ids == [lost_first_id, lost_second_id]


def test_reanimation_return_model_without_sync_owner_raises_and_stays_pending():
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE

    unit = _make_game_unit(name="Warriors", datasheet_id="necron_reanim_pending", model_count=3)
    lost_first = unit.models[1]
    lost_second = unit.models[2]
    unit.remove_model(lost_first)
    unit.remove_model(lost_second)

    game, _player = _build_game_with_unit(unit, local=False)

    try:
        unit.apply_reanimation_protocols(
            1,
            game_map=game.map,
            is_human=False,
            provider=None,
        )
    except RuntimeError as exc:
        assert "Reanimation allocation decision remained pending without a synchronous decision owner" in str(exc)
    else:
        raise AssertionError("Expected reanimation selection without a synchronous owner to raise RuntimeError.")

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_ALLOCATE_DAMAGE
        and str((getattr(req, "context", {}) or {}).get("selection_kind", "") or "") == "reanimation_return_model"
    ]
    assert len(pending) == 1


def test_reanimation_position_valid_rejects_ruins_wall_overlap():
    unit = _make_game_unit(name="Warriors", datasheet_id="necron_reanim_ruins", model_count=2)
    game, _player = _build_game_with_unit(unit, local=False)
    footprint = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    wall = Polygon([(4.8, 0.0), (5.2, 0.0), (5.2, 10.0), (4.8, 10.0)])
    ruins = RuinsTerrain(
        footprint=footprint,
        walls=[{"polygon": wall, "z_bottom": 0.0, "z_top": 2.0, "thickness": 0.4}],
        openings=[],
        floors=[{"polygon": footprint, "elevation": 0.0, "thickness": RUINS_FLOOR_THICKNESS}],
        height_map={},
    )
    game.map.terrain_features = [ruins]

    anchor = unit.models[0]
    target = unit.models[1]
    anchor.set_location(2.0, 5.0, RUINS_FLOOR_THICKNESS, 0.0)
    target.set_location(8.0, 5.0, RUINS_FLOOR_THICKNESS, 0.0)

    assert unit._reanimation_position_valid(
        5.0,
        5.0,
        RUINS_FLOOR_THICKNESS,
        0.0,
        target,
        [anchor],
        game.map,
        0,
    ) is False


if __name__ == "__main__":
    unittest.main()
