import types


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, leadership="6"):
        self.id = "ds_dark_pacts"
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "2",
            "Ld": str(leadership),
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, abilities=None, leadership="6"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, leadership=leadership)
    return Unit(datasheet)


def test_dark_pacts_leadership_reroll(monkeypatch):
    ability = {
        "name": "Chaos Icon",
        "description": "Each time the bearer's unit takes a Leadership test for the Dark Pacts ability, you can re-roll that test.",
        "type": "Datasheet",
        "parameter": "",
    }
    dark_pacts = {
        "name": "Dark Pacts",
        "description": "",
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit("Chaos Bikers", abilities=[dark_pacts, ability], leadership="6")

    class _Army:
        def __init__(self, units):
            self.units = list(units)
            self.player = None
            self.faction_id = "CSM"

    army = _Army([unit])
    unit.set_parent_army(army)

    rolls = {"2D6": [12, 5]}
    roll_calls = []

    def _fake_get_roll(die):
        roll_calls.append(die)
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.units.unit.get_roll", _fake_get_roll)

    applied = {"called": False}

    def _apply(self, target, amount, game_map=None):
        applied["called"] = True
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    ok = unit.apply_dark_pacts_choice(
        game=None,
        choice="LETHAL HITS",
        phase_name="SHOOTING_PHASE",
        trigger="shooting",
    )

    assert ok is True
    assert applied["called"] is False
    assert roll_calls == ["2D6", "2D6"]
