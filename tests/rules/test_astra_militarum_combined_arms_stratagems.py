from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        base_size: str = "32mm",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _ability(name: str, description: str = "", ability_type: str = "Ability") -> dict:
    return {
        "name": name,
        "description": description,
        "type": ability_type,
        "parameter": "",
    }


def _voice_of_command_abilities(order_text: str) -> list[dict]:
    return [
        _ability("Voice of Command", "Voice of Command"),
        _ability("Orders", order_text),
    ]


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords or ["ASTRA MILITARUM"],
            abilities=abilities,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    return unit


def _build_game(*, am_control: PlayerControl = PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", "Combined Arms")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=am_control, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    am_player.command_points = 5
    enemy_player.command_points = 5
    am_army.configure_rule_managers(force=True)
    am_player.stratagems.refresh_available()
    return game, am_player, enemy_player, am_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _option_id_for_payload(request, key: str, value: str) -> str:
    wanted = str(value or "").strip()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "").strip() == wanted:
            return str(getattr(option, "option_id", "") or "")
    return ""


def test_combined_arms_stratagem_descriptors_registered():
    expected = {
        "000008381002": ("Coordinated Action", "shared_orders_between_two_units"),
        "000008381003": ("Reinforcements!", "clone_unit_to_strategic_reserves"),
        "000008381004": ("Flexible Command", "expanded_order_target_keywords"),
        "000008381005": ("Fields of Fire", "paired_target_ap_bonus"),
        "000008381006": ("Inspired Command", "issue_order_as_if_command_phase"),
        "000008381007": ("Stalwart Protector", "vehicle_grants_cover_to_infantry"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == expected_name
        assert str(getattr(desc, "effect", "") or "") == expected_effect


def test_flexible_command_allows_regiment_officer_to_target_squadron():
    from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE

    game, am_player, _enemy_player, am_army, _enemy_army = _build_game()
    officer = _make_unit(
        "Command Squad",
        keywords=["OFFICER", "REGIMENT"],
        abilities=_voice_of_command_abilities("This model can issue 1 order to REGIMENT units within 6\"."),
    )
    regiment = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY"])
    squadron = _make_unit("Scout Sentinel", keywords=["SQUADRON", "VEHICLE"])
    am_army.add_unit(officer)
    am_army.add_unit(regiment)
    am_army.add_unit(squadron)
    _deploy_unit(game, officer, 10.0, 10.0)
    _deploy_unit(game, regiment, 12.0, 10.0)
    _deploy_unit(game, squadron, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    before = list(am_army.voice_of_command.get_eligible_targets(officer, game=game, order_key=ORDER_MOVE.key) or [])
    assert regiment in before
    assert squadron not in before

    assert am_player.stratagems.use("FLEXIBLE COMMAND", phase_name="Command phase")
    after = list(am_army.voice_of_command.get_eligible_targets(officer, game=game, order_key=ORDER_MOVE.key) or [])
    assert regiment in after
    assert squadron in after
    assert int(am_player.command_points or 0) == 3


def test_inspired_command_remote_payload_issues_order_in_opponent_command_phase():
    from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE

    game, am_player, enemy_player, am_army, _enemy_army = _build_game(am_control=PlayerControl.REMOTE)
    officer = _make_unit(
        "Castellan",
        keywords=["OFFICER", "REGIMENT"],
        abilities=_voice_of_command_abilities("This model can issue 1 order to REGIMENT units within 6\"."),
    )
    target = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY"])
    am_army.add_unit(officer)
    am_army.add_unit(target)
    _deploy_unit(game, officer, 10.0, 10.0)
    _deploy_unit(game, target, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert am_player.stratagems.use(
        "INSPIRED COMMAND",
        officer_unit=officer,
        order_target_unit=target,
        order_key=ORDER_MOVE.key,
        phase_name="Command phase",
    )
    assert ORDER_MOVE.key in list(am_army.voice_of_command.get_active_order_keys(target) or [])
    assert int(am_player.command_points or 0) == 4


def test_coordinated_action_local_selection_queues_and_mirrors_orders():
    from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE

    game, am_player, _enemy_player, am_army, _enemy_army = _build_game(am_control=PlayerControl.LOCAL)
    officer = _make_unit(
        "Platoon Commander",
        keywords=["OFFICER", "REGIMENT"],
        abilities=_voice_of_command_abilities("This model can issue 1 order to REGIMENT units within 6\"."),
    )
    regiment = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY"])
    squadron = _make_unit("Leman Russ", keywords=["SQUADRON", "VEHICLE"], base_size="100mm")
    am_army.add_unit(officer)
    am_army.add_unit(regiment)
    am_army.add_unit(squadron)
    _deploy_unit(game, officer, 8.0, 10.0)
    _deploy_unit(game, regiment, 10.0, 10.0)
    _deploy_unit(game, squadron, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    assert am_player.stratagems.use("COORDINATED ACTION", phase_name="Command phase")
    assert int(am_player.command_points or 0) == 5

    queued = list(game.decision_queue.list() or [])
    first_request = next(
        req for req in queued
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "combined_arms_coordinated_action_regiment"
    )
    assert str(getattr(first_request, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    assert str((first_request.context or {}).get("ability", "") or "") == "combined_arms_coordinated_action_regiment"
    regiment_option_id = _option_id_for_payload(first_request, "regiment_unit_id", str(get_entity_id(regiment) or ""))
    assert regiment_option_id
    resolve_decision_command(game, first_request, regiment_option_id, player_id=am_player.id)

    queued = list(game.decision_queue.list() or [])
    second_request = next(
        req for req in queued
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "combined_arms_coordinated_action_squadron"
    )
    assert str((second_request.context or {}).get("ability", "") or "") == "combined_arms_coordinated_action_squadron"
    squadron_option_id = _option_id_for_payload(second_request, "squadron_unit_id", str(get_entity_id(squadron) or ""))
    assert squadron_option_id
    resolve_decision_command(game, second_request, squadron_option_id, player_id=am_player.id)

    assert int(am_player.command_points or 0) == 4
    assert am_army.voice_of_command.issue_order(game, officer, regiment, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert ORDER_MOVE.key in list(am_army.voice_of_command.get_active_order_keys(regiment) or [])
    assert ORDER_MOVE.key in list(am_army.voice_of_command.get_active_order_keys(squadron) or [])


def test_fields_of_fire_applies_bonus_only_against_selected_enemy():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    regiment = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY"])
    squadron = _make_unit("Leman Russ", keywords=["SQUADRON", "VEHICLE"])
    enemy_marked = _make_unit("Enemy Marked", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(regiment)
    am_army.add_unit(squadron)
    enemy_army.add_unit(enemy_marked)
    enemy_army.add_unit(enemy_other)
    _deploy_unit(game, regiment, 10.0, 10.0)
    _deploy_unit(game, squadron, 14.0, 10.0)
    _deploy_unit(game, enemy_marked, 20.0, 10.0)
    _deploy_unit(game, enemy_other, 24.0, 10.0)
    game.rebuild_entity_registry()

    weapon = Wargear(
        {
            "name": "Battle Cannon",
            "type": "Ranged",
            "range": "48",
            "A": "1",
            "BS_WS": "4+",
            "S": "10",
            "AP": "0",
            "D": "3",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    assert am_player.stratagems.use(
        "FIELDS OF FIRE",
        regiment_unit=regiment,
        squadron_unit=squadron,
        enemy_unit=enemy_marked,
        phase_name="Shooting phase",
    )
    assert int(profile.get_effective_ap(regiment.models[0], enemy_marked) or 0) == -1
    assert int(profile.get_effective_ap(squadron.models[0], enemy_marked) or 0) == -1
    assert int(profile.get_effective_ap(regiment.models[0], enemy_other) or 0) == 0
    assert int(profile.get_effective_ap(squadron.models[0], enemy_other) or 0) == 0


def test_stalwart_protector_reaction_grants_cover():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    infantry = _make_unit("Shock Troops", keywords=["REGIMENT", "INFANTRY"])
    vehicle = _make_unit("Chimera", keywords=["VEHICLE", "SQUADRON"], base_size="100mm")
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(infantry)
    am_army.add_unit(vehicle)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, vehicle, 15.0, 10.0)
    _deploy_unit(game, infantry, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[infantry])
    pending = _pending_by_name(am_player.stratagems, "STALWART PROTECTOR")
    assert pending is not None

    assert am_player.stratagems.use("STALWART PROTECTOR", unit=vehicle, phase_name="Shooting phase", dequeue=True)
    bonus = game.map.get_selfless_protector_bonus_for_ranged_attack(
        attacking_unit=attacker,
        target_model=infantry.models[0],
        protector_units=[vehicle],
    )
    assert bool(bonus.get("applies"))
    assert bool(bonus.get("grants_benefit_of_cover"))
    assert bonus.get("source_unit") is vehicle


def test_reinforcements_replaces_destroyed_unit_once_per_battle():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    destroyed = _make_unit("Infantry Squad", keywords=["REGIMENT", "INFANTRY"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(destroyed)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "FIGHT_PHASE", 0)
    game.map.units.remove(destroyed)
    destroyed.is_alive = lambda: False
    existing_ids = {id(entry) for entry in list(am_army.units or [])}

    game.event_system.publish("unit_destroyed", unit=destroyed, destroyed_by_unit=enemy)
    pending = _pending_by_name(am_player.stratagems, "REINFORCEMENTS!")
    assert pending is not None
    assert am_player.stratagems.use("REINFORCEMENTS!", destroyed_unit=destroyed, phase_name="Fight phase", dequeue=True)

    replacements = [entry for entry in list(am_army.units or []) if id(entry) not in existing_ids]
    assert len(replacements) == 1
    replacement = replacements[0]
    assert replacement is not destroyed
    assert str(getattr(replacement, "reserve_status", "") or "") == "strategic_reserves"
    assert bool(replacement.is_in_reserves())
    assert bool(replacement.is_alive())

    am_player.stratagems._used_stratagems_this_phase.clear()
    assert not am_player.stratagems.use("REINFORCEMENTS!", destroyed_unit=destroyed, phase_name="Fight phase")
