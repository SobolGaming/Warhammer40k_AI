from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch23_wolf_guard_headtakers_let_loose_the_wolves_support_matrix_case():
    description = (
        "At the start of the Declare Battle Formations step, split this unit into two units, one containing all "
        "of its HEADTAKERS models and one containing all of its HUNTING WOLVES models, with new Starting "
        "Strengths accordingly."
    )

    status, notes = _classify_ability(
        "Let Loose the Wolves",
        description,
        faction_id="SM",
        datasheet_id="000004131",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "declare battle formations" in notes_l
    assert "headtakers" in notes_l
    assert "hunting wolves" in notes_l


def test_space_marines_batch23_wolf_guard_headtakers_headhunters_support_matrix_case():
    description = (
        "At the start of the battle, select one unit from your opponent's army to be this unit's quarry. "
        "Weapons equipped by HEADTAKERS models in this unit have the [DEVASTATING WOUNDS] and [PRECISION] "
        "abilities while targeting its quarry. Each time this unit's quarry is destroyed, select one new enemy "
        "unit to be this unit's quarry. This ability can be used even if this unit is embarked within a Transport."
    )

    status, notes = _classify_ability(
        "Headhunters",
        description,
        faction_id="SM",
        datasheet_id="000004131",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "let loose the wolves split" in notes_l
    assert "devastating wounds" in notes_l
    assert "precision" in notes_l
    assert "while embarked" in notes_l
