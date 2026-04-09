from __future__ import annotations

from warhammer40k_ai.battlefield.terrain_layouts import TerrainLayoutsRegistry
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_selection import (
    DEFAULT_MISSION_PACK_ID,
    build_mission_selection_catalog,
    default_mission_selection,
    get_mission_pack,
    iter_random_mission_options,
    selected_mission_info_from_choice,
)
from warhammer40k_ai.engine.deployment_validation import validate_selected_mission_choice
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _build_game(*, player_a_force: str | None = None, player_b_force: str | None = None) -> Game:
    army_a = Army.with_detachment("Chaos Daemons", "Test")
    army_b = Army.with_detachment("Chaos Daemons", "Test")
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
    catalog = build_mission_selection_catalog(
        _build_game(player_a_force="Take and Hold", player_b_force="Priority Assets")
    )

    preview_entries = [entry for entry in catalog if entry["pack_id"] == "provisional_11e_preview"]
    default_entries = [entry for entry in catalog if entry["pack_id"] == DEFAULT_MISSION_PACK_ID]

    assert default_entries
    assert len(preview_entries) == 1
    assert preview_entries[0]["id"] == "P11-TH-PA"
    assert preview_entries[0]["force_disposition_pair_key"] == "take_and_hold__priority_assets"
    assert preview_entries[0]["twist_is_stubbed"] is True
    assert preview_entries[0]["random_selection_enabled"] is False
    assert preview_entries[0]["secondary_rule_set_id"] == "provisional_11e_preview"
    assert preview_entries[0]["layouts"] == [3, 5, 8]
    assert preview_entries[0]["metadata"]["preview_visibility_semantics_enabled"] is True
    assert preview_entries[0]["metadata"]["preview_layout_recommendation_source"] == "mission_pairing"


def test_preview_pack_exposes_five_force_dispositions() -> None:
    pack = get_mission_pack("provisional_11e_preview")

    assert [entry.display_name for entry in pack.force_dispositions] == [
        "Take and Hold",
        "Purge the Foe",
        "Disruption",
        "Reconnaissance",
        "Priority Assets",
    ]
    assert len(pack.pairings) == 25


def test_preview_pack_pairing_matrix_exposes_exactly_three_valid_layout_ids_per_pairing() -> None:
    pack = get_mission_pack("provisional_11e_preview")
    valid_layout_ids = set(TerrainLayoutsRegistry.layout_ids())

    for player_a in pack.force_dispositions:
        for player_b in pack.force_dispositions:
            catalog = build_mission_selection_catalog(
                _build_game(
                    player_a_force=player_a.display_name,
                    player_b_force=player_b.display_name,
                )
            )
            preview_entries = [entry for entry in catalog if entry["pack_id"] == pack.pack_id]

            assert len(preview_entries) == 1
            layouts = preview_entries[0]["layouts"]
            assert layouts is not None
            assert len(layouts) == 3
            assert len(set(layouts)) == 3
            assert set(layouts).issubset(valid_layout_ids)


def test_random_mission_options_stay_on_chapter_approved_pack() -> None:
    random_options = iter_random_mission_options(
        _build_game(player_a_force="Take and Hold", player_b_force="Priority Assets")
    )

    assert len(random_options) == 20
    assert {entry["pack_id"] for entry in random_options} == {DEFAULT_MISSION_PACK_ID}
    assert all(entry["random_selection_enabled"] is True for entry in random_options)


def test_selected_mission_info_roundtrips_into_deployment_validation() -> None:
    catalog = build_mission_selection_catalog(
        _build_game(player_a_force="Disruption", player_b_force="Reconnaissance")
    )
    preview_entry = next(entry for entry in catalog if entry["pack_id"] == "provisional_11e_preview")
    selected = selected_mission_info_from_choice(preview_entry, layout=preview_entry["layouts"][0])

    deployment_definition, selected_layout = validate_selected_mission_choice(selected, layout=selected["layout"])

    assert deployment_definition.deployment_definition_id == preview_entry["deployment_definition_id"]
    assert selected_layout == preview_entry["layouts"][0]
    assert selected["metadata"]["preview_visibility_semantics_enabled"] is True


def test_preview_battlefield_creation_authors_terrain_areas_and_enables_preview_visibility_gate() -> None:
    game = _build_game(player_a_force="Take and Hold", player_b_force="Purge the Foe")
    catalog = build_mission_selection_catalog(game)
    preview_entry = next(entry for entry in catalog if entry["pack_id"] == "provisional_11e_preview")
    game.selected_mission_info = selected_mission_info_from_choice(preview_entry, layout=preview_entry["layouts"][0])

    game.execute_create_battlefield_phase()

    assert game.map.preview_visibility_semantics_enabled is True
    assert game.map.preview_visibility_ruleset == "preview_11e_terrain_apr_2026"
    assert len(game.map.terrain_features) > 0
    assert len(game.map.terrain_areas) > 0
