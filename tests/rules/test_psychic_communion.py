import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        datasheet_id,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
        attached_to=None,
        attached_to_names=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = list(attached_to_names or [])


def _make_unit(
    name,
    datasheet_id,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    attached_to=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestPsychicCommunion(unittest.TestCase):
    def test_psychic_communion_unit_variant_caps_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.psychic_communion import apply_psychic_communion_on_selected_to_shoot

        ability = [
            {
                "name": "Psychic Communion (Psychic)",
                "description": (
                    "Each time this unit is selected to shoot, for each Warlock model in this unit, until the end "
                    "of the phase, add 1 to the Attacks and Strength characteristics of that model's Destructor "
                    "weapon for each other friendly Aeldari Psyker model within 6\" of that model (to a maximum of +2)."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        warlocks = _make_unit(
            "Warlock Conclave",
            "W1",
            abilities=ability,
            keywords=["Warlock", "Psyker"],
            faction_keywords=["Aeldari"],
            model_count=2,
        )
        psyker1 = _make_unit(
            "Farseer",
            "P1",
            keywords=["Psyker"],
            faction_keywords=["Aeldari"],
        )
        psyker2 = _make_unit(
            "Spiritseer",
            "P2",
            keywords=["Psyker"],
            faction_keywords=["Aeldari"],
        )

        army = Army.with_detachment("Aeldari", detachment_type="Test")
        army.add_unit(warlocks)
        army.add_unit(psyker1)
        army.add_unit(psyker2)

        for unit in (warlocks, psyker1, psyker2):
            unit.deployed = True

        # Place models within 6" of each other
        warlocks.models[0].set_location(0, 0, 0, 0)
        warlocks.models[1].set_location(1, 0, 0, 0)
        psyker1.models[0].set_location(2, 0, 0, 0)
        psyker2.models[0].set_location(3, 0, 0, 0)

        apply_psychic_communion_on_selected_to_shoot(
            warlocks,
            selected_models=list(warlocks.models),
            phase_name="SHOOTING_PHASE",
        )

        for model in warlocks.models:
            atk_bonus, _ = model.get_temporary_weapon_attacks_bonus("Destructor")
            str_bonus, _ = model.get_temporary_weapon_strength_bonus("Destructor")
            self.assertEqual(atk_bonus, 2)
            self.assertEqual(str_bonus, 2)

    def test_psychic_communion_model_variant_applies_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.psychic_communion import apply_psychic_communion_on_selected_to_shoot

        ability = [
            {
                "name": "Psychic Communion (Psychic)",
                "description": (
                    "Each time this model is selected to shoot, until the end of the phase, add 1 to the Attacks "
                    "and Strength characteristics of its Destructor weapon for each other friendly Aeldari Psyker "
                    "model within 6\" of this model (to a maximum of +2)."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        warlock = _make_unit(
            "Warlock",
            "W2",
            abilities=ability,
            keywords=["Warlock", "Psyker"],
            faction_keywords=["Aeldari"],
        )
        psyker = _make_unit(
            "Farseer",
            "P3",
            keywords=["Psyker"],
            faction_keywords=["Aeldari"],
        )

        army = Army.with_detachment("Aeldari", detachment_type="Test")
        army.add_unit(warlock)
        army.add_unit(psyker)

        warlock.deployed = True
        psyker.deployed = True

        warlock.models[0].set_location(0, 0, 0, 0)
        psyker.models[0].set_location(5, 0, 0, 0)

        apply_psychic_communion_on_selected_to_shoot(
            warlock,
            selected_models=list(warlock.models),
            phase_name="SHOOTING_PHASE",
        )

        atk_bonus, _ = warlock.models[0].get_temporary_weapon_attacks_bonus("Destructor")
        str_bonus, _ = warlock.models[0].get_temporary_weapon_strength_bonus("Destructor")
        self.assertEqual(atk_bonus, 1)
        self.assertEqual(str_bonus, 1)
