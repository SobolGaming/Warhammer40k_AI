import os


def test_tyranids_synaptic_nexus_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "000008556002": "6d6",
        "000008556003": "within 9\"",
        "000008556004": "re-roll hit and wound rolls of 1",
        "000008556005": "worsens incoming ap by 1",
        "000008556006": "choose_quarry",
        "000008556007": "shoot and declare a charge",
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
