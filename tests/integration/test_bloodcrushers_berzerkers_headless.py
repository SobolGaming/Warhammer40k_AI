from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_PATH = ROOT / "scripts" / "bloodcrushers_vs_berzerkers_charge_fight.py"


def _scenario_module():
    spec = importlib.util.spec_from_file_location("bloodcrushers_vs_berzerkers_charge_fight", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_bloodcrushers_charge_fight_and_berzerkers_fight_back():
    scenario = _scenario_module()

    summary = scenario.run_scenario(seed=40, forced_charge_dice=[6, 6])

    assert summary["charge_move_engaged_before_damage_allocations"] is True
    assert summary["brass_stampede_mortal_wounds"] > 0
    assert summary["bloodcrushers_charged_this_round_at_fight_start"] is True
    assert summary["bloodcrushers_should_fight_first_at_fight_start"] is True
    assert summary["bloodcrushers_in_fight_first_units_at_fight_start"] is True
    assert summary["berzerkers_in_remaining_units_at_fight_start"] is True
    assert summary["bloodcrushers_fought_this_phase"] is True
    assert summary["berzerkers_fought_this_phase"] is True
    assert summary["bloodcrusher_melee_successful_attacks"] > 0
    assert summary["berzerker_melee_successful_attacks"] > 0
    assert [entry["unit_name"] for entry in summary["fight_unit_selections"]] == [
        "Bloodcrushers",
        "Khorne Berzerkers",
    ]
    assert [entry["phase_step"] for entry in summary["fight_unit_selections"]] == [
        "FIGHT_FIRST",
        "REMAINING_COMBATANTS",
    ]


@pytest.mark.integration
def test_charged_unit_outside_engagement_after_fights_first_does_not_fight_back():
    scenario = _scenario_module()

    summary = scenario.run_scenario(
        seed=40,
        forced_charge_dice=[6, 6],
        damage_allocation_mode="break_engagement",
        expect_berzerkers_fight_back=False,
    )

    after_fights_first = summary["after_bloodcrushers_fights_first"]
    assert summary["charge_move_engaged_before_damage_allocations"] is True
    assert summary["brass_stampede_mortal_wounds"] > 0
    assert summary["bloodcrushers_fought_this_phase"] is True
    assert after_fights_first["bloodcrushers_engaged_with_berzerkers"] is False
    assert after_fights_first["berzerkers_eligible_to_fight"] is False
    assert summary["berzerkers_fought_this_phase"] is False
    assert summary["berzerker_melee_declaration_count"] == 0
    assert summary["berzerker_melee_successful_attacks"] == 0
    assert summary["fight_unit_selections"] == [
        {
            "phase_step": "FIGHT_FIRST",
            "player_id": "player:chaos-daemons",
            "unit_id": "unit:chaos-daemons-bloodcrushers",
            "unit_name": "Bloodcrushers",
        }
    ]
