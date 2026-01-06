import unittest


class TestWarlordAndPactRestrictions(unittest.TestCase):
    def test_supreme_commander_must_be_warlord(self):
        from warhammer40k_ai.classes.army import Army, ArmyValidationError
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.ability import Ability

        def _unit(name: str, *, supreme: bool, warlord: bool) -> Unit:
            u = Unit.__new__(Unit)
            u.name = name
            u.is_warlord = bool(warlord)
            u.possible_abilities = []
            if supreme:
                u.possible_abilities.append(
                    Ability(
                        name="SUPREME COMMANDER",
                        faction_id="",
                        description="If this unit is in your army, it must be your Warlord.",
                        type="Special",
                        parameter="",
                        legend=None,
                    )
                )
            return u

        army = Army("World Eaters", detachment_type="Some Detachment")
        army.faction_id = "WE"
        sc = _unit("The Silent King", supreme=True, warlord=False)
        other = _unit("Other", supreme=False, warlord=True)
        army.units = [sc, other]

        with self.assertRaises(ArmyValidationError):
            army.validate_warlord()

        # Fix: make Supreme Commander the warlord
        sc.is_warlord = True
        other.is_warlord = False
        army.validate_warlord()

    def test_pact_of_blood_disallows_blood_legions_army_faction(self):
        from warhammer40k_ai.classes.army import Army, ArmyValidationError

        army = Army("Blood Legions", detachment_type="Some Detachment")
        army.faction_id = "WE"
        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_pact_of_sorcery_disallows_scintillating_legions_army_faction(self):
        from warhammer40k_ai.classes.army import Army, ArmyValidationError

        army = Army("Scintillating Legions", detachment_type="Some Detachment")
        army.faction_id = "TS"
        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()


if __name__ == "__main__":
    unittest.main()
