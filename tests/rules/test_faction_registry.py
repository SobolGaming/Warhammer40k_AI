from types import SimpleNamespace

from warhammer40k_ai.rules.context import RulesContext
from warhammer40k_ai.rules.detachment_manager import DetachmentManagerBase
from warhammer40k_ai.rules.detachment_registry import get_detachment_manager_attr_for_faction
from warhammer40k_ai.rules.faction_registry import faction_ids_match, get_faction_profile, normalize_faction_id


def test_faction_registry_normalizes_legacy_knight_aliases():
    assert normalize_faction_id("QT") == "CK"
    assert normalize_faction_id("QI") == "IK"
    assert faction_ids_match("QT", "CK") is True
    assert faction_ids_match("QI", "IK") is True


def test_detachment_registry_accepts_raw_and_canonical_faction_ids():
    assert get_detachment_manager_attr_for_faction("QT") == "chaos_knights_detachments"
    assert get_detachment_manager_attr_for_faction("CK") == "chaos_knights_detachments"
    assert get_detachment_manager_attr_for_faction("QI") == "imperial_knights_detachments"
    assert get_detachment_manager_attr_for_faction("IK") == "imperial_knights_detachments"


def test_rules_context_uses_faction_registry_alias_matching():
    ctx = RulesContext(
        player=None,
        army=None,
        faction_id="QT",
        detachment_type="",
    )

    assert ctx.has_faction_id("CK") is True


def test_detachment_manager_uses_faction_registry_alias_matching():
    manager = DetachmentManagerBase(army=SimpleNamespace(faction_id="QI"))

    assert manager._army_faction_matches("IK") is True


def test_faction_profile_exposes_primary_keyword():
    profile = get_faction_profile("SM")

    assert profile is not None
    assert profile.primary_keyword == "ADEPTUS ASTARTES"
