from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_value
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "3",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: str = "3",
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _build_game(detachment_type: str = "Assimilation Swarm"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))

    tyr_army = Army("Tyranids", detachment_type)
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_army.configure_rule_managers(force=True)
    game.rebuild_entity_registry()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)


def _publish_command_phase(game: Game, player: Player, *, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name="COMMAND_PHASE")
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _feed_requests(game: Game) -> list:
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "feed_the_swarm"
    ]


def _request_for_source(game: Game, source_unit: Unit):
    source_id = str(get_entity_id(source_unit) or "")
    for req in _feed_requests(game):
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("source_unit_id", "") or "") == source_id:
            return req
    return None


def _pick_option_by_action(request, action: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == str(action).strip().lower():
            return option
    return None


def _destroy_models(unit: Unit, count: int) -> None:
    for _ in range(max(0, int(count))):
        if not unit.models:
            return
        model = unit.models.pop()
        model.wounds = 0
        unit.models_lost.append(model)
    unit.update_coherency()


def test_feed_the_swarm_queues_and_applies_heal():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game("Assimilation Swarm")
    harvester = _make_unit(
        "Haruspex",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    target = _make_unit(
        "Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="4",
    )
    tyr_army.add_unit(harvester)
    tyr_army.add_unit(target)
    _set_unit_position(harvester, 10.0, 10.0)
    _set_unit_position(target, 14.5, 10.0)
    target.models[0].wounds = 1
    game.rebuild_entity_registry()

    _publish_command_phase(game, tyr_player, current_player_index=0)
    request = _request_for_source(game, harvester)
    assert request is not None

    heal_option = _pick_option_by_action(request, "heal")
    assert heal_option is not None
    with patch("warhammer40k_ai.rules.tyranids_detachments.get_roll", return_value=2):
        value, apply_result = resolve_decision_value(
            game,
            request,
            heal_option.option_id,
            player_id=tyr_player.id,
        )

    assert apply_result is not None and bool(getattr(apply_result, "ok", False))
    assert isinstance(value, dict)
    assert str(value.get("action", "")).lower() == "heal"
    assert int(target.models[0].wounds) == int(target.models[0]._base_wounds)
    assert int(value.get("heal_roll", 0) or 0) == 3
    assert int(value.get("healed_wounds", 0) or 0) == 3
    assert tyr_army.tyranids_detachments.feed_the_swarm_source_can_act(
        harvester, game=game, player=tyr_player
    ) is False


def test_feed_the_swarm_endless_multitude_returns_three_and_blocks_second_regen():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game("Assimilation Swarm")
    source_a = _make_unit(
        "Harvester A",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    source_b = _make_unit(
        "Harvester B",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    target = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
        model_count=5,
    )
    tyr_army.add_unit(source_a)
    tyr_army.add_unit(source_b)
    tyr_army.add_unit(target)
    _set_unit_position(source_a, 10.0, 10.0)
    _set_unit_position(source_b, 11.0, 11.0)
    _set_unit_position(target, 14.0, 10.0)
    _destroy_models(target, 4)
    game.rebuild_entity_registry()

    _publish_command_phase(game, tyr_player, current_player_index=0)
    req_a = _request_for_source(game, source_a)
    req_b = _request_for_source(game, source_b)
    assert req_a is not None
    assert req_b is not None

    opt_a = _pick_option_by_action(req_a, "return")
    assert opt_a is not None
    value_a, apply_a = resolve_decision_value(game, req_a, opt_a.option_id, player_id=tyr_player.id)
    assert apply_a is not None and bool(getattr(apply_a, "ok", False))
    assert isinstance(value_a, dict)
    assert int(value_a.get("return_count", 0) or 0) == 3
    assert len(target.models_lost) == 1

    options_b = tyr_army.tyranids_detachments.feed_the_swarm_options_for_source(
        source_b, game=game, player=tyr_player
    )
    assert options_b == []
    assert len(target.models_lost) == 1


def test_feed_the_swarm_regenerating_monstrosity_allows_second_regeneration():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game("Assimilation Swarm")
    source_a = _make_unit(
        "Harvester A",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    source_b = _make_unit(
        "Harvester B",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    target = _make_unit(
        "Raveners",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
        model_count=3,
    )

    def _regen_monstrosity_check(key: str, **_kwargs) -> bool:
        return str(key or "").strip().lower() == "enhancement_regenerating_monstrosity"

    target._attached_unit_has_active_enhancement = _regen_monstrosity_check

    tyr_army.add_unit(source_a)
    tyr_army.add_unit(source_b)
    tyr_army.add_unit(target)
    _set_unit_position(source_a, 10.0, 10.0)
    _set_unit_position(source_b, 11.0, 10.5)
    _set_unit_position(target, 14.0, 10.0)
    _destroy_models(target, 2)
    game.rebuild_entity_registry()

    _publish_command_phase(game, tyr_player, current_player_index=0)
    req_a = _request_for_source(game, source_a)
    req_b = _request_for_source(game, source_b)
    assert req_a is not None
    assert req_b is not None

    opt_a = _pick_option_by_action(req_a, "return")
    opt_b = _pick_option_by_action(req_b, "return")
    assert opt_a is not None
    assert opt_b is not None

    value_a, apply_a = resolve_decision_value(game, req_a, opt_a.option_id, player_id=tyr_player.id)
    assert apply_a is not None and bool(getattr(apply_a, "ok", False))
    assert int(value_a.get("return_count", 0) or 0) == 1

    value_b, apply_b = resolve_decision_value(game, req_b, opt_b.option_id, player_id=tyr_player.id)
    assert apply_b is not None and bool(getattr(apply_b, "ok", False))
    assert int(value_b.get("return_count", 0) or 0) == 1
    assert len(target.models_lost) == 0


def test_feed_the_swarm_biophagic_flow_extends_range_to_nine():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game("Assimilation Swarm")
    source = _make_unit(
        "Harvester",
        keywords=["MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    target = _make_unit(
        "Genestealers",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    target.models[0].wounds = 1
    tyr_army.add_unit(source)
    tyr_army.add_unit(target)
    _set_unit_position(source, 10.0, 10.0)
    _set_unit_position(target, 18.0, 10.0)

    mgr = tyr_army.tyranids_detachments
    options_without_flow = mgr.feed_the_swarm_options_for_source(source, game=game, player=tyr_player)
    assert options_without_flow == []

    bearer = _make_unit(
        "Biophagic Bearer",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="4",
    )

    def _biophagic_check(key: str, **_kwargs) -> bool:
        return str(key or "").strip().lower() == "enhancement_biophagic_flow"

    bearer._attached_unit_has_active_enhancement = _biophagic_check
    tyr_army.add_unit(bearer)
    _set_unit_position(bearer, 12.0, 10.0)

    options_with_flow = mgr.feed_the_swarm_options_for_source(source, game=game, player=tyr_player)
    assert any(str(option.get("action", "")).lower() == "heal" for option in options_with_flow)
    assert all(float(option.get("range", 0.0) or 0.0) >= 9.0 for option in options_with_flow)
