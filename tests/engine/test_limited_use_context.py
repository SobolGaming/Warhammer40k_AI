from __future__ import annotations

from warhammer40k_ai.engine.limited_use_context import (
    LIMIT_SCOPE_BATTLE,
    LIMIT_SCOPE_BATTLE_PER_MODEL,
    LIMIT_SCOPE_BATTLE_PER_UNIT,
    LIMIT_SCOPE_BATTLE_ROUND,
    LIMIT_SCOPE_TURN,
    limited_use_scopes_from_text,
    normalize_optional_ability_limited_use_context,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_OVERWATCH_SHOOTER
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def test_normalizes_known_waaagh_without_once_per_battle_message() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "phase": "Command phase",
            "waaagh_call_number": 1,
            "waaagh_scope": "all",
        },
        ability_key="waaagh",
        ability_name="Waaagh!",
        message="Call Waaagh!? (First call this battle)",
    )

    assert context["limited_use"] is True
    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE
    assert context["limited_use_key"] == "waaagh"
    assert context["once_per_battle"] is True
    assert context["once_per_battle_key"] == "waaagh"
    assert context["once_per_battle_scope"] == "army"


def test_limited_use_battle_scope_can_opt_out_of_once_per_battle_alias() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "limited_use": True,
            "limited_use_scope": "battle",
            "limited_use_key": "waaagh",
            "once_per_battle": False,
        },
        ability_key="waaagh",
        ability_name="Waaagh! (Bully Boyz second call)",
        message="Call second Waaagh!?",
    )

    assert context["limited_use"] is True
    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE
    assert context["limited_use_key"] == "waaagh"
    assert context["once_per_battle"] is False
    assert "once_per_battle_key" not in context


def test_normalizes_model_once_per_battle_prompt_from_known_helper_key() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "phase": "Fight phase",
            "model_id": "model-1",
            "buff_key": "ancient_banner",
        },
        ability_key="start_any_phase_damage_set_one",
        ability_name="Ancient Banner",
        message="Activate Ancient Banner?",
    )

    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE_PER_MODEL
    assert context["limited_use_key"] == "ancient_banner"
    assert context["once_per_battle_scope"] == "model"
    assert context["once_per_battle_per_model"] is True


def test_normalizes_unit_once_per_battle_prompt_from_text() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "unit_id": "unit-1",
            "ability_key": "dark_ritual",
        },
        ability_key="dark_ritual",
        ability_name="Dark Ritual",
        message="Use Dark Ritual? Once per battle.",
    )

    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE
    assert context["limited_use_key"] == "dark_ritual"
    assert context["once_per_battle_scope"] == "unit"


def test_normalizes_stratagem_once_per_battle_scope_before_target_unit() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "stratagem_id": "strat-1",
            "unit_id": "target-unit",
            "once_per_battle_key": "insane_bravery",
        },
        ability_key="insane_bravery",
        ability_name="Insane Bravery",
        message="Use Insane Bravery?",
    )

    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE
    assert context["once_per_battle_scope"] == "stratagem"


def test_normalizes_once_per_battle_round_key() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "once_per_battle_round_key": "watch_master",
        },
        ability_key="watch_master",
        ability_name="Watch Master",
        message="Reduce this Stratagem cost.",
    )

    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE_ROUND
    assert context["limited_use_key"] == "watch_master"
    assert context["once_per_battle_round"] is True
    assert context["once_per_battle_round_key"] == "watch_master"


def test_normalizes_fire_overwatch_as_once_per_turn_from_stratagem_context() -> None:
    context = normalize_optional_ability_limited_use_context(
        {
            "ability": "fire_overwatch",
            "stratagem_name": "FIRE OVERWATCH",
            "tool_id": "stratagem:fire_overwatch",
        },
        ability_key="fire_overwatch",
        ability_name="FIRE OVERWATCH",
        message="FIRE OVERWATCH: select a unit to shoot the enemy mover.",
    )

    assert context["limited_use"] is True
    assert context["limited_use_scope"] == LIMIT_SCOPE_TURN
    assert context["limited_use_key"] == "fire_overwatch"
    assert context["once_per_turn"] is True
    assert context["once_per_turn_key"] == "fire_overwatch"


def test_scopes_from_source_text_distinguishes_per_unit_and_per_model() -> None:
    assert limited_use_scopes_from_text("Each model can only use this once per battle per model.") == (
        LIMIT_SCOPE_BATTLE_PER_MODEL,
    )
    assert limited_use_scopes_from_text("You cannot target the same Character model more than once per battle.") == (
        LIMIT_SCOPE_BATTLE_PER_MODEL,
    )
    assert limited_use_scopes_from_text("Each unit can only be selected once per battle per unit.") == (
        LIMIT_SCOPE_BATTLE_PER_UNIT,
    )


def test_request_decision_normalizes_direct_choose_decision_once_key() -> None:
    army = Army.with_detachment("Grey Knights", detachment_type="Other")
    player = Player("GK", PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player])

    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Grimoire of Conjunctions: choose whether the unit gains the bonus.",
        player_id=player.id,
        options=[
            DecisionOption.create("Use", payload={"action": "use", "target_unit_id": "unit-1"}),
            DecisionOption.create("Skip", payload={"action": "skip"}),
        ],
        context={
            "ability": "grey_knights_augurium_grimoire_of_conjunctions",
            "ability_name": "Grimoire of Conjunctions",
            "unit_id": "unit-1",
            "once_key": "grimoire_of_conjunctions",
            "optional": True,
        },
    )

    game.request_decision(request)

    pending = game.decision_queue.list()
    assert len(pending) == 1
    context = pending[0].context
    assert context["limited_use"] is True
    assert context["limited_use_scope"] == LIMIT_SCOPE_BATTLE
    assert context["limited_use_key"] == "grimoire_of_conjunctions"
    assert context["once_per_battle_key"] == "grimoire_of_conjunctions"
    assert context["once_per_battle_scope"] == "unit"


def test_request_decision_normalizes_fire_overwatch_selector_as_turn_limited() -> None:
    army = Army.with_detachment("Space Marines", detachment_type="Other")
    player = Player("SM", PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player])

    request = DecisionRequest.create(
        DECISION_SELECT_OVERWATCH_SHOOTER,
        "FIRE OVERWATCH: select a unit to shoot the enemy mover.",
        player_id=player.id,
        options=[
            DecisionOption.create("Shooter", payload={"unit_id": "unit-1", "ability_key": "fire_overwatch"}),
            DecisionOption.create("Skip", payload={"action": "skip", "skip": True}),
        ],
        context={
            "ability": "fire_overwatch",
            "phase_name": "Movement phase",
            "enemy_unit_id": "unit-enemy",
            "stratagem_name": "FIRE OVERWATCH",
            "tool_id": "stratagem:fire_overwatch",
            "optional": True,
        },
    )

    game.request_decision(request)

    pending = game.decision_queue.list()
    assert len(pending) == 1
    context = pending[0].context
    assert context["limited_use"] is True
    assert context["limited_use_scope"] == LIMIT_SCOPE_TURN
    assert context["limited_use_key"] == "fire_overwatch"
    assert context["once_per_turn"] is True
    assert context["once_per_turn_key"] == "fire_overwatch"
