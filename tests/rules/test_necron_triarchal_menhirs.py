from types import SimpleNamespace

from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class _DummyEventSystem:
    def __init__(self):
        self.published = []

    def publish(self, event_name, **kwargs):
        self.published.append((event_name, kwargs))


class _DummyGame:
    def __init__(self):
        self.event_system = _DummyEventSystem()


class _DummyPlayer:
    def __init__(self, game):
        self.name = "P1"
        self.id = "P1"
        self.game = game


class _DummyDatasheet:
    def __init__(self, *, abilities):
        self.id = "000002360"
        self.name = "The Silent King"
        self.faction_data = {"name": "Necrons"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "10",
                "Sv": "2",
                "W": "16",
                "Ld": "6",
                "OC": "6",
                "base_size": "100mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _build_model(name: str, wounds: int) -> Model:
    return Model(
        name=name,
        movement=8,
        toughness=10,
        save=2,
        wounds=wounds,
        leadership=6,
        objective_control=6,
        model_base=Base(BaseType.CIRCULAR, 1.0),
        inv_save=4,
    )


def _triarchal_menhirs_ability_row() -> dict:
    return {
        "name": "TRIARCHAL MENHIRS",
        "description": (
            "If this unit's Szarekh model is destroyed, all of this unit's remaining "
            "Triarchal Menhir models are also destroyed."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _make_silent_king_unit(*, with_triarchal_menhirs: bool) -> tuple[Unit, _DummyGame]:
    abilities = [_triarchal_menhirs_ability_row()] if with_triarchal_menhirs else []
    datasheet = _DummyDatasheet(abilities=abilities)
    unit = Unit(datasheet)
    unit.models = [
        _build_model("SZAREKH", wounds=16),
        _build_model("TRIARCHAL MENHIR", wounds=5),
        _build_model("TRIARCHAL MENHIR", wounds=5),
    ]
    for model in list(unit.models):
        model.parent_unit = unit

    game = _DummyGame()
    army = SimpleNamespace(player=_DummyPlayer(game))
    unit.parent_army = army
    return unit, game


def _unit_model_names(unit: Unit) -> list[str]:
    return [str(getattr(model, "name", "") or "") for model in list(getattr(unit, "models", []) or [])]


def test_triarchal_menhirs_destroy_remaining_menhirs_when_szarekh_dies():
    unit, game = _make_silent_king_unit(with_triarchal_menhirs=True)
    szarekh = next(model for model in unit.models if model.name == "SZAREKH")

    szarekh.wounds = 0
    szarekh.die(game_map=SimpleNamespace())

    assert len(unit.models) == 0
    unit_destroyed_events = [entry for entry in list(game.event_system.published or []) if entry[0] == "unit_destroyed"]
    assert len(unit_destroyed_events) == 1
    assert unit_destroyed_events[0][1].get("unit") is unit
    assert unit_destroyed_events[0][1].get("last_model") is szarekh


def test_triarchal_menhirs_does_not_trigger_when_menhir_dies():
    unit, game = _make_silent_king_unit(with_triarchal_menhirs=True)
    menhir = next(model for model in unit.models if model.name == "TRIARCHAL MENHIR")

    menhir.wounds = 0
    menhir.die(game_map=SimpleNamespace())

    names = _unit_model_names(unit)
    assert names.count("SZAREKH") == 1
    assert names.count("TRIARCHAL MENHIR") == 1
    assert len(unit.models) == 2
    assert not any(event_name == "unit_destroyed" for event_name, _payload in list(game.event_system.published or []))


def test_triarchal_menhirs_requires_ability():
    unit, game = _make_silent_king_unit(with_triarchal_menhirs=False)
    szarekh = next(model for model in unit.models if model.name == "SZAREKH")

    szarekh.wounds = 0
    szarekh.die(game_map=SimpleNamespace())

    names = _unit_model_names(unit)
    assert names.count("TRIARCHAL MENHIR") == 2
    assert names.count("SZAREKH") == 0
    assert len(unit.models) == 2
    assert not any(event_name == "unit_destroyed" for event_name, _payload in list(game.event_system.published or []))
