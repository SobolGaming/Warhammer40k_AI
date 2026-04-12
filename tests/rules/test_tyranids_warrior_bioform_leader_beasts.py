from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        invulnerable_save: int = 0,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "40mm",
                "inv_sv": str(int(invulnerable_save)),
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
    invulnerable_save: int = 0,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            objective_control=objective_control,
            invulnerable_save=invulnerable_save,
        )
    )


def _build_army(detachment: str) -> Army:
    army = Army.with_detachment("Tyranids", detachment)
    army.faction_id = "TYR"
    return army


def test_leader_beasts_applies_warrior_keywords_and_objective_control():
    army = _build_army("Warrior Bioform Onslaught")
    warriors = _make_unit(
        "Tyranid Warriors with Ranged Bio-weapons",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        objective_control=1,
    )

    army.add_unit(warriors)

    assert warriors.is_battleline is True
    assert warriors.has_any_keyword("TYRANID WARRIORS")
    model = warriors.models[0]
    assert model.has_any_keyword("TYRANID WARRIORS")
    assert int(model.objective_control) == 3

    warriors.apply_status_effect(BattleShockEffect(current_turn=1))
    assert int(model.objective_control) == 0


def test_leader_beasts_not_applied_outside_warrior_bioform_onslaught():
    army = _build_army("Invasion Fleet")
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        objective_control=1,
    )

    army.add_unit(warriors)

    assert warriors.is_battleline is False
    assert warriors.has_any_keyword("TYRANID WARRIORS") is False
    assert int(warriors.models[0].objective_control) == 1


def test_leader_beasts_grants_five_up_invulnerable_save():
    army = _build_army("Warrior Bioform Onslaught")
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        invulnerable_save=0,
    )
    prime = _make_unit(
        "Winged Tyranid Prime",
        keywords=["INFANTRY", "CHARACTER", "WINGED TYRANID PRIME"],
        faction_keywords=["TYRANIDS"],
        invulnerable_save=0,
    )
    lash_whip_prime = _make_unit(
        "Tyranid Prime with Lash Whip",
        keywords=["INFANTRY", "CHARACTER", "TYRANID PRIME WITH LASH WHIP"],
        faction_keywords=["TYRANIDS"],
        invulnerable_save=0,
    )
    non_eligible = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        invulnerable_save=0,
    )

    army.add_unit(warriors)
    army.add_unit(prime)
    army.add_unit(lash_whip_prime)
    army.add_unit(non_eligible)

    warriors_inv, warriors_source = warriors.get_model_invulnerable_save_override(warriors.models[0])
    prime_inv, prime_source = prime.get_model_invulnerable_save_override(prime.models[0])
    lash_whip_inv, lash_whip_source = lash_whip_prime.get_model_invulnerable_save_override(lash_whip_prime.models[0])
    other_inv, other_source = non_eligible.get_model_invulnerable_save_override(non_eligible.models[0])

    assert int(warriors_inv or 0) == 5
    assert str(warriors_source or "").strip().lower() == "leader-beasts"
    assert int(prime_inv or 0) == 5
    assert str(prime_source or "").strip().lower() == "leader-beasts"
    assert int(lash_whip_inv or 0) == 5
    assert str(lash_whip_source or "").strip().lower() == "leader-beasts"
    assert other_inv is None
    assert other_source is None
