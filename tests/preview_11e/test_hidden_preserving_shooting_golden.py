from __future__ import annotations

import pytest

from warhammer40k_ai.battlefield.hidden_state import HiddenShootingExemption


pytestmark = pytest.mark.preview


TAU_EMPIRE_SOURCE = "wc_2026_05_13_tau_empire_faction_focus"


def test_hidden_preserving_shooting_fixture_is_preview_gated_and_sourced() -> None:
    exemption = HiddenShootingExemption(
        exemption_id="pathfinder_stealth_hidden_preserving_shooting_preview",
        unit_id="unit:pathfinders",
        source_id="preview:hidden_preserving_shooting",
        duration="current_player_turn",
        source_provenance=(TAU_EMPIRE_SOURCE,),
    )

    payload = exemption.to_dict()

    assert payload["enabled_by_profile"] == "11e_preview"
    assert payload["source_provenance"] == [TAU_EMPIRE_SOURCE]
    assert exemption.applies_to(unit_id="unit:pathfinders") is True
    assert exemption.applies_to(unit_id="unit:fire_warriors") is False
