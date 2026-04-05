import os


def test_tyranids_subterranean_assault_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "000010148002": "synapse keyword",
        "000010148003": "tunnel markers",
        "000010148004": "sustained hits 1",
        "000010148005": "another tunnel marker",
        "000010148006": "re-roll charge rolls",
        "000010148007": "strategic reserves",
    }
    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    for stratagem_id, note_fragment in expected.items():
        row = next(
            item
            for item in stratagems
            if str(item.get("id", "") or "").strip() == stratagem_id
        )
        status, notes, _ = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            detachment_name=str(row.get("detachment", "") or ""),
            stratagem_id=stratagem_id,
        )
        assert status == "Implemented"
        assert note_fragment.lower() in str(notes or "").lower()
