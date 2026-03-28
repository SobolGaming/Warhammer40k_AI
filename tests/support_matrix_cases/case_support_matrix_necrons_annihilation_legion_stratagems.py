import os


def test_support_matrix_marks_annihilation_legion_stratagems_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected_ids = {
        "000008405003",
        "000008405004",
        "000008405005",
        "000008405006",
        "000008405007",
    }

    for stratagem_id in expected_ids:
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
        assert "implemented" in str(notes or "").lower()
