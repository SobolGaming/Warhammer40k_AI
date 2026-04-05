from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch17_pedro_predator_ragnar_support_matrix_cases():
    oath_status, oath_notes = _classify_ability(
        "Oath of Rynn",
        "Once per battle, at the start of either player's Command phase, this model can use this ability. When it does, until the end of the turn, add 1 to the Attacks characteristic of weapons equipped by models in this model's unit.",
        faction_id="SM",
        datasheet_id="000002713",
    )
    assert oath_status == "Supported"
    lowered_oath = str(oath_notes or "").lower()
    assert "either player" in lowered_oath
    assert "+1 attacks" in lowered_oath or "+1 attack" in lowered_oath

    destructor_status, destructor_notes = _classify_ability(
        "Destructor",
        "Each time this model makes a ranged attack that targets an INFANTRY unit, improve the Armour Penetration characteristic of that attack by 1.",
        faction_id="SM",
        datasheet_id="000002715",
    )
    assert destructor_status == "Supported"
    lowered_destructor = str(destructor_notes or "").lower()
    assert "infantry" in lowered_destructor
    assert "ap" in lowered_destructor or "armour penetration" in lowered_destructor

    war_howl_status, war_howl_notes = _classify_ability(
        "War Howl",
        "While this model is leading a Blood Claws unit, each time a model in that unit makes a melee attack, you can re-roll the Wound roll. While this model is leading a Wolf Guard Headtakers unit, that unit is eligible to declare a charge in a turn in which it Advanced.",
        faction_id="SM",
        datasheet_id="000000285",
    )
    assert war_howl_status == "Supported"
    lowered_war_howl = str(war_howl_notes or "").lower()
    assert "blood claws" in lowered_war_howl
    assert "headtakers" in lowered_war_howl

    battle_lust_status, battle_lust_notes = _classify_ability(
        "Battle-lust",
        "Each time this model ends a Charge move, until the end of the turn, add 2 to the Attacks characteristic of this model's Frostfang weapon.",
        faction_id="SM",
        datasheet_id="000000285",
    )
    assert battle_lust_status == "Supported"
    lowered_battle_lust = str(battle_lust_notes or "").lower()
    assert "frostfang" in lowered_battle_lust
    assert "+2" in lowered_battle_lust
