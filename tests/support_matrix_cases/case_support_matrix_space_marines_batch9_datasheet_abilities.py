import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Terminatus Assault",
            "You can re-roll Charge rolls made for this unit. Each time this unit ends a Charge move, each enemy unit within Engagement Range of this unit must take a Battle-shock test. If that enemy unit does not have the IMPERIUM or CHAOS keywords, subtract 1 from that test.",
            "targets without imperium/chaos",
        ),
        (
            "Wisdom of the Ancients (Aura)",
            'While a friendly Adeptus Astartes Infantry unit is within 6" of this model, each time a model in that unit makes an attack, re-roll a Hit roll of 1.',
            "re-roll hit rolls of 1 for attacks",
        ),
        (
            "Reposition Under Covering Fire",
            "In your Shooting phase, after this unit has shot, if it contains an Eliminator Sergeant equipped with an instigator bolt carbine, this unit can make a Normal move. If it does so, until the end of the turn, this unit is not eligible to declare a charge.",
            "instigator bolt carbine",
        ),
        (
            "Armour of Faith",
            "Once per phase, when an attack is allocated to this model and the saving throw is failed, you can change the Damage characteristic of that attack to 0.",
            "once per phase",
        ),
        (
            "Sigismund's Heir",
            "Each time this model's unit declares a charge, if one or more targets of that charge have the CHARACTER keyword, add 2 to the Charge roll. Once per battle, when this model's unit is selected to fight, if that unit is within Engagement Range of one or more enemy CHARACTER units, this model can use this ability. If it does, until the end of the phase, melee weapons equipped by this model have the [DEVASTATING WOUNDS] ability.",
            "devastating wounds",
        ),
        (
            "Total Obliteration",
            "Each time a ranged attack made by a model in this unit targets a MONSTER or VEHICLE model, you can re-roll the Hit roll, you can re-roll the Wound roll and you can re-roll the Damage roll.",
            "damage roll",
        ),
    ],
)
def test_space_marines_batch9_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="SM")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
