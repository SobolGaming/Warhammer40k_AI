from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        base_size: str = "32mm",
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "9" if "MONSTER" in set(self.keywords) else "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": str(base_size),
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
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    tyr_army = Army("Tyranids", "Subterranean Assault")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    enemy_player.command_points = 10
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_move_request(game: Game, unit: Unit, placement_kind: str):
    unit_id = str(get_entity_id(unit) or "")
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(DECISION_MOVE_UNIT):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("placement_kind", "") or "") != str(placement_kind):
            continue
        if str(context.get("unit_id", "") or "") != unit_id:
            continue
        return request
    return None


def test_subterranean_assault_stratagem_descriptors_registered():
    expected = {
        "000010148002": ("Adaptive Optimisation", "grant_synapse_keyword"),
        "000010148003": ("Replenishing Swarms", "heal_or_return_destroyed_wounds_one_models"),
        "000010148004": ("Enfilading Emergence", "grant_keywords_to_all_weapons"),
        "000010148005": ("Tunnel Network", "redeploy_via_other_tunnel_marker"),
        "000010148006": ("Swarming Assault", "grant_charge_reroll_aura"),
        "000010148007": ("Retreat Below", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_id.effect) == expected_effect
        assert str(by_name.name) == expected_name


def test_adaptive_optimisation_grants_synapse_until_next_command_phase():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    tyr_army.add_unit(trygon)
    _deploy_unit(game, trygon, 20.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    assert not trygon.has_any_keyword("SYNAPSE")
    assert not trygon.models[0].has_any_keyword("SYNAPSE")

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use("ADAPTIVE OPTIMISATION", unit=trygon, phase_name="Command phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert trygon.has_any_keyword("SYNAPSE")
    assert trygon.models[0].has_any_keyword("SYNAPSE")
    assert bool(trygon.special_rules.get("tyranids_subterranean_adaptive_optimisation_active")) is True

    game.turn = 2
    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    assert not trygon.has_any_keyword("SYNAPSE")
    assert not trygon.models[0].has_any_keyword("SYNAPSE")
    assert bool(trygon.special_rules.get("tyranids_subterranean_adaptive_optimisation_active", False)) is False


def test_replenishing_swarms_heals_damaged_model():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    warriors = _make_unit(
        "Tyranid Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=3,
        model_count=2,
    )
    tyr_army.add_unit(trygon)
    tyr_army.add_unit(warriors)
    _deploy_unit(game, trygon, 20.0, 20.0)
    _deploy_unit(game, warriors, 24.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    marker = tyr_army.tyranids_detachments.place_tunnel_marker_at(game=game, unit=trygon, x=20.0, y=20.0)
    assert marker is not None
    target_model = warriors.models[0]
    target_model.wounds = 1

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_tyranids.dice_module.get_roll", return_value=2):
        ok = tyr_player.stratagems.use(
            "REPLENISHING SWARMS",
            unit=warriors,
            target_model=target_model,
            action="heal",
            phase_name="Movement phase",
        )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert int(target_model.wounds or 0) == 3


def test_replenishing_swarms_returns_destroyed_wounds_one_models():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    gaunts = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=1,
        model_count=3,
    )
    tyr_army.add_unit(trygon)
    tyr_army.add_unit(gaunts)
    _deploy_unit(game, trygon, 20.0, 20.0)
    _deploy_unit(game, gaunts, 24.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    marker = tyr_army.tyranids_detachments.place_tunnel_marker_at(game=game, unit=trygon, x=20.0, y=20.0)
    assert marker is not None
    destroyed_model = gaunts.models.pop()
    destroyed_model.wounds = 0
    gaunts.models_lost.append(destroyed_model)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_tyranids.dice_module.get_roll", return_value=1):
        ok = tyr_player.stratagems.use(
            "REPLENISHING SWARMS",
            unit=gaunts,
            action="return",
            phase_name="Movement phase",
        )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert destroyed_model in list(gaunts.models or [])
    assert destroyed_model not in list(gaunts.models_lost or [])
    assert int(destroyed_model.wounds or 0) == 1


def test_enfilading_emergence_grants_weapon_keywords_until_fight_phase_end():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    raveners = _make_unit(
        "Raveners",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=3,
        model_count=2,
    )
    raveners.arrived_from_reserves_this_turn = True
    raveners.models[0].wargear = [SimpleNamespace(id="devourer-1", name="Devourer", is_ranged=lambda: True)]
    raveners.models[1].wargear = [SimpleNamespace(id="claws-1", name="Ravener Claws", is_melee=lambda: True)]
    tyr_army.add_unit(raveners)
    _deploy_unit(game, raveners, 20.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("ENFILADING EMERGENCE", unit=raveners, phase_name="Movement phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9

    ranged_bonuses = list(raveners.models[0].get_temporary_weapon_keyword_bonuses("Devourer") or [])
    melee_bonuses = list(raveners.models[1].get_temporary_weapon_keyword_bonuses("Ravener Claws") or [])
    assert {
        str(entry.get("keyword", "") or "").strip().upper() for entry in ranged_bonuses
    } == {"SUSTAINED HITS 1", "IGNORES COVER"}
    assert {
        str(entry.get("keyword", "") or "").strip().upper() for entry in melee_bonuses
    } == {"SUSTAINED HITS 1", "IGNORES COVER"}

    game.event_system.publish("phase_end", player=tyr_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(raveners.models[0].get_temporary_weapon_keyword_bonuses("Devourer") or []) == []
    assert list(raveners.models[1].get_temporary_weapon_keyword_bonuses("Ravener Claws") or []) == []
    assert bool(raveners.special_rules.get("tyranids_enfilading_emergence_active", False)) is False


def test_tunnel_network_queues_move_and_redeploys_by_other_tunnel_marker():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    source_trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    destination_mawloc = _make_unit(
        "Mawloc",
        keywords=["MONSTER", "MAWLOC"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    raveners = _make_unit(
        "Raveners",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=3,
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=2,
    )
    tyr_army.add_unit(source_trygon)
    tyr_army.add_unit(destination_mawloc)
    tyr_army.add_unit(raveners)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source_trygon, 20.0, 20.0)
    _deploy_unit(game, destination_mawloc, 40.0, 20.0)
    _deploy_unit(game, raveners, 24.0, 20.0)
    _deploy_unit(game, enemy, 54.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    source_marker = tyr_army.tyranids_detachments.place_tunnel_marker_at(game=game, unit=source_trygon, x=20.0, y=20.0)
    destination_marker = tyr_army.tyranids_detachments.place_tunnel_marker_at(
        game=game,
        unit=destination_mawloc,
        x=40.0,
        y=20.0,
    )
    assert source_marker is not None
    assert destination_marker is not None

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("TUNNEL NETWORK", unit=raveners, phase_name="Movement phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert raveners not in list(game.map.units or [])
    assert raveners.deployed is False

    request = _find_move_request(game, raveners, "subterranean_tunnel_network")
    assert request is not None
    assert list(request.context.get("tunnel_marker_allowed_ids") or []) == [str(destination_marker.marker_id)]

    confirm_option = list(request.options or [None])[0]
    assert confirm_option is not None
    result = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": str(get_entity_id(raveners.models[0]) or ""),
                    "position": [44.5, 20.0, 0.0],
                    "facing": 0.0,
                },
                {
                    "model_id": str(get_entity_id(raveners.models[1]) or ""),
                    "position": [46.0, 20.0, 0.0],
                    "facing": 0.0,
                },
            ]
        },
        player_id=tyr_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    assert raveners in list(game.map.units or [])
    assert raveners.deployed is True
    assert str(getattr(raveners, "reserve_status", "") or "") == "deployed"


def test_swarming_assault_grants_charge_rerolls_until_charge_phase_end():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    warriors = _make_unit(
        "Tyranid Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=3,
        model_count=2,
    )
    trygon.arrived_from_reserves_this_turn = True
    tyr_army.add_unit(trygon)
    tyr_army.add_unit(warriors)
    _deploy_unit(game, trygon, 20.0, 20.0)
    _deploy_unit(game, warriors, 24.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, tyr_player, "CHARGE_PHASE", 0)
    assert bool(warriors.can_reroll_charge_roll(game=game)) is False

    ok = tyr_player.stratagems.use("SWARMING ASSAULT", unit=trygon, phase_name="Charge phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert bool(warriors.can_reroll_charge_roll(game=game)) is True

    game.event_system.publish("phase_end", player=tyr_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert bool(warriors.can_reroll_charge_roll(game=game)) is False


def test_retreat_below_queues_at_opponent_fight_phase_end_and_moves_two_burrowers():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    trygon = _make_unit(
        "Trygon",
        keywords=["MONSTER", "TRYGON"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    mawloc = _make_unit(
        "Mawloc",
        keywords=["MONSTER", "MAWLOC"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
        base_size="80mm",
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=2,
    )
    tyr_army.add_unit(trygon)
    tyr_army.add_unit(mawloc)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, trygon, 20.0, 20.0)
    _deploy_unit(game, mawloc, 30.0, 20.0)
    _deploy_unit(game, enemy, 50.0, 20.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(tyr_player.stratagems, "RETREAT BELOW")
    assert pending is not None
    assert int(pending.get("max_units", 0) or 0) == 2

    ok = tyr_player.stratagems.use(
        "RETREAT BELOW",
        units=[trygon, mawloc],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert str(getattr(trygon, "reserve_status", "") or "") == "strategic_reserves"
    assert str(getattr(mawloc, "reserve_status", "") or "") == "strategic_reserves"
    assert trygon not in list(game.map.units or [])
    assert mawloc not in list(game.map.units or [])
