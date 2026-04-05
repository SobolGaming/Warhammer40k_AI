import os


def test_support_matrix_marks_awakened_dynasty_stratagems_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected_ids = {
        "000008371002",
        "000008371003",
        "000008371004",
        "000008371005",
        "000008371006",
        "000008371007",
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
        assert str(notes or "").strip()
