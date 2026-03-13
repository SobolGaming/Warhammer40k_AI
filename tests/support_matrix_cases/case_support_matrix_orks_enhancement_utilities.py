from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _enhancement_description(name: str) -> str:
    enhancement = _WAHA.get_enhancement_by_name(name)
    assert enhancement is not None, name
    return str(getattr(enhancement, "description", "") or "")


def test_support_matrix_classifies_da_kaptin_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._enhancement_support(
        "Da Kaptin",
        "000010712002",
        _enhancement_description("Da Kaptin"),
    )

    assert status == "Supported"
    notes_l = notes.lower()
    assert "battle-shock" in notes_l or "battle shock" in notes_l
    assert "mortal" in notes_l


def test_support_matrix_classifies_bionik_workshop_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._enhancement_support(
        "Bionik Workshop",
        "000010712004",
        _enhancement_description("Bionik Workshop"),
    )

    assert status == "Supported"
    notes_l = notes.lower()
    assert "start of battle" in notes_l
    assert "bionik" in notes_l


def test_support_matrix_classifies_supa_glowy_fing_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._enhancement_support(
        "Supa-glowy Fing",
        "000008877005",
        _enhancement_description("Supa-glowy Fing"),
    )

    assert status == "Supported"
    notes_l = notes.lower()
    assert "visible" in notes_l
    assert "mortal" in notes_l
    assert "hit" in notes_l
