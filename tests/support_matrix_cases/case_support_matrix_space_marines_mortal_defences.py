import os

from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor


def test_support_matrix_classifies_space_marines_mortal_defence_abilities_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    gsm._seed_ability_support_maps([], [])

    expected = {
        "Unbreakable Duty": (
            "While this model is within range of an objective marker and/or within 6\" of the centre of the battlefield, this model has the Feel No Pain 4+ ability.",
            "battlefield centre",
        ),
        "Honour Guard of Macragge": (
            "While this unit contains one or more Victrix Honour Guard models, this unit's MARNEUS CALGAR model has the Feel No Pain 4+ ability.",
            "marneus calgar gains feel no pain 4+",
        ),
        "No Hiding From the Watchers (Aura)": (
            "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, models in that unit have the Feel No Pain 4+ ability against mortal wounds.",
            "against mortal wounds",
        ),
        "The Lion Helm": (
            "Models in the bearer's unit have a 4+ invulnerable save. In addition, once per battle, in any phase, the bearer can summon a Watcher in the Dark. When it does, until the end of the phase, models in the bearer's unit have the Feel No Pain 4+ ability against mortal wounds.",
            "watcher in the dark activation",
        ),
    }

    for name, (description, note_anchor) in expected.items():
        status, notes = gsm._classify_ability(name, description, faction_id="SM")
        assert status == "Supported"
        assert str(note_anchor).lower() in str(notes or "").lower()


def test_support_matrix_marks_space_marines_mortal_wound_stratagems_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000008375002": "feel no pain 5+ against mortal wounds",
        "000009844002": "feel no pain 5+ against mortal wounds",
    }

    for stratagem_id, note_anchor in expected.items():
        row = next(
            item
            for item in stratagems
            if str(item.get("id", "") or "").strip() == str(stratagem_id)
        )
        status, notes, _ = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            detachment_name=str(row.get("detachment", "") or ""),
            stratagem_id=str(stratagem_id),
        )
        assert status == "Implemented"
        assert str(note_anchor).lower() in str(notes or "").lower()


def test_space_marines_mortal_wound_stratagem_descriptors_registered_by_id_and_name():
    expected = {
        "000008375002": "Angelic Grace",
        "000009844002": "Fuelled by Faith",
    }

    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.effect == "feel_no_pain_vs_mortals"
        assert by_name.effect == "feel_no_pain_vs_mortals"
