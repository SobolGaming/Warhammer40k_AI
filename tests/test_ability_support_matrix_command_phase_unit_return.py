from __future__ import annotations


def test_support_matrix_classifies_narthecium_style_return_to_bearers_unit_as_supported():
    import scripts.generate_ability_support_matrix as support_matrix

    status, notes = support_matrix._classify_ability(
        "Narthecium",
        "In your Command phase, you can return 1 destroyed model (excluding CHARACTERS ) to the bearer\u2019s unit.",
        faction_id="AGI",
    )
    assert status == "Supported"
    assert "return 1 destroyed model(s)" in str(notes or "").lower()
    assert "excludes character" in str(notes or "").lower()


def test_support_matrix_classifies_healing_serum_style_below_starting_strength_return_as_supported():
    import scripts.generate_ability_support_matrix as support_matrix

    status, notes = support_matrix._classify_ability(
        "Healing Serum",
        (
            "At the start of your Command phase, if the bearer\u2019s unit is below its Starting Strength, "
            "you can return up to D3 destroyed models (excluding CHARACTERS) to the bearer\u2019s unit."
        ),
        faction_id="AGI",
    )
    assert status == "Supported"
    note_l = str(notes or "").lower()
    assert "return up to d3 destroyed model(s)" in note_l
    assert "below starting strength" in note_l


def test_support_matrix_classifies_grot_orderly_bodyguard_return_as_supported():
    import scripts.generate_ability_support_matrix as support_matrix

    status, notes = support_matrix._classify_ability(
        "Grot Orderly",
        (
            "Once per battle, in your Command phase, if the bearer is leading a unit that is below its Starting "
            "Strength, you can return up to D3 destroyed Bodyguard models to that unit."
        ),
        faction_id="ORK",
    )
    assert status == "Supported"
    note_l = str(notes or "").lower()
    assert "return up to d3 destroyed bodyguard model(s)" in note_l
    assert "below starting strength" in note_l
    assert "once per battle" in note_l
