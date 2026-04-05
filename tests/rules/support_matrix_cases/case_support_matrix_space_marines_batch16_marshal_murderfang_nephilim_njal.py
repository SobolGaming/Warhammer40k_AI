from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch16_marshal_murderfang_nephilim_njal_support_matrix_cases():
    pious_status, pious_notes = _classify_ability(
        "Pious Fervour",
        "Each time this model's unit is selected to fight, until the end of the phase, add 1 to the Attacks characteristic of this model's master-crafted power weapon for each enemy unit within 6\" of this model (to a maximum of +3).",
        faction_id="SM",
        datasheet_id="000002796",
    )
    assert pious_status == "Supported"
    lowered_pious = str(pious_notes).lower()
    assert "master-crafted power weapon" in lowered_pious
    assert "+3" in lowered_pious

    murder_status, murder_notes = _classify_ability(
        "Murder-maker (Aura)",
        "In the Fight phase, each time an attack targets a friendly Wulfen unit within 6\" of this model, if a model in that unit is destroyed as a result of that attack, if that model has not fought this phase, roll one D6: on a 4+, do not remove the destroyed model from play; it can fight after the attacking unit has finished making its attacks, and is then removed from play.",
        faction_id="SM",
        datasheet_id="000000314",
    )
    assert murder_status == "Supported"
    lowered_murder = str(murder_notes).lower()
    assert "wulfen" in lowered_murder
    assert "fight-on-death" in lowered_murder or "fight on death" in lowered_murder

    nephilim_status, nephilim_notes = _classify_ability(
        "Lightning-fast Manoeuvres",
        "Each time a ranged attack targets this model, subtract 1 from the Hit roll. If that attack was made by a model that can Fly, subtract 1 from the Wound roll as well.",
        faction_id="SM",
        datasheet_id="000000239",
    )
    assert nephilim_status == "Supported"
    lowered_nephilim = str(nephilim_notes).lower()
    assert "fly" in lowered_nephilim
    assert "wound" in lowered_nephilim

    tempest_status, tempest_notes = _classify_ability(
        "Tempest's Wrath (Psychic)",
        "In your Shooting phase, after this model's unit has shot, select one enemy unit (excluding MONSTERS and VEHICLES) hit by one or more of those attacks made with this model's Living Lightning weapon. Until the start of your next turn, that enemy unit is stormwracked. While a unit is stormwracked, subtract 6\" from the Range characteristic of ranged weapons equipped by models in that unit (to a minimum of 12\").",
        faction_id="SM",
        datasheet_id="000000292",
    )
    assert tempest_status == "Supported"
    lowered_tempest = str(tempest_notes).lower()
    assert "living lightning" in lowered_tempest
    assert "stormwracked" in lowered_tempest
