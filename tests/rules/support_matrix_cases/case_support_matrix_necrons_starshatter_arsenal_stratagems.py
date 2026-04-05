import os


def test_necrons_starshatter_arsenal_stratagems_are_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000009750002": "+1 to wound vs targets within objective range",
        "000009750003": "-1 to wound if s>t",
        "000009750004": "advance roll as 6",
        "000009750005": "move through models/terrain",
        "000009750006": "reanimation protocols (d3)",
        "000009750007": "normal move (d6",
    }

    for stratagem_id, phrase in expected.items():
        row = next(
            item
            for item in stratagems
            if str(item.get("id", "") or "").strip() == stratagem_id
        )
        status, notes, _name = gsm._stratagem_support(
            str(row.get("name", "") or ""),
            str(row.get("description", "") or ""),
            stratagem_id=str(row.get("id", "") or ""),
        )
        assert status == "Implemented"
        assert phrase in str(notes or "").lower()
