import os


def test_saga_of_the_bold_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010266002": "lethal hits",
        "000010266003": "re-roll hit rolls",
        "000010266004": "character keyword",
        "000010266005": "charge after advancing",
        "000010266006": "reduces incoming damage",
        "000010266007": "charge bonus",
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
