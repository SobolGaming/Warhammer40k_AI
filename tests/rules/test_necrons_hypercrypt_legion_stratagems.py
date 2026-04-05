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
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        base_size: str = "32mm",
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "8" if "VEHICLE" in set(self.keywords) else "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": str(base_size),
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        normalized_abilities = []
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized_abilities.append(entry)
        self.datasheets_abilities = normalized_abilities
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
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
            abilities=abilities,
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
    game.turn = 2

    necron_army = Army("Necrons", "Hypercrypt Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)

    necron_player.command_points = 10
    enemy_player.command_points = 10
    return game, necron_player, enemy_player, necron_army, enemy_army


def _reanimation_ability():
    return [{"name": "Reanimation Protocols", "description": "", "type": "Datasheet", "parameter": ""}]


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
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(DECISION_MOVE_UNIT):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("placement_kind", "") or "") != str(placement_kind):
            continue
        if str(ctx.get("unit_id", "") or "") != unit_id:
            continue
        return req
    return None


def test_hypercrypt_legion_stratagem_descriptors_registered():
    expected = {
        "000008555002": ("Hyperphasic Recall", "remove_and_set_up_within_monolith_range"),
        "000008555003": ("Quantum Deflection", "grant_invulnerable_save"),
        "000008555004": ("Reanimation Crypts", "trigger_reanimation_protocols_for_all_reserve_units"),
        "000008555005": ("Cosmic Precision", "deep_strike_min_distance_override_with_no_charge"),
        "000008555006": ("Dimensional Corridor", "allow_charge_after_eternity_gate"),
        "000008555007": ("Entropic Damping", "attacker_ranged_weapons_become_hazardous_against_target"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_dimensional_corridor_allows_charge_after_eternity_gate():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    monolith = _make_unit("Monolith", keywords=["NECRONS", "MONOLITH", "VEHICLE"], wounds=20, base_size="100mm")
    lychguard = _make_unit(
        "Lychguard",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(monolith)
    necron_army.add_unit(lychguard)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, monolith, 10.0, 10.0)
    _deploy_unit(game, lychguard, 18.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    lychguard.special_rules["eternity_gate_no_charge_turn_owner"] = necron_player.id
    lychguard.special_rules["eternity_gate_no_charge_turn"] = int(game.turn)
    lychguard.special_rules["eternity_gate_anchor_unit_id"] = str(get_entity_id(monolith) or "")

    _set_phase(game, necron_player, "CHARGE_PHASE", 0)
    assert lychguard.can_declare_charge_against(enemy, game) is False

    ok = necron_player.stratagems.use("DIMENSIONAL CORRIDOR", unit=lychguard, phase_name="Charge phase")
    assert ok is True
    assert int(necron_player.command_points or 0) == 8
    assert lychguard.can_declare_charge_against(enemy, game) is True


def test_quantum_deflection_queues_and_grants_invulnerable_save():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    ark = _make_unit("Ghost Ark", keywords=["VEHICLE"], faction_keywords=["NECRONS"], wounds=14, base_size="100mm")
    infantry = _make_unit("Necron Warriors", keywords=["INFANTRY"], faction_keywords=["NECRONS"])
    attacker = _make_unit(
        "Enemy Attackers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(ark)
    necron_army.add_unit(infantry)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, ark, 10.0, 10.0)
    _deploy_unit(game, infantry, 16.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[ark, infantry])

    pending = _pending_by_name(necron_player.stratagems, "QUANTUM DEFLECTION")
    assert pending is not None
    assert ark in list(pending.get("candidates") or [])
    assert infantry not in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use("QUANTUM DEFLECTION", unit=ark, phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    inv_value, inv_source = ark.models[0].get_temporary_invulnerable_save()
    assert int(inv_value or 0) == 4
    assert "QUANTUM DEFLECTION" in str(inv_source or "").upper()


def test_entropic_damping_queues_and_marks_attacks_as_hazardous():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    tesseract = _make_unit(
        "Tesseract Vault",
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["NECRONS"],
        wounds=24,
        base_size="160mm",
    )
    ark = _make_unit("Ghost Ark", keywords=["VEHICLE"], faction_keywords=["NECRONS"], wounds=14, base_size="100mm")
    attacker = _make_unit(
        "Enemy Guns",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(tesseract)
    necron_army.add_unit(ark)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, tesseract, 10.0, 10.0)
    _deploy_unit(game, ark, 18.0, 10.0)
    _deploy_unit(game, attacker, 25.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[tesseract, ark])

    pending = _pending_by_name(necron_player.stratagems, "ENTROPIC DAMPING")
    assert pending is not None
    assert tesseract in list(pending.get("candidates") or [])
    assert ark not in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use("ENTROPIC DAMPING", unit=tesseract, phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert bool(tesseract.special_rules.get("shooting_phase_ranged_hazardous_active"))
    assert str(tesseract.special_rules.get("shooting_phase_ranged_hazardous_owner", "") or "") == enemy_player.id


def test_reanimation_crypts_triggers_reanimation_for_each_reserve_unit():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    warlord = _make_unit("Overlord", keywords=["CHARACTER", "INFANTRY"], faction_keywords=["NECRONS"])
    reserve_one = _make_unit(
        "Reserve Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    reserve_two = _make_unit(
        "Reserve Immortals",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    battlefield_unit = _make_unit(
        "Battlefield Unit",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    reserve_one.deployed = False
    reserve_one.reserve_status = "reserves"
    reserve_two.deployed = False
    reserve_two.reserve_status = "reserves"
    battlefield_unit.deployed = True
    battlefield_unit.reserve_status = "deployed"
    warlord.is_warlord = True
    necron_army.warlord = warlord
    necron_army.add_unit(warlord)
    necron_army.add_unit(reserve_one)
    necron_army.add_unit(reserve_two)
    necron_army.add_unit(battlefield_unit)
    _deploy_unit(game, warlord, 10.0, 10.0)
    _deploy_unit(game, battlefield_unit, 14.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "COMMAND_PHASE", 0)
    with patch.object(reserve_one, "apply_reanimation_protocols") as rp_one, patch.object(
        reserve_two, "apply_reanimation_protocols"
    ) as rp_two:
        with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", side_effect=[2, 3]):
            ok = necron_player.stratagems.use("REANIMATION CRYPTS", unit=warlord, phase_name="Command phase")
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    rp_one.assert_called_once()
    rp_two.assert_called_once()
    reanimation_rolls = sorted([int(rp_one.call_args.args[0]), int(rp_two.call_args.args[0])])
    assert reanimation_rolls == [2, 3]
    assert str(rp_one.call_args.kwargs.get("roll_expr", "") or "") == "D3"


def test_hyperphasic_recall_queues_after_enemy_shooting_and_redeploys():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    monolith = _make_unit("Monolith", keywords=["MONOLITH", "VEHICLE"], faction_keywords=["NECRONS"], wounds=20, base_size="100mm")
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Attackers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(monolith)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, monolith, 20.0, 20.0)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, attacker, 40.0, 20.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    destroyed_model = warriors.models[0]
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        killing_models_by_target={warriors: [destroyed_model]},
    )

    pending = _pending_by_name(necron_player.stratagems, "HYPERPHASIC RECALL")
    assert pending is not None
    assert warriors in list(pending.get("candidates") or [])
    assert monolith in list(pending.get("monolith_candidates") or [])

    ok = necron_player.stratagems.use(
        "HYPERPHASIC RECALL",
        unit=warriors,
        monolith_unit=monolith,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 8
    assert warriors not in list(game.map.units or [])
    assert warriors.deployed is False

    request = _find_move_request(game, warriors, "hyperphasic_recall")
    assert request is not None
    assert str(request.context.get("reserves_arrival_anchor_unit_id", "") or "") == str(get_entity_id(monolith) or "")
    confirm_option = list(request.options or [None])[0]
    assert confirm_option is not None

    result = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": str(get_entity_id(warriors.models[0]) or ""),
                    "position": [23.0, 20.0, 0.0],
                    "facing": 0.0,
                },
                {
                    "model_id": str(get_entity_id(warriors.models[1]) or ""),
                    "position": [24.5, 20.0, 0.0],
                    "facing": 0.0,
                },
            ]
        },
        player_id=necron_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    assert warriors in list(game.map.units or [])
    assert warriors.deployed is True
    assert str(getattr(warriors, "reserve_status", "") or "") == "deployed"
    assert bool(getattr(warriors, "arrived_from_reserves_this_turn", False)) is False


def test_hyperphasic_recall_queues_after_enemy_fight_kills_models():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    monolith = _make_unit("Monolith", keywords=["MONOLITH", "VEHICLE"], faction_keywords=["NECRONS"], wounds=20, base_size="100mm")
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(monolith)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, monolith, 20.0, 20.0)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "fight_attacks_resolved",
        unit=attacker,
        target_unit=warriors,
        killing_models_by_target={warriors: [warriors.models[0]]},
    )

    pending = _pending_by_name(necron_player.stratagems, "HYPERPHASIC RECALL")
    assert pending is not None
    assert str(pending.get("event", "") or "") == "fight_attacks_resolved"
    assert warriors in list(pending.get("candidates") or [])
    assert monolith in list(pending.get("monolith_candidates") or [])
