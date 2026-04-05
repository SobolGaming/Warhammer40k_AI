import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Target Elimination",
            "Each time this unit is selected to shoot, it can use this ability. If it does, until the end of the phase, add 2 to the Attacks characteristic of bolt rifles equipped by models in this unit and you can only select one enemy unit as the target of all of this unit's attacks.",
            "bolt rifles",
        ),
        (
            "Outrider Escort",
            "Once per turn, in your opponent's Shooting phase, when another friendly ADEPTUS ASTARTES MOUNTED unit within 6\" of this model is selected as the target of an attack, one model from your army with this ability can use it. If it does, after that enemy unit has finished making its attacks, that model can shoot as if it were your Shooting phase, but when resolving those attacks it can only target that enemy unit (and only if it is an eligible target).",
            "reactive shooting attack",
        ),
        (
            "Combat Support",
            "Once per turn, in your opponent's Shooting phase, when a friendly Adeptus Astartes Phobos Infantry unit within 6\" of this model is selected as the target of an attack, one model from your army with this ability can use it. If it does, after that enemy unit has finished making its attacks, that model can shoot as if it were your Shooting phase, but when resolving those attacks it can only target that enemy unit (and only if it is an eligible target).",
            "reactive shooting attack",
        ),
        (
            "Master of the Forge",
            "In your Command phase, select one friendly ADEPTUS ASTARTES VEHICLE model within 3\" of this model. That model regains up to 3 lost wounds and, until the start of your next Command phase, each time that VEHICLE model makes an attack, add 1 to the Hit roll. You cannot select a unit for this ability that has already been selected for the Blessing of the Omnissiah ability this phase, and vice versa.",
            "regain 3 wounds",
        ),
    ],
)
def test_space_marines_batch11_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="SM")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
