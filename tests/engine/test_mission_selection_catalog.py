from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_selection import (
    DEFAULT_MISSION_PACK_ID,
    build_mission_selection_catalog,
    default_mission_selection,
    iter_random_mission_options,
    selected_mission_info_from_choice,
)
from warhammer40k_ai.engine.deployment_validation import validate_selected_mission_choice
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _build_game(*, player_a_force: str | None = None, player_b_force: str | None = None) -> Game:
    army_a = Army("Chaos Daemons", "Test")
    army_b = Army("Chaos Daemons", "Test")
    army_a.force_disposition = player_a_force
    army_b.force_disposition = player_b_force
    if player_a_force:
        army_a.allowed_force_dispositions = [player_a_force]
    if player_b_force:
        army_b.allowed_force_dispositions = [player_b_force]
    player_a = Player("Player A", control=PlayerControl.LOCAL, army=army_a)
    player_b = Player("Player B", control=PlayerControl.LOCAL, army=army_b)
    return Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player_a, player_b])


def test_default_mission_selection_preserves_chapter_approved_default() -> None:
    selection, layout = default_mission_selection()

    assert selection["pack_id"] == DEFAULT_MISSION_PACK_ID
    assert selection["id"] == "M"
    assert selection["primary"] == "Purge the Foe"
    assert selection["deployment"] == "Crucible of Battle"
    assert layout == 1


def test_catalog_without_force_dispositions_only_exposes_chapter_approved_pack() -> None:
    catalog = build_mission_selection_catalog(_build_game())

    assert len(catalog) == 20
    assert {entry["pack_id"] for entry in catalog} == {DEFAULT_MISSION_PACK_ID}
    assert {entry["id"] for entry in catalog} == set("ABCDEFGHIJKLMNOPQRST")


def test_catalog_with_force_dispositions_adds_preview_pack_options() -> None:
    catalog = build_mission_selection_catalog(_build_game(player_a_force="Assault", player_b_force="Bulwark"))

    preview_entries = [entry for entry in catalog if entry["pack_id"] == "provisional_11e_preview"]
    default_entries = [entry for entry in catalog if entry["pack_id"] == DEFAULT_MISSION_PACK_ID]

    assert default_entries
    assert len(preview_entries) == 1
    assert preview_entries[0]["id"] == "P11-AB-1"
    assert preview_entries[0]["force_disposition_pair_key"] == "assault__bulwark"
    assert preview_entries[0]["twist_is_stubbed"] is True
    assert preview_entries[0]["random_selection_enabled"] is False
    assert preview_entries[0]["secondary_rule_set_id"] == "provisional_11e_preview"


def test_random_mission_options_stay_on_chapter_approved_pack() -> None:
    random_options = iter_random_mission_options(_build_game(player_a_force="Assault", player_b_force="Bulwark"))

    assert len(random_options) == 20
    assert {entry["pack_id"] for entry in random_options} == {DEFAULT_MISSION_PACK_ID}
    assert all(entry["random_selection_enabled"] is True for entry in random_options)


def test_selected_mission_info_roundtrips_into_deployment_validation() -> None:
    catalog = build_mission_selection_catalog(_build_game(player_a_force="Siege", player_b_force="Bulwark"))
    preview_entry = next(entry for entry in catalog if entry["pack_id"] == "provisional_11e_preview")
    selected = selected_mission_info_from_choice(preview_entry, layout=preview_entry["layouts"][0])

    deployment_definition, selected_layout = validate_selected_mission_choice(selected, layout=selected["layout"])

    assert deployment_definition.deployment_definition_id == preview_entry["deployment_definition_id"]
    assert selected_layout == preview_entry["layouts"][0]
