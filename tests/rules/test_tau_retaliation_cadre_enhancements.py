from __future__ import annotations

import types
import uuid
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_REQUEST_DICE_ROLL,
)
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
        faction_name: str = "T'au Empire",
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
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "50mm",
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


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool = True):
        self._id = str(uuid.uuid4())
        self.name = name
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


def _make_unit(
    name: str,
    *,
    faction_name: str = "T'au Empire",
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


def _apply_starflare(unit: Unit) -> Enhancement:
    enhancement = Enhancement(
        id="000008815005",
        name="Starflare Ignition System",
        faction_id="TAU",
        detachment="Retaliation Cadre",
        points=20,
        description=(
            "T'au Empire Battlesuit model only. At the end of your opponent's turn, if the bearer's unit is not within "
            "Engagement Range of one or more enemy units, you can remove that unit from the battlefield and place it into "
            "Strategic Reserves."
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _apply_internal_grenade_racks(unit: Unit) -> Enhancement:
    enhancement = Enhancement(
        id="000008815002",
        name="Internal Grenade Racks",
        faction_id="TAU",
        detachment="Retaliation Cadre",
        points=20,
        description=(
            "T'au Empire Battlesuit model only. The bearer has the Grenades keyword, and each time the bearer ends a "
            "Normal move, you can select one enemy unit that it moved over during that move. If you do, roll six D6: "
            "for each 4+, that enemy unit suffers 1 mortal wound."
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _apply_prototype_weapon_system(unit: Unit) -> Enhancement:
    enhancement = Enhancement(
        id="000008815003",
        name="Prototype Weapon System",
        faction_id="TAU",
        detachment="Retaliation Cadre",
        points=15,
        description=(
            "T'au Empire Battlesuit model only. Each time the bearer is selected to shoot, select either the "
            "[LETHAL HITS] or [SUSTAINED HITS 1] ability. Until those attacks are resolved, ranged weapons equipped "
            "by the bearer have the selected ability."
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _apply_puretide_engram_neurochip(unit: Unit) -> Enhancement:
    enhancement = Enhancement(
        id="000008815004",
        name="Puretide Engram Neurochip",
        faction_id="TAU",
        detachment="Retaliation Cadre",
        points=25,
        description=(
            "T'au Empire Battlesuit model only. Each time you target the bearer's unit with a Stratagem, roll one D6: "
            "on a 4+, you gain 1CP."
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army.with_detachment("T'au Empire", "Retaliation Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tau_player = Player("T'au", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, tau_army, enemy_army, tau_player, enemy_player


def _bearer_model(unit: Unit):
    return list(getattr(unit, "models", []) or [])[0]


def _resolve_yes_option(game: Game, request, *, player_id: str) -> None:
    yes_option_id = ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            yes_option_id = str(getattr(option, "option_id", "") or "")
            break
    assert yes_option_id
    result = resolve_decision_command(game, request, yes_option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _resolve_optional_reroll(game: Game, *, player_id: str) -> None:
    pending = list(game.decision_queue.list() or [])
    for req in pending:
        if str(getattr(req, "decision_type", "") or "") != "SELECT_DICE_REROLL":
            continue
        option_id = ""
        for option in list(getattr(req, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("action_id", "") or "") == "none":
                option_id = str(getattr(option, "option_id", "") or "")
                break
        if not option_id and list(getattr(req, "options", []) or []):
            option_id = str(getattr(req.options[0], "option_id", "") or "")
        if option_id:
            result = resolve_decision_command(game, req, option_id, player_id=player_id)
            assert bool(getattr(result, "ok", False))
        return


def test_retaliation_cadre_enhancements_have_tool_descriptors():
    expected = {
        "000008815002": ("Internal Grenade Racks", "bearer_gains_grenades_and_move_over_mortal_wounds"),
        "000008815003": ("Prototype Weapon System", "choose_bearer_ranged_weapon_keyword_mode"),
        "000008815004": ("Puretide Engram Neurochip", "targeted_stratagem_cp_refund"),
        "000008815005": ("Starflare Ignition System", "end_of_opponent_turn_enter_strategic_reserves_if_not_engaged"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_internal_grenade_racks_adds_grenades_keyword_and_bearer_move_over_spec():
    _game, tau_army, _enemy_army, _tau_player, _enemy_player = _build_game()
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "FLY", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_army.add_unit(source)
    bearer = _bearer_model(source)

    _apply_internal_grenade_racks(source)

    assert source.has_keyword("GRENADES")
    assert bearer.has_keyword("GRENADES")
    specs = source.model_move_over_mortal_wounds_specs(bearer)
    assert len(specs) == 1
    spec = dict(specs[0] or {})
    assert str(spec.get("source", "") or "") == "Internal Grenade Racks"
    assert int(spec.get("dice", 0) or 0) == 6
    assert int(spec.get("threshold", 0) or 0) == 4
    assert int(spec.get("mortal_per_success", 0) or 0) == 1
    assert list(spec.get("move_types", []) or []) == ["move"]


def test_internal_grenade_racks_queues_move_over_target_and_applies_mortals():
    game, tau_army, enemy_army, tau_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.auto_resolve_dice_rolls = False
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "FLY", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(source)
    enemy_army.add_unit(enemy)
    bearer = _bearer_model(source)
    _apply_internal_grenade_racks(source)

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=5.0, y=0.0)
    bearer.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    applied: dict[str, object] = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["target"] = target_unit
        applied["amount"] = int(applied.get("amount", 0) or 0) + int(amount or 0)
        return 0

    source._apply_mortal_wounds_to_unit = types.MethodType(_apply, source)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=source, action="move")

    requests = list(game.decision_queue.list() or [])
    move_request = next(
        req for req in requests if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    )
    assert str((getattr(move_request, "context", {}) or {}).get("mortal_wounds_kind", "") or "") == "move_over"
    enemy_id = str(get_entity_id(enemy) or "")
    option_id = ""
    for option in list(getattr(move_request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == enemy_id:
            option_id = str(getattr(option, "option_id", "") or "")
            break
    assert option_id
    result = resolve_decision_command(game, move_request, option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False))

    roll_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
    )
    roll_id = (getattr(roll_request, "context", {}) or {}).get("roll_id")
    assert roll_id is not None
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = [4, 2, 4, 5, 1, 6]
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 2, 4, 5, 1, 6]):
        result = resolve_decision_command(game, roll_request, roll_request.options[0].option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False))
    _resolve_optional_reroll(game, player_id=tau_player.id)

    assert applied["target"] is enemy
    assert int(applied["amount"] or 0) == 4


def test_prototype_weapon_system_selects_keyword_mode_and_clears_after_shooting():
    game, tau_army, enemy_army, tau_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "FLY", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(source)
    enemy_army.add_unit(enemy)
    bearer = _bearer_model(source)
    bearer.wargear = [
        _DummyWargear("Fusion Blaster", ranged=True),
        _DummyWargear("Plasma Rifle", ranged=True),
        _DummyWargear("Battlesuit Fists", ranged=False),
    ]
    _apply_prototype_weapon_system(source)

    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_prototype_weapon_system(attacking_unit=source, target_units=[enemy])

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    )
    assert str((getattr(request, "context", {}) or {}).get("ability", "") or "") == "prototype_weapon_system"
    choice_keys = {
        str((getattr(option, "payload", {}) or {}).get("choice_key", "") or "")
        for option in list(getattr(request, "options", []) or [])
    }
    assert choice_keys == {"LETHAL_HITS", "SUSTAINED_HITS_1"}
    lethal_option_id = next(
        str(getattr(option, "option_id", "") or "")
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("choice_key", "") or "") == "LETHAL_HITS"
    )
    result = resolve_decision_command(game, request, lethal_option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False))

    fusion_rules = bearer.get_temporary_weapon_keyword_bonuses("Fusion Blaster")
    plasma_rules = bearer.get_temporary_weapon_keyword_bonuses("Plasma Rifle")
    fists_rules = bearer.get_temporary_weapon_keyword_bonuses("Battlesuit Fists")
    assert [rule["keyword"] for rule in fusion_rules] == ["LETHAL HITS"]
    assert [rule["keyword"] for rule in plasma_rules] == ["LETHAL HITS"]
    assert fists_rules == []

    game._on_unit_shooting_resolved_prototype_weapon_system(attacker_unit=source)

    assert bearer.get_temporary_weapon_keyword_bonuses("Fusion Blaster") == []
    assert bearer.get_temporary_weapon_keyword_bonuses("Plasma Rifle") == []


def test_puretide_engram_neurochip_refunds_cp_on_four_plus():
    game, tau_army, _enemy_army, tau_player, _enemy_player = _build_game()
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_army.add_unit(source)
    _apply_puretide_engram_neurochip(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    tau_player.command_points = 1
    tau_player._pending_stratagem_target_unit_id = str(get_entity_id(source) or "")
    tau_player._pending_stratagem_name = "Strike and Fade"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        ok = bool(tau_player.spend_command_points(1, reason="Stratagem: Strike and Fade", source="stratagem"))

    assert ok
    assert int(tau_player.command_points or 0) == 1


def test_starflare_ignition_system_has_tool_descriptor():
    descriptor = get_enhancement_tool_descriptor(enhancement_id="000008815005")
    assert descriptor is not None
    assert str(getattr(descriptor, "name", "") or "") == "Starflare Ignition System"
    assert str(getattr(descriptor, "effect", "") or "") == "end_of_opponent_turn_enter_strategic_reserves_if_not_engaged"
    assert str((getattr(descriptor, "effect_params", {}) or {}).get("ability_key", "") or "") == "starflare_ignition_system"


def test_starflare_ignition_system_queues_and_applies_end_of_opponent_turn_reserves():
    game, tau_army, enemy_army, tau_player, enemy_player = _build_game()
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _apply_starflare(source)

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    ability = source.get_end_of_opponent_turn_strategic_reserves_ability()
    assert isinstance(ability, dict)
    assert str(ability.get("ability_key", "") or "") == "starflare_ignition_system"
    assert str(ability.get("trigger_phase", "") or "") == "OPPONENT_TURN_END"

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "starflare_ignition_system"
    ]
    assert len(pending) == 1
    _resolve_yes_option(game, pending[0], player_id=tau_player.id)

    assert bool(source.is_in_strategic_reserves())
    assert source not in list(getattr(game.map, "units", []) or [])


def test_starflare_ignition_system_requires_not_engaged_to_queue_prompt():
    game, tau_army, enemy_army, _tau_player, enemy_player = _build_game()
    source = _make_unit(
        "Crisis Commander",
        keywords=["CHARACTER", "BATTLESUIT", "T'AU EMPIRE"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _apply_starflare(source)

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=0.1, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability_key", "") or "") == "starflare_ignition_system"
    ]
    assert len(pending) == 0
    assert not bool(source.is_in_strategic_reserves())
