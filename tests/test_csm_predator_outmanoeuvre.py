from warhammer40k_ai.units.unit import Unit


class _Datasheet:
    def __init__(self, *, name: str, keywords: list[str], model_stats: dict, wargear_rows: list[dict], abilities: list[dict]):
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords)
        self.faction_keywords = ["HERETIC ASTARTES"]
        self.datasheets_unit_composition = [{"description": f"1 {name}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [dict(model_stats)]
        self.datasheets_wargear = list(wargear_rows)
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities)
        if wargear_rows:
            names = "; ".join(str(row.get("name", "") or "").strip() for row in wargear_rows if str(row.get("name", "") or "").strip())
            self.loadout = f"This model is equipped with: {names}."
        else:
            self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _model_stats(*, toughness: str = "10") -> dict:
    return {
        "M": "10",
        "T": toughness,
        "Sv": "3",
        "W": "11",
        "Ld": "7",
        "OC": "3",
        "base_size": "90mm",
        "inv_sv": "0",
        "inv_sv_descr": "",
    }


def _make_target_unit(*, name: str, keywords: list[str], toughness: str) -> Unit:
    ds = _Datasheet(
        name=name,
        keywords=keywords,
        model_stats=_model_stats(toughness=toughness),
        wargear_rows=[],
        abilities=[],
    )
    return Unit(ds)


def test_annihilator_parses_monster_vehicle_damage_reroll_rule():
    ds = _Datasheet(
        name="Chaos Predator Annihilator",
        keywords=["VEHICLE"],
        model_stats=_model_stats(toughness="10"),
        wargear_rows=[
            {
                "name": "Twin lascannon",
                "type": "Ranged",
                "range": "48",
                "A": "2",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "D6",
                "description": "",
            }
        ],
        abilities=[
            {
                "name": "Annihilator",
                "description": (
                    "Each time a ranged attack made by this model is allocated to a MONSTER or VEHICLE model, "
                    "you can re-roll the Damage roll."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    unit = Unit(ds)
    model = unit.models[0]

    rule = unit.get_monster_vehicle_reroll_rule(model)

    assert isinstance(rule, dict)
    assert rule.get("reroll_hit") is False
    assert rule.get("reroll_wound") is False
    assert rule.get("reroll_damage") is True
    assert rule.get("requires_shooting_phase") is False


def test_destructor_ap_bonus_applies_only_vs_infantry():
    ds = _Datasheet(
        name="Chaos Predator Destructor",
        keywords=["VEHICLE"],
        model_stats=_model_stats(toughness="10"),
        wargear_rows=[
            {
                "name": "Predator autocannon",
                "type": "Ranged",
                "range": "48",
                "A": "2",
                "BS_WS": "3+",
                "S": "9",
                "AP": "-1",
                "D": "3",
                "description": "",
            }
        ],
        abilities=[
            {
                "name": "Destructor",
                "description": (
                    "Each time a ranged attack made by this model targets an enemy INFANTRY unit, "
                    "improve the Armour Penetration characteristic of that attack by 1."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    unit = Unit(ds)
    model = unit.models[0]
    profile = next(iter(model.wargear[0].profiles.values()))

    infantry = _make_target_unit(name="Infantry Target", keywords=["INFANTRY"], toughness="5")
    vehicle = _make_target_unit(name="Vehicle Target", keywords=["VEHICLE"], toughness="10")

    assert profile.get_effective_ap(model, infantry) == -2
    assert profile.get_effective_ap(model, vehicle) == -1


def test_outmanoeuvre_grants_melee_strength_when_charged():
    ds = _Datasheet(
        name="Chaos Bikers",
        keywords=["INFANTRY"],
        model_stats=_model_stats(toughness="5"),
        wargear_rows=[
            {
                "name": "Astartes chainsword",
                "type": "Melee",
                "range": "Melee",
                "A": "3",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-1",
                "D": "1",
                "description": "",
            }
        ],
        abilities=[
            {
                "name": "Outmanoeuvre",
                "description": (
                    "Each time a model in this unit makes a melee attack, if this unit made a Charge move this turn, "
                    "improve the Strength characteristic of that attack by 1."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    unit = Unit(ds)
    unit.round_state.charged_this_round = True
    model = unit.models[0]
    profile = next(iter(model.wargear[0].profiles.values()))

    target = _make_target_unit(name="Tough Target", keywords=["INFANTRY"], toughness="5")
    wound_result = profile._wound_target_with_tracking(
        target,
        model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result.get("needed") == 4
