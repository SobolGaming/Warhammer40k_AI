from warhammer40k_ai.units.unit import Unit


DEATH_TOTEM_TEXT = "Each time the bearer makes a melee attack, re-roll a Hit roll of 1."
DEATH_TO_THE_ALIEN_TEXT = (
    "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
    "If the target of that attack does not have the IMPERIUM or CHAOS keywords, "
    "you can re-roll the Hit roll instead."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Astartes",
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Astartes",
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_death_totem_optional_wargear_grants_melee_hit_reroll_ones():
    wulfen = _make_unit(
        "Wulfen",
        abilities=[
            {
                "name": "Death Totem",
                "description": DEATH_TOTEM_TEXT,
                "type": "Wargear",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "WULFEN"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    bearer = wulfen.models[0]
    bearer.optional_wargear.append("Death Totem")

    melee_mods = wulfen.get_model_hit_reroll_modifiers(bearer, attack_type="melee")

    assert 1 in tuple(melee_mods.get("reroll_hit_values", ()) or ())
    assert not bool(melee_mods.get("reroll_hit_full", False))
    assert any("Death Totem" in str(reason or "") for reason in list(melee_mods.get("reroll_hit_reasons", ()) or ()))

    ranged_mods = wulfen.get_model_hit_reroll_modifiers(bearer, attack_type="ranged")
    assert 1 not in tuple(ranged_mods.get("reroll_hit_values", ()) or ())


def test_death_to_the_alien_stays_reroll_ones_vs_imperium_targets():
    deathwatch = _make_unit(
        "Deathwatch Veterans",
        abilities=[
            {
                "name": "Death to the Alien",
                "description": DEATH_TO_THE_ALIEN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["ADEPTUS ASTARTES", "IMPERIUM"],
    )
    imperium_target = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    hit_mods = deathwatch.get_unit_hit_reroll_modifiers(
        "ranged",
        target=imperium_target,
        attacker_model=deathwatch.models[0],
    )

    assert bool(hit_mods.get("reroll_hit_ones", False))
    assert not bool(hit_mods.get("reroll_hit_full", False))
    assert any(
        "Death to the Alien" in str(reason or "")
        for reason in list(hit_mods.get("reroll_hit_reasons", ()) or ())
    )


def test_death_to_the_alien_upgrades_to_full_rerolls_vs_non_imperium_non_chaos_targets():
    deathwatch = _make_unit(
        "Deathwatch Veterans",
        abilities=[
            {
                "name": "Death to the Alien",
                "description": DEATH_TO_THE_ALIEN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["ADEPTUS ASTARTES", "IMPERIUM"],
    )
    xenos_target = _make_unit(
        "Hormagaunts",
        faction_name="Tyranids",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )

    hit_mods = deathwatch.get_unit_hit_reroll_modifiers(
        "melee",
        target=xenos_target,
        attacker_model=deathwatch.models[0],
    )

    assert bool(hit_mods.get("reroll_hit_ones", False))
    assert bool(hit_mods.get("reroll_hit_full", False))
    assert any(
        "Death to the Alien" in str(reason or "")
        for reason in list(hit_mods.get("reroll_hit_full_reasons", ()) or ())
    )
