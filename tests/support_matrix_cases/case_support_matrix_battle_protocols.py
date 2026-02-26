def test_support_matrix_classifies_battle_protocols_as_supported():
    from scripts.generate_ability_support_matrix import _classify_ability

    ability_name = "Battle Protocols"
    description = (
        "At the start of the battle, if this model is leading a KASTELAN ROBOTS unit, that unit enters Aegis Protocols "
        "(see below). In your Command phase, if this model is leading a KASTELAN ROBOTS unit, you can select one protocol "
        "from those listed below for that unit to enter. Once a unit enters a protocol, it remains in that protocol until it "
        "enters a different one. "
        "- Protector Protocol: Add 2 to the Attacks characteristic of ranged weapons equipped by KASTELAN ROBOT models in that unit. "
        "- Conqueror Protocol: Add 2 to the Attacks characteristic of melee weapons equipped by KASTELAN ROBOT models in that unit. "
        "- Aegis Protocol: Add 1 to the Toughness characteristic of KASTELAN ROBOT models in that unit."
    )

    status, note = _classify_ability(ability_name, description, faction_id="ADM")

    assert status == "Supported"
    assert "Aegis Protocol" in note
