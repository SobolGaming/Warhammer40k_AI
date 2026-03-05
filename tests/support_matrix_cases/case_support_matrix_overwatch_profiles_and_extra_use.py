import pytest


@pytest.mark.parametrize(
    "name,description,faction_id",
    [
        (
            "Inescapable Death",
            (
                "Once per turn, one unit from your army with this ability can be targeted with the Fire Overwatch Stratagem for 0CP, "
                "even if you have already used that Stratagem on a different unit this phase. In addition, each time you target this "
                "unit with the Fire Overwatch Stratagem, while resolving that Stratagem, hits are scored on unmodified Hit rolls of 2+."
            ),
            "NEC",
        ),
        (
            "Defensive Stance",
            (
                "Each time you target this unit with the Fire Overwatch Stratagem, while resolving that Stratagem, hits are scored on "
                "unmodified Hit rolls of 5+, or unmodified Hit rolls of 4+ instead if this unit is within range of an objective marker."
            ),
            "TYR",
        ),
        (
            "Hive Defences",
            (
                "You can target this model with the Fire Overwatch Stratagem for 0CP, and can do so even if you have already targeted a "
                "different unit with that Stratagem this turn. This model can only be targeted with that Stratagem once per turn."
            ),
            "TYR",
        ),
        (
            "Defensive Array",
            (
                "You can target this FORTIFICATION with the Fire Overwatch Stratagem for 0CP, and can do so even if you have already "
                "targeted another unit with that Stratagem this turn. This FORTIFICATION can only be targeted with that Stratagem once per turn."
            ),
            "SM",
        ),
        (
            "Sentinel Protocols",
            (
                "Each time you select this unit for the Fire Overwatch Stratagem, hits are scored on unmodified Hit rolls of 4+ when "
                "resolving that Stratagem."
            ),
            "SM",
        ),
    ],
)
def test_support_matrix_overwatch_profiles_and_extra_use_supported(name, description, faction_id):
    import scripts.generate_ability_support_matrix as gsm

    status, _notes = gsm._classify_ability(name, description, faction_id=faction_id)
    assert status == "Supported"

