import os

from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor


def test_support_matrix_classifies_requested_space_marines_abilities_as_supported():
    import scripts.generate_ability_support_matrix as gsm

    gsm._seed_ability_support_maps([], [])

    expected = {
        "Hailstrike": (
            "Each time this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) hit by one or more of those attacks. "
            "Until the end of the phase, each time a friendly ADEPTUS ASTARTES unit makes a ranged attack that targets that enemy unit, "
            "improve the Armour Penetration characteristic of that attack by 1. The same enemy unit can only be affected by this ability once per phase.",
            "after shooting",
        ),
        "Close-quarters Firepower": (
            "Each time a model in this unit makes a ranged attack that targets the closest eligible target, "
            "improve the Armour Penetration characteristic of that attack by 1.",
            "closest eligible target",
        ),
        "Destructor": (
            "Each time a ranged attack made by this model targets an enemy INFANTRY unit, "
            "improve the Armour Penetration characteristic of that attack by 1.",
            "against infantry units",
        ),
    }

    for name, (description, note_anchor) in expected.items():
        status, notes = gsm._classify_ability(name, description, faction_id="SM")
        assert status == "Supported"
        assert str(note_anchor).lower() in str(notes or "").lower()


def test_support_matrix_marks_requested_stratagems_implemented():
    import scripts.generate_ability_support_matrix as gsm

    stratagems = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Stratagems.json"))
    expected = {
        "000010397003": "objective range",
        "000008443002": "objective",
        "000008443003": "within 9",
        "000008443004": "spotted unit",
        "000008443005": "embarkation",
        "000008443006": "charge rolls",
        "000008822002": "starting strength",
        "000008822003": "battle-shocked",
        "000008822004": "ballistic skill",
        "000008822005": "battle-shock tests",
        "000008822006": "shoot and declare a charge",
        "000008822007": "within 18",
        "000010507006": "worsens ap by 1",
        "000010507003": "bonded armiger",
    }

    for stratagem_id, note_anchor in expected.items():
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
        assert str(note_anchor).lower() in str(notes or "").lower()


def test_requested_stratagem_descriptors_registered():
    expected = {
        "000010397003": ("Litanies of Purgation", "conditional_melee_ap_bonus_if_attacker_or_target_within_objective_range"),
        "000008443002": ("A Tempting Trap", "conditional_ranged_wound_bonus_vs_selected_trap_objective"),
        "000008443003": ("Point-Blank Ambush", "conditional_ranged_ap_bonus_within_range"),
        "000008443004": ("Coordinate to Engage", "observer_ballistic_skill_bonus_vs_spotted_unit"),
        "000008443005": ("Combat Embarkation", "reactive_embark_and_charge_retarget"),
        "000008443006": ("Photon Grenades", "force_battleshock_and_charge_penalty"),
        "000008822002": ("Join the Hunt", "clone_unit_to_strategic_reserves"),
        "000008822003": ("A Trap Well Laid", "conditional_kroot_ap_bonus_vs_selected_hit_enemy_unless_battleshocked"),
        "000008822004": ("Emp Grenades", "enemy_vehicle_ws_bs_penalty"),
        "000008822005": ("The Grisly Feast", "battle_shock_enemies_within_range_in_next_opponent_command_phase"),
        "000008822006": ("Guerrilla Warriors", "shoot_and_charge_after_fall_back"),
        "000008822007": ("Hidden Hunters", "ranged_targeting_range_restriction"),
        "000010507006": ("Let Duty Be Your Shield", "worsen_incoming_ap"),
        "000010507003": ("Exemplar's Wisdom", "selected_bondsman_armigers_gain_ap_against_selected_hit_enemy"),
    }

    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.effect == effect
        assert by_name.effect == effect
