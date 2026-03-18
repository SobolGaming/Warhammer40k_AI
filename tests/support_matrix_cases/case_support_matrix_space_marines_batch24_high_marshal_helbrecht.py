from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch24_high_marshal_helbrecht_crusade_of_wrath_support_matrix_case():
    status, notes = _classify_ability(
        "Crusade of Wrath",
        "While this model is leading a unit, add 1 to the Attacks and Strength characteristics of melee weapons equipped by models in that unit.",
        faction_id="SM",
        datasheet_id="000002794",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "leading" in notes_l
    assert "+1 attacks" in notes_l or "+1 attack" in notes_l
    assert "+1 strength" in notes_l


def test_space_marines_batch24_high_marshal_helbrecht_high_marshal_support_matrix_case():
    status, notes = _classify_ability(
        "High Marshal",
        "At the start of the Fight phase, select one enemy unit within Engagement Range of this model’s unit and roll one D6, adding 1 to the result for every five models in this model’s unit: on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; on a 6+, that enemy unit suffers D3+3 mortal wounds.",
        faction_id="SM",
        datasheet_id="000002794",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "start of fight phase" in notes_l
    assert "engagement range" in notes_l
    assert "+1 per 5 models" in notes_l or "+1 per 5" in notes_l
    assert "d3+3" in notes_l
