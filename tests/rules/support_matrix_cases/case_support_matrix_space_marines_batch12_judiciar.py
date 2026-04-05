from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch12_judiciar_support_matrix_case():
    status, notes = _classify_ability(
        "Silent Fury",
        "Each time this model destroys an enemy CHARACTER model, until the end of the battle, add 1 to the Attacks characteristic of its executioner relic blade.",
        faction_id="SM",
    )
    assert status == "Supported"
    assert "executioner relic blade" in str(notes).lower()
