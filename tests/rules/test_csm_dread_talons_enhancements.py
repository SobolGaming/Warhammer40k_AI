from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Dread Talons",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Dread Talons")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, csm_army, enemy_army, csm_player, enemy_player


def _resolve_yes_option(game: Game, request, *, player_id: str) -> None:
    yes_option_id = ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            yes_option_id = str(getattr(option, "option_id", "") or "")
            break
    assert yes_option_id
    outcome = resolve_decision_command(game, request, yes_option_id, player_id=player_id)
    assert bool(getattr(outcome, "ok", False))


def test_dread_talons_enhancement_descriptors_registered():
    expected = {
        "000008972002": ("Eater of Dread", "command_phase_cp_roll_per_battle_shocked_enemy_unit"),
        "000008972003": ("Night's Shroud", "bearer_unit_gains_stealth"),
        "000008972004": ("Warp-fuelled Thrusters", "end_of_opponent_turn_enter_strategic_reserves_if_not_engaged"),
        "000008972005": ("Willbreaker", "post_fight_bearer_select_hit_enemy_battleshock_test"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_nights_shroud_grants_stealth_to_bearer_unit():
    csm_army = Army.with_detachment("Chaos Space Marines", "Dread Talons")
    csm_army.faction_id = "CSM"
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    csm_army.add_unit(source)

    _apply_enhancement(
        source,
        enhancement_id="000008972003",
        enhancement_name="Night's Shroud",
        description="Models in the bearer's unit have the Stealth ability.",
    )

    assert bool(source.special_rules.get("enhancement_nights_shroud_stealth", False))
    assert bool(source.has_stealth())


def test_warp_fuelled_thrusters_end_of_opponent_turn_moves_unit_to_reserves():
    game, csm_army, enemy_army, csm_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Jump Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "JUMP PACK", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)

    _apply_enhancement(
        source,
        enhancement_id="000008972004",
        enhancement_name="Warp-fuelled Thrusters",
        description=(
            "At the end of your opponent's turn, if the bearer's unit is not within Engagement Range of one or more enemy "
            "units, you can remove the bearer's unit from the battlefield and place it into Strategic Reserves."
        ),
    )

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    ability = source.get_end_of_opponent_turn_strategic_reserves_ability()
    assert isinstance(ability, dict)
    assert str(ability.get("ability_key", "") or "") == "warp_fuelled_thrusters"
    assert bool(ability.get("once_per_battle", True)) is False

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "warp_fuelled_thrusters"
    ]
    assert len(pending) == 1
    _resolve_yes_option(game, pending[0], player_id=csm_player.id)

    assert bool(source.is_in_strategic_reserves())
    assert source not in list(getattr(game.map, "units", []) or [])


def test_willbreaker_queues_post_fight_battleshock_for_bearer_hits_only():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    attacker = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(attacker)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    game.map.units = [attacker, enemy_a, enemy_b]
    game.rebuild_entity_registry()

    _apply_enhancement(
        attacker,
        enhancement_id="000008972005",
        enhancement_name="Willbreaker",
        description=(
            "In the Fight phase, after the bearer has made its attacks, select one enemy unit hit by one or more "
            "of those attacks. That unit must take a Battle-shock test."
        ),
    )

    bearer_id = str(attacker.special_rules.get("enhancement_willbreaker_bearer_model_id", "") or "")
    assert bearer_id
    bearer_model = None
    non_bearer_model = None
    for model in list(attacker.models or []):
        model_id = str(get_entity_id(model) or "")
        if model_id == bearer_id:
            bearer_model = model
        else:
            non_bearer_model = model
    assert bearer_model is not None
    assert non_bearer_model is not None

    game._on_fight_attacks_resolved_post_fight_battleshock(
        unit=attacker,
        attacker_unit=attacker,
        hits_by_target={enemy_a: 1, enemy_b: 1},
        hit_models_by_target={enemy_a: {bearer_model}, enemy_b: {non_bearer_model}},
    )
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
    ]
    assert len(pending) == 1
    context = dict(getattr(pending[0], "context", {}) or {})
    assert str(context.get("ability_name", "") or "") == "Willbreaker"

    options = list(getattr(pending[0], "options", []) or [])
    assert len(options) == 1
    only_target_id = str((options[0].payload or {}).get("unit_id", "") or "")
    assert only_target_id == str(get_entity_id(enemy_a) or "")


def test_eater_of_dread_command_phase_cp_roll_counts_only_on_battlefield_battle_shocked_enemies():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_in_reserves = _make_unit(
        "Enemy Reserves",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_in_reserves.reserve_status = "reserves"

    csm_army.add_unit(source)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    enemy_army.add_unit(enemy_in_reserves)

    _apply_enhancement(
        source,
        enhancement_id="000008972002",
        enhancement_name="Eater of Dread",
        description=(
            "At the start of your Command phase, if the bearer is on the battlefield, roll one D6, adding 1 to the result "
            "for each Battle-shocked enemy unit that is on the battlefield: on a 5+, you gain 1CP."
        ),
    )

    enemy_a.apply_status_effect(BattleShockEffect(current_turn=1))
    enemy_b.apply_status_effect(BattleShockEffect(current_turn=1))
    enemy_in_reserves.apply_status_effect(BattleShockEffect(current_turn=1))

    game.map.units = [source, enemy_a, enemy_b]
    game.rebuild_entity_registry()

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=3):
        game._on_phase_start_command_phase_cp_rolls(player=csm_player, phase=game.phase)
    after_cp = int(csm_player.command_points or 0)

    assert after_cp == before_cp + 1


def test_eater_of_dread_does_not_trigger_when_bearer_not_on_battlefield():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    source.reserve_status = "reserves"
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy.apply_status_effect(BattleShockEffect(current_turn=1))

    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _apply_enhancement(source, enhancement_id="000008972002", enhancement_name="Eater of Dread")
    game.map.units = [enemy]
    game.rebuild_entity_registry()

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=6):
        game._on_phase_start_command_phase_cp_rolls(player=csm_player, phase=game.phase)
    after_cp = int(csm_player.command_points or 0)

    assert after_cp == before_cp
