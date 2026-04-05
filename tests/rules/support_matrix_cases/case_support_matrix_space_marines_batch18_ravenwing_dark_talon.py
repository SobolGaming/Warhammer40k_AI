from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch18_ravenwing_dark_talon_support_matrix_cases():
    status, notes = _classify_ability(
        "Stasis Bomb",
        "Once per turn, one model from your army with this ability can use it after it ends a Normal move. If it does, you can select one enemy unit (excluding AIRCRAFT) that model moved over this phase. That unit suffers D3 mortal wounds and you must roll one D6: on a 1-3, that unit cannot Advance or Fall Back in your opponent's next Movement phase; on a 4-6, that unit must Remain Stationary in your opponent's next Movement phase. Each model can only use this ability once per battle.",
        faction_id="SM",
        datasheet_id="000000240",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "moved-over" in lowered or "moved over" in lowered
    assert "remain stationary" in lowered
    assert "advance" in lowered and "fall back" in lowered
