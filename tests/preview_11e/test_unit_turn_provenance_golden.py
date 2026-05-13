from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.snapshot import load_game_snapshot, snapshot_game
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state
from warhammer40k_ai.engine.unit_turn_provenance import (
    Manual,
    PhaseBoundary,
    UnitTurnProvenance,
    battle_shock_status_token,
    derive_unit_turn_provenance,
    hidden_clears_from_provenance,
    must_fight_next_status_token,
    set_status_tokens_on_unit,
    set_unit_turn_provenance,
    set_up_this_turn_modifier_token,
    status_tokens_on_unit,
)
from warhammer40k_ai.engine.weapon_keyword_runtime import evaluate_updated_heavy_criteria
from warhammer40k_ai.battlefield.hidden_state import hidden_shot_breaks_hidden_from_provenance
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper import WahaHelper


pytestmark = pytest.mark.preview


def test_heavy_preview_fixture_reads_normalized_unit_turn_provenance() -> None:
    unit = SimpleNamespace(
        id="unit:preview",
        arrived_from_reserves_this_turn=True,
        round_state=SimpleNamespace(
            reinforced_this_round=True,
            moved_this_round=True,
            advanced_this_round=False,
            fell_back_this_round=False,
            disembarked_this_round=False,
            charged_this_round=False,
            shot_this_round=False,
            max_model_move_distance_this_turn=4.0,
        ),
        models=[],
    )

    provenance = derive_unit_turn_provenance(
        unit,
        battle_round=2,
        player_turn_id="battle_round:2:player:p1",
    )
    evaluation = evaluate_updated_heavy_criteria(provenance, unit_engaged=False)

    assert provenance.set_up_this_turn is True
    assert provenance.arrived_from_reserves_this_turn is True
    assert provenance.made_normal_move is True
    assert evaluation.eligible is False
    assert evaluation.reasons == (
        "unit was set up this turn",
        "a model moved more than 3 inches this turn",
    )


def test_hidden_clearing_reads_shot_state_and_respects_exemptions() -> None:
    shot_without_exemption = UnitTurnProvenance(
        unit_id="unit:hidden",
        battle_round=1,
        player_turn_id="battle_round:1:player:p1",
        shot_this_turn=True,
    )
    shot_with_exemption = UnitTurnProvenance(
        unit_id="unit:hidden",
        battle_round=1,
        player_turn_id="battle_round:1:player:p1",
        shot_this_turn=True,
        hidden_shooting_exemptions=("pathfinder_hidden_preserving_shooting",),
    )

    assert hidden_clears_from_provenance(shot_without_exemption) is True
    assert hidden_shot_breaks_hidden_from_provenance(shot_without_exemption) is True
    assert hidden_clears_from_provenance(shot_with_exemption) is False
    assert hidden_shot_breaks_hidden_from_provenance(shot_with_exemption) is False


def test_set_up_modifier_and_battle_shock_tokens_are_generic() -> None:
    set_up_token = set_up_this_turn_modifier_token(
        unit_id="unit:tempestus",
        source_id="detachment:bridgehead_preview",
        modifier_id="bridgehead_strike_set_up_this_turn_shooting",
        battle_round=2,
        player_turn_id="battle_round:2:player:p1",
        payload={"hit_bonus": 1},
    )
    battle_shock_token = battle_shock_status_token(
        unit_id="unit:target",
        source_id="battle_shock_test:failed",
        battle_round=2,
        player_turn_id="battle_round:2:player:p1",
    )
    must_fight_next = must_fight_next_status_token(
        unit_id="unit:slaanesh",
        source_id="stratagem:preview",
        expires_at=PhaseBoundary(phase="FIGHT_PHASE", battle_round=2, player_turn_id="battle_round:2:player:p1"),
        payload={"requires_next_fight_selection": True},
    )

    assert set_up_token.condition_kind == "set_up_this_turn_modifier"
    assert set_up_token.payload["requires_set_up_this_turn"] is True
    assert set_up_token.payload["hit_bonus"] == 1
    assert battle_shock_token.condition_kind == "battle_shock"
    assert isinstance(battle_shock_token.expires_at, Manual)
    assert battle_shock_token.payload["requires_command_phase_leadership_test_to_clear"] is True
    assert must_fight_next.condition_kind == "must_fight_next"
    assert must_fight_next.expires_at.to_dict()["kind"] == "phase_boundary"


def test_status_tokens_and_turn_provenance_are_snapshot_and_state_blob_visible() -> None:
    datasheet = WahaHelper().get_full_datasheet_info_by_name("Bloodletters")
    assert datasheet is not None
    unit = Unit(datasheet)
    army = Army(faction=unit.faction)
    unit.parent_army = army
    army.units.append(unit)
    player = Player("Preview Player", army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.map.units = [unit]

    provenance = set_unit_turn_provenance(
        unit,
        UnitTurnProvenance(
            unit_id=unit.id,
            battle_round=1,
            player_turn_id="battle_round:1:player:preview",
            set_up_this_turn=True,
            arrived_from_reserves_this_turn=True,
            shot_this_turn=True,
            max_model_move_distance_this_turn=2.5,
            hidden_shooting_exemptions=("stealth_hidden_preserving_shooting",),
        ),
    )
    token = battle_shock_status_token(
        unit_id=unit.id,
        source_id="battle_shock_test:failed",
        battle_round=1,
        player_turn_id=provenance.player_turn_id,
    )
    set_status_tokens_on_unit(unit, [token])

    payload = snapshot_game(game)
    unit_payload = next(entry for entry in payload["units"] if entry["id"] == unit.id)
    loaded = load_game_snapshot(payload)
    loaded_unit = loaded.players[0].army.units[0]
    state_blob = canonical_omniscient_state(loaded)
    state_unit = next(entry for entry in state_blob["units"] if entry["unit_id"] == unit.id)

    assert unit_payload["unit_turn_provenance"]["set_up_this_turn"] is True
    assert unit_payload["status_tokens"][0]["condition_kind"] == "battle_shock"
    assert loaded_unit.unit_turn_provenance.to_dict() == provenance.to_dict()
    assert status_tokens_on_unit(loaded_unit)[0].to_dict() == token.to_dict()
    assert state_unit["turn_provenance"]["hidden_shooting_exemptions"] == [
        "stealth_hidden_preserving_shooting"
    ]
    assert state_unit["status_tokens"][0]["payload"]["requires_command_phase_leadership_test_to_clear"] is True
