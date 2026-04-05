import os


def test_ordo_malleus_gift_of_the_prescient_enhancement_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    row = next(
        item
        for item in enhancements
        if str(item.get("id", "") or "").strip() == "000009134004"
    )

    status, notes = gsm._enhancement_support(
        str(row.get("name", "") or ""),
        "000009134004",
        str(row.get("description", "") or ""),
    )
    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "gift of the prescient" in notes_l
    assert "rapid ingress" in notes_l
