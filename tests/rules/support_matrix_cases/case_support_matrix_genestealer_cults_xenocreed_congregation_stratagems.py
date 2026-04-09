import os


def test_genestealer_cults_xenocreed_congregation_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000009072002": "re-roll the hit roll",
        "000009072003": "attacks and weapon skill",
        "000009072004": "charge after advancing or falling back",
        "000009072005": "[assault]",
        "000009072006": "without a marker more than 6",
        "000009072007": "surge move of up to d6",
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
