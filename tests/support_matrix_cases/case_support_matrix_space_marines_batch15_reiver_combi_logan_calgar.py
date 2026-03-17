from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch15_reiver_combi_logan_calgar_support_matrix_cases():
    deadly_status, deadly_notes = _classify_ability(
        "Deadly Terror",
        "While this model is leading a unit, increase the range of that unit's Terror Troops ability by 3\".",
        faction_id="SM",
        datasheet_id="000001345",
    )
    assert deadly_status == "Supported"
    assert "terror troops" in str(deadly_notes).lower()

    evade_status, evade_notes = _classify_ability(
        "Evade and Survive",
        "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit, if this unit is not within Engagement Range of one or more enemy units, it can make a Normal move.",
        faction_id="SM",
        datasheet_id="000000076",
    )
    assert evade_status == "Supported"
    assert "move characteristic" in str(evade_notes).lower()

    priority_status, priority_notes = _classify_ability(
        "Priority Objective Identified",
        "At the start of the first battle round, if your army includes one or more models with this ability, you can select one objective marker on the battlefield. Until the end of the battle, while one or more models with this ability are on the battlefield, each time a friendly ADEPTUS ASTARTES model makes an attack that targets an enemy unit that is within range of that objective marker, re-roll a Wound roll of 1.",
        faction_id="SM",
        datasheet_id="000000076",
    )
    assert priority_status == "Supported"
    lowered_priority = str(priority_notes).lower()
    assert "objective" in lowered_priority
    assert "wound" in lowered_priority

    high_king_status, high_king_notes = _classify_ability(
        "High King of Fenris",
        "Once per battle round, in your Movement phase, you can select one friendly Space Wolves unit that is in Reserves. If you do, until the end of the phase, for the purpose of setting up that unit on the battlefield, treat the current battle round number as being one higher than it actually is.",
        faction_id="SM",
        datasheet_id="000000282",
    )
    assert high_king_status == "Supported"
    lowered_high_king = str(high_king_notes).lower()
    assert "space wolves" in lowered_high_king
    assert "+1" in lowered_high_king

    master_status, master_notes = _classify_ability(
        "Master Tactician",
        "At the start of your Command phase, if this unit's Marneus Calgar model is your WARLORD and is on the battlefield, you gain 1CP.",
        faction_id="SM",
        datasheet_id="000002199",
    )
    assert master_status == "Supported"
    lowered_master = str(master_notes).lower()
    assert "warlord" in lowered_master
    assert "1 cp" in lowered_master

    inspiring_status, inspiring_notes = _classify_ability(
        "Inspiring Leader",
        "While this unit is leading a unit and contains a MARNEUS CALGAR model, that unit is eligible to shoot and declare a charge in a turn in which it Advanced or Fell Back.",
        faction_id="SM",
        datasheet_id="000002199",
    )
    assert inspiring_status == "Supported"
    lowered_inspiring = str(inspiring_notes).lower()
    assert "advance" in lowered_inspiring
    assert "fall" in lowered_inspiring
