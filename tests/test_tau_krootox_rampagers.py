from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        ds_id: str = "",
        abilities=None,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "2",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
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
        self.attached_to = []


def _make_unit(name: str, *, abilities=None, keywords=None, model_count: int = 1, wounds: str = "2"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        model_count=model_count,
        wounds=wounds,
    )
    return Unit(datasheet)


def _alive_count(unit) -> int:
    count = 0
    for model in list(getattr(unit, "models", []) or []):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if alive:
            count += 1
    return count


def test_kroot_linebreakers_battleshocks_target_after_model_destroyed_by_mortals():
    from warhammer40k_ai.engine.game import Game

    linebreakers = {
        "name": "Kroot Linebreakers",
        "description": (
            "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it, "
            "then roll one D6 for each model in this unit that is within Engagement Range of that enemy unit: "
            "for each 4+, that enemy unit suffers D3 mortal wounds. "
            "If one or more enemy models are destroyed as a result of these mortal wounds, "
            "that enemy unit must take a Battle-shock test."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    rampagers = _make_unit("Krootox Rampagers", abilities=[linebreakers], keywords=["KROOT"], model_count=2)
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=2, wounds="1")

    specs = list(rampagers.special_rules.get("charge_end_mortal_wounds", []) or [])
    assert len(specs) == 1
    assert bool(specs[0].get("battle_shock_on_models_destroyed", False))

    battle_shock_calls: list[int] = []
    target.take_battle_shock_test = lambda turn: battle_shock_calls.append(int(turn))

    game_stub = SimpleNamespace(map=None, turn=3)

    with patch("warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit", return_value=True):
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 1, 3]):
            Game.resolve_charge_end_mortal_wounds(game_stub, rampagers, target, specs[0])

    assert _alive_count(target) == 1
    assert battle_shock_calls == [3]


def test_kroot_linebreakers_does_not_battleshock_when_no_models_destroyed():
    from warhammer40k_ai.engine.game import Game

    linebreakers = {
        "name": "Kroot Linebreakers",
        "description": (
            "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it, "
            "then roll one D6 for each model in this unit that is within Engagement Range of that enemy unit: "
            "for each 4+, that enemy unit suffers D3 mortal wounds. "
            "If one or more enemy models are destroyed as a result of these mortal wounds, "
            "that enemy unit must take a Battle-shock test."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    rampagers = _make_unit("Krootox Rampagers", abilities=[linebreakers], keywords=["KROOT"], model_count=2)
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=2, wounds="1")
    spec = list(rampagers.special_rules.get("charge_end_mortal_wounds", []) or [])[0]

    battle_shock_calls: list[int] = []
    target.take_battle_shock_test = lambda turn: battle_shock_calls.append(int(turn))

    game_stub = SimpleNamespace(map=None, turn=4)

    with patch("warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit", return_value=True):
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[3, 3]):
            Game.resolve_charge_end_mortal_wounds(game_stub, rampagers, target, spec)

    assert _alive_count(target) == 2
    assert not battle_shock_calls
