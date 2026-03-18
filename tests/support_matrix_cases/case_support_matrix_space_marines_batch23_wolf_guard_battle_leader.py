from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_wolf_guard_battle_leader_tempered_ferocity_support_matrix_case():
    description = (
        "While this model is leading a unit, weapons equipped by models in that unit have the [SUSTAINED HITS 1] "
        "ability and, each time a model in that unit makes an attack that targets an enemy unit within 6\", "
        "re-roll a Hit roll of 1."
    )

    status, notes = _classify_ability(
        "Tempered Ferocity",
        description,
        faction_id="SM",
        datasheet_id="000004130",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "sustained hits 1" in notes_l
    assert "within 6" in notes_l
    assert "re-roll hit rolls of 1" in notes_l
