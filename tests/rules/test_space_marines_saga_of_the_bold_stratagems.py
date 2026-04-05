from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_CHARGE, DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        model_name: str = "Test Model",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": str(model_name),
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
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
    model_count: int = 1,
    model_name: str = "Test Model",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            model_name=model_name,
        )
    )


def _melee_wargear(name: str = "Frost Claws") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.turn = 1
    sm_army = Army("Space Marines", "Saga of the Bold")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 0.1), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _target_option_id(request, target: Unit) -> str | None:
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    return None


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def test_saga_of_the_bold_stratagem_descriptors_exist():
    expected = {
        "000010266002": ("Inspiring Presence", "grant_keywords_to_melee_weapons"),
        "000010266003": ("Champion's Guidance", "phase_hit_reroll"),
        "000010266004": ("Birth of a Saga", "temporary_model_character_keyword_and_unit_character_status"),
        "000010266005": ("Alpha Strike", "charge_after_advance"),
        "000010266006": ("Heroic Resolve", "defensive_damage_reduction"),
        "000010266007": ("Countercharge", "out_of_turn_charge_without_charge_bonus"),
    }

    for stratagem_id, (name, effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect


def test_alpha_strike_allows_charge_after_advance_until_phase_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    character = _make_unit(
        "Wolf Lord",
        keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(character)
    _deploy_unit(game, character, 10.0, 10.0)
    game.rebuild_entity_registry()

    character.round_state.advanced_this_round = True
    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    assert character.can_charge_after_advance() is False

    ok = sm_player.stratagems.use("ALPHA STRIKE", unit=character, phase_name="Charge phase")
    assert ok
    assert character.can_charge_after_advance() is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert character.can_charge_after_advance() is False


def test_birth_of_a_saga_grants_and_cleans_character_keyword():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    manager = sm_army.space_marines_detachments
    headtakers = _make_unit(
        "Wolf Guard Headtakers",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        model_name="Wolf Guard Headtaker",
    )
    sm_army.add_unit(headtakers)
    _deploy_unit(game, headtakers, 10.0, 10.0)
    game.rebuild_entity_registry()

    headtaker_model = headtakers.models[0]
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)

    ok = sm_player.stratagems.use(
        "BIRTH OF A SAGA",
        unit=headtakers,
        model=headtaker_model,
        phase_name="Command phase",
    )
    assert ok

    assert "CHARACTER" in list(getattr(headtaker_model, "keywords", []) or [])
    sr = dict(getattr(headtakers, "special_rules", {}) or {})
    assert bool(sr.get("space_marines_birth_of_a_saga_active")) is True
    assert bool(manager._attached_unit_has_keyword(headtakers, "CHARACTER")) is True

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)

    assert "CHARACTER" not in list(getattr(headtaker_model, "keywords", []) or [])
    sr_after = dict(getattr(headtakers, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_birth_of_a_saga_active", False)) is False
    assert bool(manager._attached_unit_has_keyword(headtakers, "CHARACTER")) is False


def test_champions_guidance_grants_full_hit_rerolls_for_shooting():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    character = _make_unit(
        "Wolf Lord",
        keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(character)
    enemy_army.add_unit(target)
    _deploy_unit(game, character, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)
    game.rebuild_entity_registry()

    model = character.models[0]
    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("CHAMPION'S GUIDANCE", unit=character, phase_name="Shooting phase")
    assert ok

    mods = character.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=model)
    assert bool(mods.get("reroll_hit_full")) is True
    assert any("guidance" in str(reason).lower() for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_champions_guidance_grants_full_hit_rerolls_in_opponent_fight_phase():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    character = _make_unit(
        "Wolf Lord",
        keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(character)
    enemy_army.add_unit(target)
    _deploy_unit(game, character, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)
    game.rebuild_entity_registry()

    model = character.models[0]
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use("CHAMPION'S GUIDANCE", unit=character, phase_name="Fight phase")
    assert ok

    mods = character.get_unit_hit_reroll_modifiers("melee", target=target, attacker_model=model)
    assert bool(mods.get("reroll_hit_full")) is True
    assert any("guidance" in str(reason).lower() for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_inspiring_presence_grants_lethal_hits_to_melee_weapons():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    character = _make_unit(
        "Wolf Lord",
        keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(character)
    _deploy_unit(game, character, 10.0, 10.0)
    game.rebuild_entity_registry()

    model = character.models[0]
    weapon = _melee_wargear()
    model.wargear = [weapon]

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    ok = sm_player.stratagems.use("INSPIRING PRESENCE", unit=character, phase_name="Fight phase")
    assert ok

    bonuses = list(model.get_temporary_weapon_keyword_bonuses("Frost Claws") or [])
    assert bonuses
    assert any(str(bonus.get("keyword", "") or "").upper() == "LETHAL HITS" for bonus in bonuses)


def test_countercharge_queues_reaction_and_declares_out_of_turn_charge_without_charge_bonus():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    character = _make_unit(
        "Wolf Lord",
        keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(character)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, character, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 15.0, 10.0)
    _deploy_unit(game, enemy_b, 10.0, 15.0)
    game.rebuild_entity_registry()
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    pending = _pending_by_name(sm_player.stratagems, "COUNTERCHARGE")
    assert pending is not None

    ok = sm_player.stratagems.use("COUNTERCHARGE", unit=character, phase_name="Charge phase")
    assert ok

    request = _first_request(game, DECISION_DECLARE_CHARGE)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert bool(ctx.get("out_of_turn")) is True
    assert bool(ctx.get("count_as_charged")) is False
    assert str(ctx.get("charge_retarget_reason", "") or "") == "space_marines_countercharge"

    enemy_a_id = str(get_entity_id(enemy_a) or "")
    enemy_b_id = str(get_entity_id(enemy_b) or "")
    option_id = _target_option_id(request, enemy_a)
    assert option_id

    result = resolve_decision_command(
        game,
        request,
        option_id,
        result_payload={"target_unit_ids": [enemy_a_id, enemy_b_id]},
        player_id=sm_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    apply_result = getattr(result, "value", None)
    declared = getattr(apply_result, "value", None)
    assert isinstance(declared, dict)
    assert bool(declared.get("count_as_charged", True)) is False
    assert set(list(declared.get("target_unit_ids", []) or [])) == {enemy_a_id, enemy_b_id}

    roll_request = _first_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_ctx = dict(getattr(roll_request, "context", {}) or {})
    roll_spec = dict(roll_ctx.get("roll_spec", {}) or {})
    assert set(list(roll_spec.get("target_unit_ids", []) or [])) == {enemy_a_id, enemy_b_id}
