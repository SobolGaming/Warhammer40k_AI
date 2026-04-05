import os


def test_tyranids_unending_swarm_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "000008409002": "re-roll the d6 distance",
        "000008409003": "replacement unit",
        "000008409004": "-1 to hit",
        "000008409005": "sustained hits 1",
        "000008409006": "fixed +6",
        "000008409007": "fewer than five models",
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
