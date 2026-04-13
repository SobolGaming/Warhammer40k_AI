from __future__ import annotations

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_HARBINGER,
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_QUARRY,
)
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.harbingers_of_dread import DOMINION
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_objective_control_bonus
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Knights",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
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
    faction_name: str = "Chaos Knights",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
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
        faction_id="QT",
        detachment="Helhunt Lance",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game(*, phase=BattleRoundPhases.COMMAND_PHASE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ck_army = Army.with_detachment("Chaos Knights", "Helhunt Lance")
    ck_army.faction_id = "QT"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ck_player = Player("CK", control=PlayerControl.REMOTE, army=ck_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ck_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = phase
    return game, ck_army, enemy_army, ck_player, enemy_player


def _refresh_units(game: Game) -> None:
    units = []
    for player in list(getattr(game, "players", []) or []):
        army = getattr(player, "army", None)
        units.extend(list(getattr(army, "units", []) or []))
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, decision_type: str, *, ability: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        if ability:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != ability:
                continue
        return request
    return None


def _find_option(request, *, key: str = "", unit_id: str = ""):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if key and str(payload.get("choice_key", "") or "").strip().upper() == str(key).strip().upper():
            return option
        if unit_id and str(payload.get("target_unit_id", "") or "").strip() == str(unit_id).strip():
            return option
    return None


def test_helhunt_enhancement_descriptors_registered():
    expected = {
        "000010751002": ("Aspect of the Beast", "select_bearer_specific_dread_ability"),
        "000010751003": ("Hunter's Helm", "reroll_advance_and_charge"),
        "000010751004": ("Octagram of Conjuration", "post_shoot_battleshock_for_friendly_war_dog_models"),
        "000010751005": ("Throne Tyrannicus", "selected_character_affected_by_bearer_war_dog_auras"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_hunters_helm_grants_reroll_advance_and_charge():
    ck_army = Army.with_detachment("Chaos Knights", "Helhunt Lance")
    ck_army.faction_id = "QT"
    source = _make_unit(
        "Stalker",
        keywords=["CHAOS KNIGHTS", "CHARACTER"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    ck_army.add_unit(source)

    _apply_enhancement(
        source,
        enhancement_id="000010751003",
        enhancement_name="Hunter's Helm",
    )

    assert bool(source.can_reroll_advance_roll()) is True
    assert bool(source.can_reroll_charge_roll()) is True


def test_aspect_of_the_beast_queues_choice_and_dominion_extends_bearer_aura():
    game, ck_army, enemy_army, ck_player, enemy_player = _build_game(phase=BattleRoundPhases.COMMAND_PHASE)

    aura = Ability(
        name="Dread Dominion (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, improve that WAR DOG model's "
            "Leadership and Objective Control characteristics by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    source = _make_unit(
        "Aspect Bearer",
        keywords=["CHAOS KNIGHTS", "CHARACTER", "TITANIC"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    source.possible_abilities = [aura]
    war_dog = _make_unit(
        "War Dog",
        keywords=["CHAOS KNIGHTS", "WAR DOG"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ck_army.add_unit(source)
    ck_army.add_unit(war_dog)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(war_dog, x=13.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    _refresh_units(game)

    _apply_enhancement(
        source,
        enhancement_id="000010751002",
        enhancement_name="Aspect of the Beast",
    )

    assert get_aura_objective_control_bonus(war_dog, game_map=game.map) == 0
    assert not ck_army.harbingers_of_dread.is_dread_active(DOMINION.key)

    ck_army.chaos_knights_detachments.on_command_phase_start(game=game, player=ck_player)
    request = _find_request(game, DECISION_CHOOSE_HARBINGER, ability="helhunt_aspect_of_the_beast")
    assert request is not None
    option = _find_option(request, key=DOMINION.key)
    assert option is not None

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ck_player.id,
        option_id=option.option_id,
        payload={},
    )
    outcome = dispatch_decision(game, request, result)
    assert bool(getattr(outcome, "ok", False))

    assert ck_army.harbingers_of_dread.is_dread_active(DOMINION.key, unit=source)
    assert not ck_army.harbingers_of_dread.is_dread_active(DOMINION.key, unit=war_dog)
    assert not ck_army.harbingers_of_dread.is_dread_active(DOMINION.key)
    assert get_aura_objective_control_bonus(war_dog, game_map=game.map) == 1


def test_throne_tyrannicus_shares_supported_war_dog_aura_until_next_command_phase():
    game, ck_army, _enemy_army, ck_player, _enemy_player = _build_game(phase=BattleRoundPhases.COMMAND_PHASE)

    aura = Ability(
        name="Dread Dominion (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, improve that WAR DOG model's "
            "Leadership and Objective Control characteristics by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    source = _make_unit(
        "Throne Bearer",
        keywords=["CHAOS KNIGHTS", "CHARACTER", "TITANIC"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    source.possible_abilities = [aura]
    target = _make_unit(
        "Linked Character",
        keywords=["CHAOS KNIGHTS", "CHARACTER"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    ck_army.add_unit(source)
    ck_army.add_unit(target)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(target, x=6.0, y=0.0)
    _refresh_units(game)

    _apply_enhancement(
        source,
        enhancement_id="000010751005",
        enhancement_name="Throne Tyrannicus",
    )

    assert get_aura_objective_control_bonus(target, game_map=game.map) == 0

    ck_army.chaos_knights_detachments.on_command_phase_start(game=game, player=ck_player)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="helhunt_throne_tyrannicus")
    assert request is not None
    option = _find_option(request, unit_id=str(get_entity_id(target) or ""))
    assert option is not None

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ck_player.id,
        option_id=option.option_id,
        payload={},
    )
    outcome = dispatch_decision(game, request, result)
    assert bool(getattr(outcome, "ok", False))

    _set_unit_location(target, x=30.0, y=0.0)
    assert get_aura_objective_control_bonus(target, game_map=game.map) == 1

    game.turn = 2
    ck_army.chaos_knights_detachments.on_command_phase_start(game=game, player=ck_player)
    assert get_aura_objective_control_bonus(target, game_map=game.map) == 0


def test_octagram_of_conjuration_grants_post_shoot_battleshock_to_nearby_war_dog():
    game, ck_army, enemy_army, _ck_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)

    source = _make_unit(
        "Knight Abominant",
        keywords=["CHAOS KNIGHTS", "CHARACTER", "TITANIC", "KNIGHT ABOMINANT"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    war_dog = _make_unit(
        "War Dog Karnivore",
        keywords=["CHAOS KNIGHTS", "WAR DOG"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ck_army.add_unit(source)
    ck_army.add_unit(war_dog)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(war_dog, x=6.0, y=0.0)
    _set_unit_location(enemy_a, x=18.0, y=0.0)
    _set_unit_location(enemy_b, x=19.0, y=1.0)
    _refresh_units(game)

    _apply_enhancement(
        source,
        enhancement_id="000010751004",
        enhancement_name="Octagram of Conjuration",
    )

    specs = war_dog.model_post_shoot_battleshock_specs(war_dog.models[0])
    assert any(str(spec.get("source", "") or "") == "Octagram of Conjuration" for spec in specs)

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=war_dog,
        hits_by_target={enemy_a: 1, enemy_b: 1},
        hit_models_by_target={
            enemy_a: [war_dog.models[0]],
            enemy_b: [war_dog.models[0]],
        },
    )

    request = _find_request(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert request is not None
    assert "Octagram of Conjuration" in str(getattr(request, "prompt", "") or "")


def test_octagram_of_conjuration_applies_to_bearer_via_masters_of_the_pack():
    game, ck_army, enemy_army, _ck_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)

    source = _make_unit(
        "Pack Alpha",
        keywords=["CHAOS KNIGHTS", "CHARACTER", "TITANIC", "KNIGHT ABOMINANT"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    war_dog_a = _make_unit(
        "War Dog A",
        keywords=["CHAOS KNIGHTS", "WAR DOG"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    war_dog_b = _make_unit(
        "War Dog B",
        keywords=["CHAOS KNIGHTS", "WAR DOG"],
        faction_keywords=["CHAOS KNIGHTS"],
    )
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ck_army.add_unit(source)
    ck_army.add_unit(war_dog_a)
    ck_army.add_unit(war_dog_b)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(war_dog_a, x=4.0, y=0.0)
    _set_unit_location(war_dog_b, x=5.0, y=0.0)
    _set_unit_location(enemy, x=18.0, y=0.0)
    _refresh_units(game)

    _apply_enhancement(
        source,
        enhancement_id="000010751004",
        enhancement_name="Octagram of Conjuration",
    )

    specs = source.model_post_shoot_battleshock_specs(source.models[0])
    assert any(str(spec.get("source", "") or "") == "Octagram of Conjuration" for spec in specs)

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=source,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: [source.models[0]]},
    )

    request = _find_request(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert request is not None
    assert "Octagram of Conjuration" in str(getattr(request, "prompt", "") or "")
