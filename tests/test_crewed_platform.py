from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType


class _DummyEventSystem:
    def publish(self, *_args, **_kwargs):
        return None


class _DummyGame:
    def __init__(self):
        self.event_system = _DummyEventSystem()


class _DummyPlayer:
    def __init__(self):
        self.name = "P1"
        self.game = _DummyGame()


class _DummyDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "4",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _build_model(name: str) -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=3,
        save=4,
        wounds=1,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )


def _make_unit(name: str, ability_desc: str, models: list[Model]) -> Unit:
    ability = {
        "name": "Crewed Platform",
        "description": ability_desc,
        "type": "Datasheet",
        "parameter": "",
    }
    datasheet = _DummyDatasheet(name, abilities=[ability])
    unit = Unit(datasheet)
    unit.models = list(models)
    for m in unit.models:
        m.parent_unit = unit
    army = SimpleNamespace(player=_DummyPlayer())
    unit.parent_army = army
    return unit


def test_crewed_platform_guardian_defenders_destroys_platforms():
    ability_desc = (
        "When the last Guardian Defender model in this unit is destroyed, any remaining Heavy Weapon Platform "
        "models in this unit are also destroyed."
    )
    guardian = _build_model("Guardian Defender")
    platform = _build_model("Heavy Weapon Platform")
    unit = _make_unit("Guardian Defenders", ability_desc, [guardian, platform])
    guardian.wounds = 0
    guardian.die(game_map=SimpleNamespace())
    assert platform not in unit.models
    assert len(unit.models) == 0


def test_crewed_platform_storm_guardians_destroys_platforms():
    ability_desc = (
        "When the last Storm Guardian model in this unit is destroyed, any remaining Serpent's Scale Platform "
        "models in this unit are also destroyed."
    )
    guardian = _build_model("Storm Guardian")
    platform = _build_model("Serpent's Scale Platform")
    unit = _make_unit("Storm Guardians", ability_desc, [guardian, platform])
    guardian.wounds = 0
    guardian.die(game_map=SimpleNamespace())
    assert platform not in unit.models
    assert len(unit.models) == 0


def test_crewed_platform_does_not_trigger_with_crew_remaining():
    ability_desc = (
        "When the last Guardian Defender model in this unit is destroyed, any remaining Heavy Weapon Platform "
        "models in this unit are also destroyed."
    )
    guardian1 = _build_model("Guardian Defender")
    guardian2 = _build_model("Guardian Defender")
    platform = _build_model("Heavy Weapon Platform")
    unit = _make_unit("Guardian Defenders", ability_desc, [guardian1, guardian2, platform])
    guardian1.wounds = 0
    guardian1.die(game_map=SimpleNamespace())
    assert platform in unit.models
    assert guardian2 in unit.models
