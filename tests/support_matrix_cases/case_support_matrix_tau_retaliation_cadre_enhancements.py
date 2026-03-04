import os


def test_tau_retaliation_cadre_starflare_is_supported():
    import scripts.generate_ability_support_matrix as gsm

    enhancements = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Enhancements.json"))
    enhancement_id = "000008815005"
    enhancement_name = "Starflare Ignition System"

    row = next(
        item
        for item in enhancements
        if str(item.get("id", "") or "").strip() == enhancement_id
        and str(item.get("name", "") or "").strip().replace("\u2019", "'") == enhancement_name
    )
    status, notes = gsm._enhancement_support(
        enhancement_name,
        enhancement_id,
        str(row.get("description", "") or ""),
    )
    assert status == "Supported"
    assert "starflare" in str(notes or "").lower()
