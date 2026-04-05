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
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        attached_to=None,
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
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
        faction_id="CSM",
        detachment="Nightmare Hunt",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    nightmare_army = Army("Chaos Space Marines", "Nightmare Hunt")
    nightmare_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    nightmare_player = Player("Nightmare", control=PlayerControl.REMOTE, army=nightmare_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(nightmare_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, nightmare_army, enemy_army, nightmare_player, enemy_player


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


def test_nightmare_hunt_enhancement_descriptors_registered():
    expected = {
        "000010641002": (
            "Greyveil Hex",
            "bearer_unit_gains_stealth_and_objective_controlled_ranged_targeting_cap",
        ),
        "000010641003": (
            "Warp-fuelled Thrusters",
            "end_of_opponent_fight_phase_enter_strategic_reserves_if_not_engaged",
        ),
        "000010641004": (
            "Terrorglut Parasite",
            "start_of_fight_phase_bearer_engagement_range_enemy_battleshock_minus_one",
        ),
        "000010641005": (
            "Sorrowscent Vulture",
            "grant_scouts_to_bearer_unit_and_allow_attach_to_warp_talons",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_greyveil_hex_grants_stealth_and_controlled_objective_targeting_cap():
    game, nightmare_army, enemy_army, _nightmare_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nightmare_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010641002",
        enhancement_name="Greyveil Hex",
        description=(
            "Models in the bearer's unit have the Stealth ability. While within range of one or more objective markers "
            "you control, that unit can only be selected as the target of a ranged attack if the attacking model is within 18\"."
        ),
    )

    assert bool(source.has_stealth())
    source._within_controlled_objective_range = lambda _game_map=None: True
    dist, sources = source.get_ranged_targeting_restriction(game_map=game.map)
    assert float(dist or 0.0) == 18.0
    assert any("Greyveil Hex" in str(s) for s in list(sources or []))

    source._within_controlled_objective_range = lambda _game_map=None: False
    dist2, sources2 = source.get_ranged_targeting_restriction(game_map=game.map)
    assert dist2 is None
    assert list(sources2 or []) == []


def test_warp_fuelled_thrusters_triggers_end_of_opponent_fight_phase():
    game, nightmare_army, enemy_army, nightmare_player, enemy_player = _build_game()
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
    nightmare_army.add_unit(source)
    enemy_army.add_unit(enemy)

    _apply_enhancement(
        source,
        enhancement_id="000010641003",
        enhancement_name="Warp-fuelled Thrusters",
        description=(
            "At the end of your opponent's Fight phase, if the bearer's unit is not within Engagement Range, "
            "you can place it into Strategic Reserves."
        ),
    )

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    ability = source.get_end_of_opponent_turn_strategic_reserves_ability()
    assert isinstance(ability, dict)
    assert str(ability.get("ability_key", "") or "") == "warp_fuelled_thrusters"
    assert str(ability.get("trigger_phase", "") or "") == "OPPONENT_FIGHT_PHASE_END"

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    pending_turn_end = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "warp_fuelled_thrusters"
    ]
    assert len(pending_turn_end) == 0

    game._on_phase_end_opponent_fight_phase_strategic_reserves(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    pending_fight_end = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "warp_fuelled_thrusters"
    ]
    assert len(pending_fight_end) == 1
    _resolve_yes_option(game, pending_fight_end[0], player_id=nightmare_player.id)

    assert bool(source.is_in_strategic_reserves())
    assert source not in list(getattr(game.map, "units", []) or [])


def test_terrorglut_parasite_applies_minus_one_battleshock_at_fight_start():
    game, nightmare_army, enemy_army, _nightmare_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nightmare_army.add_unit(source)
    enemy_army.add_unit(enemy)

    _apply_enhancement(
        source,
        enhancement_id="000010641004",
        enhancement_name="Terrorglut Parasite",
        description=(
            "At the start of the Fight phase, each enemy unit within Engagement Range of the bearer must take a "
            "Battle-shock test, subtracting 1 from the result."
        ),
    )

    _set_unit_location(source, x=10.0, y=10.0)
    _set_unit_location(enemy, x=10.5, y=10.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    captured = {"modifier": None, "reasons": []}
    original_take = enemy.take_battle_shock_test

    def _capture_take(*args, **kwargs):
        sr = dict(getattr(enemy, "special_rules", {}) or {})
        captured["modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0)
        captured["reasons"] = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        return original_take(*args, **kwargs)

    enemy.take_battle_shock_test = _capture_take
    game._on_phase_start_engagement_battleshock(player=game.get_current_player(), phase=BattleRoundPhases.FIGHT_PHASE)

    assert captured["modifier"] == -1
    assert any("Ability modifier" in str(reason) for reason in list(captured["reasons"] or []))


def test_sorrowscent_vulture_grants_scouts_and_warp_talons_attach_override():
    game, nightmare_army, _enemy_army, _nightmare_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    source = _make_unit(
        "Chaos Lord with Jump Pack",
        datasheet_id="000001500",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
        attached_to=["000001600"],
    )
    source.can_be_attached_to = ["000001600"]
    warp_talons = _make_unit(
        "Warp Talons",
        datasheet_id="000000959",
        keywords=["INFANTRY", "HERETIC ASTARTES", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=5,
    )
    warp_talons.max_attached_leaders = lambda: 1
    warp_talons._leader_attachment_constraint_error = lambda _leader, current_leaders=None: ""

    nightmare_army.add_unit(source)
    nightmare_army.add_unit(warp_talons)
    game.map.units = [source, warp_talons]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010641005",
        enhancement_name="Sorrowscent Vulture",
        description=(
            "Models in the bearer's unit have the Scouts 6\" ability. In the Declare Battle Formations step, "
            "the bearer can be attached to a Warp Talons unit."
        ),
    )

    has_scout, scout_distance = source.has_scout()
    assert has_scout is True
    assert float(scout_distance) == 6.0
    assert "000000959" in list(getattr(source, "can_be_attached_to", []) or [])
    assert bool(source.can_attach_to(warp_talons))
