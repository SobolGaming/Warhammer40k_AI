import os

import pytest


@pytest.mark.parametrize(
    ("stratagem_id", "phrase"),
    [
        ("000008418002", "battle-shock"),
        ("000008418003", "precision"),
        ("000008418004", "battle round as one higher"),
        ("000008418005", "reactive normal move"),
        ("000008418006", "within 18"),
        ("000008418007", "strategic reserves"),
    ],
)
def test_tyranids_vanguard_onslaught_stratagem_is_implemented(stratagem_id: str, phrase: str):
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
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
    assert str(phrase or "").lower() in str(notes or "").lower()
