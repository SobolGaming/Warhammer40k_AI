from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch13_legacy_of_jerulas_support_matrix_case():
    status, notes = _classify_ability(
        "Legacy of Jerulas",
        "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. Until the end of the turn, each time a friendly model that disembarked from this TRANSPORT this turn makes an attack that targets that enemy unit, re-roll a Hit roll of 1 and re-roll a Wound roll of 1.",
        faction_id="SM",
    )
    assert status == "Supported"
    assert "disembarked" in str(notes).lower()


def test_space_marines_batch13_storm_of_vengeance_support_matrix_case():
    status, notes = _classify_ability(
        "Storm of Vengeance",
        "Once per turn, in your opponent's Shooting phase, when a friendly ADEPTUS ASTARTES unit within 6\" of this model is destroyed, this model can use this ability. If it does, after the attacking unit has finished making its attacks, this model can shoot as if it were your Shooting phase, but when resolving those attacks it can only target that enemy unit (and only if it is an eligible target).",
        faction_id="SM",
    )
    assert status == "Supported"
    assert "reactive shooting" in str(notes).lower()


def test_space_marines_batch13_guardian_of_the_lost_support_matrix_case():
    status, notes = _classify_ability(
        "Guardian of the Lost",
        "While this model is leading a unit, each time an attack is allocated to a model in that unit, subtract 1 from the Damage characteristic of that attack.",
        faction_id="SM",
    )
    assert status == "Supported"
    assert "damage characteristic" in str(notes).lower()
