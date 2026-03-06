import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Bound Creation",
            (
                "While this unit is in the same unit as a Cryptek model, that CRYPTEK model has the Feel No Pain 4+ ability."
            ),
        ),
        (
            "Grand Illusion",
            (
                "If your army includes this model, after both players have deployed their armies, select up to three "
                "NECRONS units from your army and redeploy them. When doing so, any of those units can be placed into "
                "Strategic Reserves, regardless of how many units are already in Strategic Reserves."
            ),
        ),
        (
            "Tunnelling Horrors",
            (
                "At the end of your opponent's turn, if this unit is not within Engagement Range of one or more enemy "
                "units, you can remove this unit from the battlefield. In the Reinforcements step of your next Movement "
                "phase, set it up anywhere on the battlefield that is more than 9\" horizontally away from all enemy models."
            ),
        ),
        (
            "Translocation Beams",
            (
                "At the end of the Fight phase, if there are no models currently embarked within this TRANSPORT, you can "
                "select one friendly Necrons Infantry unit wholly within 6\" of this TRANSPORT. Unless that unit is within "
                "Engagement Range of one or more enemy units, it can embark within this TRANSPORT."
            ),
        ),
        (
            "Systematic Vigour",
            (
                "Each time a CRYPTOTHRALL model in this unit is destroyed by a melee attack, if that model has not fought "
                "this phase, roll one D6: on a 2+, do not remove it from play. The destroyed model can fight after the "
                "attacking model's unit has finished making its attacks, and it is then removed from play."
            ),
        ),
        (
            "Implacable Resilience",
            "Each time an attack is allocated to this model, subtract 1 from that attack's Damage characteristic.",
        ),
        (
            "Nebuloscope",
            "Ranged weapons equipped by the bearer have the [IGNORES COVER] ability.",
        ),
    ],
)
def test_support_matrix_necrons_group2_datasheet_abilities_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    status, _notes = gsm._classify_ability(name, description, faction_id="NEC")
    assert status == "Supported"
