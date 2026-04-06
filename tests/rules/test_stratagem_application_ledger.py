from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.stratagem_ledger import StratagemApplicationLedger


def _manager_stub():
    return SimpleNamespace(
        _current_phase_name="Fight phase",
        _used_stratagems_this_phase={"COUNTER-OFFENSIVE"},
        _heroic_intervention_units_this_phase={"unit:1"},
        _rapid_ingress_units_this_phase=set(),
        _command_reroll_units_this_phase={"unit:3"},
        _grenade_units_this_phase=set(),
    )


def test_ledger_reads_existing_phase_usage_sets() -> None:
    manager = _manager_stub()
    ledger = StratagemApplicationLedger(manager)

    assert ledger.phase_name() == "Fight phase"
    assert ledger.already_used_this_phase("counter-offensive") is True
    assert ledger.target_already_used_this_phase("heroic intervention", "unit:1") is True
    assert ledger.target_already_used_this_phase("command re-roll", "unit:2") is False


def test_ledger_marks_target_usage_through_manager_state() -> None:
    manager = _manager_stub()
    ledger = StratagemApplicationLedger(manager)

    ledger.mark_used_this_phase("Heroic Intervention")
    ledger.mark_target_used_this_phase("Heroic Intervention", "unit:9")

    assert "HEROIC INTERVENTION" in manager._used_stratagems_this_phase
    assert "unit:9" in manager._heroic_intervention_units_this_phase
