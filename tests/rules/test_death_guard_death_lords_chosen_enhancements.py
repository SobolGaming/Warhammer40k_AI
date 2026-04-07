from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Death Guard",
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Death Guard",
    keywords=None,
    faction_keywords=None,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
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
        faction_id="DG",
        detachment="Death Lord's Chosen",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army.with_detachment("Death Guard", "Death Lord's Chosen")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, dg_army, enemy_army, dg_player, enemy_player


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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    attached = list(getattr(bodyguard, "attached_leaders", []) or [])
    if leader not in attached:
        attached.append(leader)
    bodyguard.attached_leaders = attached


def test_death_lords_chosen_enhancement_descriptors_registered():
    expected = {
        "000010143002": (
            "Face of Death",
            "start_of_fight_phase_bearer_engagement_range_enemy_battleshock",
        ),
        "000010143003": (
            "Vile Vigour",
            "leading_bearer_unit_movement_bonus_and_advance_reroll",
        ),
        "000010143004": (
            "Warprot Talisman",
            "once_per_battle_end_of_opponent_turn_enter_strategic_reserves",
        ),
        "000010143005": (
            "Helm of the Fly King",
            "leading_bearer_unit_ranged_targeting_cap",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_face_of_death_triggers_battleshock_for_enemy_in_engagement_range():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Deathshroud Champion",
        keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=0.5, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010143002",
        enhancement_name="Face of Death",
        description=(
            "At the start of the Fight phase, each enemy unit within Engagement Range of the bearer's unit "
            "must take a Battle-shock test."
        ),
    )

    calls: list[int] = []
    original_take = enemy.take_battle_shock_test
    enemy.take_battle_shock_test = lambda turn: calls.append(int(turn or 0)) or original_take(turn)

    game._on_phase_start_death_guard_detachments(player=dg_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert len(calls) == 1

    calls.clear()
    _set_unit_location(enemy, x=20.0, y=0.0)
    game._on_phase_start_death_guard_detachments(player=dg_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert calls == []


def test_vile_vigour_requires_bearer_leading_and_alive():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    leader = _make_unit(
        "Death Guard Terminator Lord",
        keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["BODYGUARD"],
    )
    bodyguard = _make_unit(
        "Blightlord Terminators",
        keywords=["INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    _set_unit_location(leader, x=0.0, y=0.0)
    _set_unit_location(bodyguard, x=0.0, y=1.5)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000010143003",
        enhancement_name="Vile Vigour",
        description=(
            "While the bearer is leading a unit, add 1\" to the Move characteristic of models in that unit and "
            "you can re-roll Advance rolls made for that unit."
        ),
    )

    base_move = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "M", game_map=game.map))
    assert not bool(bodyguard.can_reroll_advance_roll())

    _attach_leader(bodyguard, leader)
    boosted_move = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "M", game_map=game.map))
    assert boosted_move == base_move + 1
    assert bool(bodyguard.can_reroll_advance_roll())

    bearer = leader.models[0]
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    fallback_move = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "M", game_map=game.map))
    assert fallback_move == base_move
    assert not bool(bodyguard.can_reroll_advance_roll())


def test_warprot_talisman_prompts_and_enters_strategic_reserves_once():
    game, dg_army, enemy_army, dg_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Terminator Sorcerer",
        keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010143004",
        enhancement_name="Warprot Talisman",
        description=(
            "Once per battle, at the end of your opponent's turn, if the bearer's unit is not within Engagement Range "
            "of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves."
        ),
    )

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "warprot_talisman"
    ]
    assert len(pending) == 1
    _resolve_yes_option(game, pending[0], player_id=dg_player.id)

    assert bool(source.is_in_strategic_reserves())
    assert bool(source.has_used_unit_once_per_battle("warprot_talisman"))


def test_helm_of_the_fly_king_applies_targeting_cap_while_bearer_is_leading():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    leader = _make_unit(
        "Terminator Champion",
        keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["BODYGUARD"],
    )
    bodyguard = _make_unit(
        "Deathshroud Terminators",
        keywords=["INFANTRY", "TERMINATOR", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    _set_unit_location(leader, x=0.0, y=0.0)
    _set_unit_location(bodyguard, x=0.0, y=1.0)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000010143005",
        enhancement_name="Helm of the Fly King",
        description=(
            "While the bearer is leading a unit, models in that unit cannot be targeted by ranged attacks unless "
            "the attacking model is within 18\"."
        ),
    )

    dist, sources = bodyguard.get_ranged_targeting_restriction(game_map=game.map)
    assert dist is None
    assert list(sources or []) == []

    _attach_leader(bodyguard, leader)
    dist, sources = bodyguard.get_ranged_targeting_restriction(game_map=game.map)
    assert float(dist or 0.0) == 18.0
    assert any("Helm of the Fly King" in str(source) for source in list(sources or []))

    bearer = leader.models[0]
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    dist2, sources2 = bodyguard.get_ranged_targeting_restriction(game_map=game.map)
    assert dist2 is None
    assert list(sources2 or []) == []
