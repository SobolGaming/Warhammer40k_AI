from warhammer40k_ai.UI.ui_constants import SUPPORTED_DETACHMENT_RULES


def test_blood_tithe_detachment_rule_has_supported_badge_metadata():
    assert "BLOOD TITHE" in SUPPORTED_DETACHMENT_RULES
