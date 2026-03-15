import os


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_grenadiers_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Grenadiers",
        "Once per turn, you can target this unit with the Grenade Stratagem for 0CP.",
        ability_id="",
        faction_id="AM",
        datasheet_id="krieg-combat-engineers",
    )
    assert status == "Supported"
    assert "Grenade" in str(notes or "")
    assert "0CP" in str(notes or "")


def test_remote_mine_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Remote Mine",
        (
            "Once per battle, at the start of your Shooting phase, you can select one enemy unit within 9\" of and "
            "visible to the bearer and roll one D6: on a 3+, that enemy unit suffers D3 mortal wounds, or 2D3 "
            "mortal wounds instead if it is a VEHICLE or FORTIFICATIONS unit. Designer's Note: Place a Remote "
            "Mine token next to the unit, removing it once this ability has been used."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="krieg-combat-engineers",
    )
    assert status == "Supported"
    assert "9" in str(notes or "")
    assert "2D3" in str(notes or "")
    assert "FORTIFICATIONS" in str(notes or "")


def test_grim_determination_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Grim Determination",
        (
            "While this unit contains an OFFICER, you can target this unit with Stratagems even while it is "
            "Battle-shocked and Orders issued to this unit do not cease to affect this unit if it becomes "
            "Battle-shocked."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="krieg-command-squad",
    )
    assert status == "Supported"
    assert "Battle-shocked" in str(notes or "")
    assert "Orders" in str(notes or "")


def test_servo_scribes_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Servo-scribes",
        (
            "Once per battle, when issuing an Order, the Lord Commissar can issue one additional Order. "
            "Designer's Note: Place a Servo-scribes token next to the unit, removing it when this ability has "
            "been used."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="krieg-command-squad",
    )
    assert status == "Supported"
    assert "additional Order" in str(notes or "")


def test_final_duty_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Final Duty",
        (
            "While the Fire Coordinator model is on the battlefield, each time a Heavy Weapons Gunner model is "
            "destroyed, roll one D6: on a 3+, do not remove it from play. The destroyed model can shoot after the "
            "attacking model's unit has finished making its attacks, and is then removed from play."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="krieg-heavy-weapons-squad",
    )
    assert status == "Supported"
    assert "FIRE COORDINATOR" in str(notes or "")
    assert "HEAVY WEAPONS GUNNER" in str(notes or "")


def test_death_befitting_an_officer_support_matrix_classifies_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Death Befitting An Officer",
        (
            "When this model is destroyed, roll one D6: on a 2+, do not remove it from play - it can, after the "
            "attacking model's unit has finished making its attacks, shoot as if it were your Shooting phase and as "
            "if it had its full wounds remaining. This model is then removed from play."
        ),
        ability_id="",
        faction_id="AM",
        datasheet_id="leman-russ-commander",
    )
    assert status == "Supported"
    assert "2+" in str(notes or "")
    assert "full wounds remaining" in str(notes or "").lower()
