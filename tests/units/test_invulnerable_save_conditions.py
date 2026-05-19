from warhammer40k_ai.units.invulnerable_save_conditions import resolve_invulnerable_save
from warhammer40k_ai.units.wargear import Wargear


def _profile(kind: str):
    wargear = Wargear(
        {
            "name": f"{kind} test weapon",
            "type": kind,
            "range": "Melee" if kind == "Melee" else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return wargear.profiles["default"]


def test_model_named_only_invulnerable_save_applies_only_to_named_model(caplog):
    assert (
        resolve_invulnerable_save(
            model_name="Ibram Gaunt",
            base_invulnerable_save=5,
            condition="Ibram Gaunt only.",
            attack_instance={},
        )
        == 5
    )
    assert (
        resolve_invulnerable_save(
            model_name="Tanith Ghost",
            base_invulnerable_save=5,
            condition="Ibram Gaunt only.",
            attack_instance={},
        )
        is None
    )
    assert "Unknown invulnerable save condition" not in caplog.text


def test_excluding_model_invulnerable_save_denies_excluded_model():
    assert (
        resolve_invulnerable_save(
            model_name="Subductor",
            base_invulnerable_save=4,
            condition="*Excluding the Cyber-mastiff.",
            attack_instance={},
        )
        == 4
    )
    assert (
        resolve_invulnerable_save(
            model_name="Cyber-mastiff",
            base_invulnerable_save=4,
            condition="*Excluding the Cyber-mastiff.",
            attack_instance={},
        )
        is None
    )


def test_improved_against_attack_condition_keeps_base_save_for_other_attacks():
    melee = _profile("Melee")
    ranged = _profile("Ranged")
    condition = "This invulnerable save is improved to 4+ against melee attacks."

    assert (
        resolve_invulnerable_save(
            model_name="Howling Banshee",
            base_invulnerable_save=5,
            condition=condition,
            attack_instance={"weapon_profile": melee},
        )
        == 4
    )
    assert (
        resolve_invulnerable_save(
            model_name="Howling Banshee",
            base_invulnerable_save=5,
            condition=condition,
            attack_instance={"weapon_profile": ranged},
        )
        == 5
    )


def test_attack_only_condition_does_not_apply_to_other_attack_types():
    melee = _profile("Melee")
    ranged = _profile("Ranged")
    condition = "This model has a 5+ invulnerable save against ranged attacks."

    assert (
        resolve_invulnerable_save(
            model_name="Illic Nightspear",
            base_invulnerable_save=5,
            condition=condition,
            attack_instance={"weapon_profile": ranged},
        )
        == 5
    )
    assert (
        resolve_invulnerable_save(
            model_name="Illic Nightspear",
            base_invulnerable_save=5,
            condition=condition,
            attack_instance={"weapon_profile": melee},
        )
        is None
    )
