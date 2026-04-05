from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch22_ulrik_the_slayer_oathbound_support_matrix_case():
    description = (
        "While this model is leading a unit, each time a model in that unit makes a melee attack, add 1 to the Hit roll. "
        "If that attack targets a unit that has this model's Slayer's Oath keyword (see above), add 1 to the Wound roll as well."
    )

    status, notes = _classify_ability(
        "Oathbound",
        description,
        faction_id="SM",
        datasheet_id="000000297",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "leading" in notes_l
    assert "+1" in notes_l
    assert "hit" in notes_l
    assert "wound" in notes_l
    assert "selected keyword" in notes_l


def test_space_marines_batch22_ulrik_the_slayer_slayers_oath_support_matrix_case():
    description = (
        "At the start of the battle, select one of the following keywords to be this model's Slayer's Oath: "
        "CHARACTER; MONSTER; VEHICLE. The first time this model's unit destroys a unit with this model's "
        "Slayer's Oath keyword, if your Detachment rule has a Saga, until the end of the battle, this model's "
        "unit receives the benefits of that Detachment rule as if that Saga had been completed."
    )

    status, notes = _classify_ability(
        "Slayer's Oath",
        description,
        faction_id="SM",
        datasheet_id="000000297",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "start of battle" in notes_l
    assert "character" in notes_l
    assert "monster" in notes_l
    assert "vehicle" in notes_l
    assert "saga" in notes_l
