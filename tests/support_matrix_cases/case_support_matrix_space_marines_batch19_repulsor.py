from scripts import generate_ability_support_matrix as gsm


def test_repulsor_emergency_combat_embarkation_support_matrix_case() -> None:
    description = (
        "Once per turn, in your opponent's Charge phase, after an enemy unit has selected targets for its charge "
        "but before it makes a Charge move, you can select one ADEPTUS ASTARTES unit from your army that was "
        "selected as a target of that charge. Provided that unit is not within Engagement Range of one or more "
        'enemy units and every model in that unit is within 3" of this TRANSPORT, it can embark within this '
        "TRANSPORT. The charging unit can then select new targets for its charge."
    )

    status, notes = gsm._classify_ability("Emergency Combat Embarkation", description, faction_id="SM")

    assert status == "Supported"
    assert "reselects charge targets" in str(notes or "")
    assert "charge is cancelled" in str(notes or "")


def test_repulsor_stabilised_disembarkation_support_matrix_case() -> None:
    description = (
        "In your opponent's Shooting phase, each time an enemy unit is selected to shoot, after that unit has shot, "
        "if any of those attacks targeted this TRANSPORT, it can use this ability. If it does, any units embarked "
        'within it can disembark. When doing so, models in those units can be set up anywhere on the battlefield '
        'wholly within 6" of this TRANSPORT and not within Engagement Range of one or more enemy units.'
    )

    status, notes = gsm._classify_ability("Stabilised Disembarkation", description, faction_id="SM")

    assert status == "Supported"
    assert "targeted this transport" in str(notes or "").lower()
    assert 'wholly within 6"' in str(notes or "")
