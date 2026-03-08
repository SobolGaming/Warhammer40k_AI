from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


_NEURAL_DISRUPTION_DESCRIPTION = (
    "In your Command phase, select one enemy unit within 12\" of this model. "
    "That unit must take a Battle-shock test."
)

_PSYCHOLOGICAL_SABOTEUR_DESCRIPTION = (
    "While an enemy unit is within 12\" of this model, if that unit is Battle-shocked: "
    "- Each time a model in that unit makes an attack, subtract 1 from the Hit roll. "
    "- Each time a friendly TYRANIDS model makes an attack that targets that unit, add 1 to the Wound roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
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
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * idx), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_neural_disruption_parses_command_phase_select_enemy_battleshock_spec():
    neurolictor = _make_unit("Neurolictor", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    ability = Ability("Neural Disruption", "TYR", _NEURAL_DISRUPTION_DESCRIPTION, "Datasheet", "")
    model = neurolictor.models[0]
    model.abilities = {"Neural Disruption": ability}

    specs = neurolictor.model_start_selected_phases_enemy_range_battleshock_specs(model)
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 12
    assert int(spec.get("test_penalty", 0) or 0) == 0
    assert list(spec.get("phase_names", []) or []) == ["COMMAND_PHASE"]
    assert not bool(spec.get("optional", True))
    assert not bool(spec.get("once_per_turn", True))
    assert str(spec.get("context_ability", "") or "") == "command_phase_select_enemy_battleshock"


def test_neural_disruption_queues_mandatory_target_and_applies_battleshock():
    game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
    neurolictor = _make_unit("Neurolictor", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    ability = Ability("Neural Disruption", "TYR", _NEURAL_DISRUPTION_DESCRIPTION, "Datasheet", "")
    model = neurolictor.models[0]
    model.abilities = {"Neural Disruption": ability}

    target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"], model_count=3)
    target_calls = []
    target.take_battle_shock_test = lambda current_turn=1: target_calls.append(int(current_turn))

    tyr_army.add_unit(neurolictor)
    enemy_army.add_unit(target)
    _deploy_unit(game, neurolictor, 10.0, 10.0)
    _deploy_unit(game, target, 17.0, 10.0)
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")) == "command_phase_select_enemy_battleshock"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert str(request.decision_type) == DECISION_CHOOSE_QUARRY
    assert not any(str((opt.payload or {}).get("action", "")) == "skip" for opt in list(request.options or []))

    target_option = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(target._id)
    )
    outcome = resolve_decision_command(game, request, target_option.option_id, player_id=tyr_player.id)
    assert bool(getattr(outcome, "ok", False))
    assert target_calls == [2]
    assert int((getattr(target, "special_rules", {}) or {}).get("battle_shock_test_modifier", 0) or 0) == 0


def test_psychological_saboteur_applies_hit_penalty_only_while_attacker_is_battleshocked():
    game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
    neurolictor = _make_unit("Neurolictor", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    neurolictor.possible_abilities = [
        Ability("Psychological Saboteur (Aura)", "TYR", _PSYCHOLOGICAL_SABOTEUR_DESCRIPTION, "Datasheet", "")
    ]
    enemy_attacker = _make_unit("Enemy Attacker", faction_name="Enemy", faction_keywords=["ENEMY"], model_count=3)
    target = _make_unit("Tyranid Target", faction_keywords=["TYRANIDS"], model_count=3)

    tyr_army.add_unit(neurolictor)
    tyr_army.add_unit(target)
    enemy_army.add_unit(enemy_attacker)
    _deploy_unit(game, neurolictor, 10.0, 10.0)
    _deploy_unit(game, enemy_attacker, 18.0, 10.0)
    _deploy_unit(game, target, 25.0, 10.0)
    game.rebuild_entity_registry()

    profile = _make_ranged_profile()
    enemy_attacker.is_battle_shocked = lambda: False
    mods_not_shocked = get_aura_attack_modifiers(enemy_attacker, target, profile, game_map=game.map)
    assert int(getattr(mods_not_shocked, "hit", 0) or 0) == 0

    enemy_attacker.is_battle_shocked = lambda: True
    mods_shocked = get_aura_attack_modifiers(enemy_attacker, target, profile, game_map=game.map)
    assert int(getattr(mods_shocked, "hit", 0) or 0) == -1


def test_psychological_saboteur_grants_wound_bonus_vs_battleshocked_targets_in_aura_range():
    game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
    neurolictor = _make_unit("Neurolictor", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    neurolictor.possible_abilities = [
        Ability("Psychological Saboteur (Aura)", "TYR", _PSYCHOLOGICAL_SABOTEUR_DESCRIPTION, "Datasheet", "")
    ]
    tyr_attacker = _make_unit("Tyranid Attacker", faction_keywords=["TYRANIDS"], model_count=3)
    enemy_target = _make_unit("Enemy Target", faction_name="Enemy", faction_keywords=["ENEMY"], model_count=3)

    tyr_army.add_unit(neurolictor)
    tyr_army.add_unit(tyr_attacker)
    enemy_army.add_unit(enemy_target)
    _deploy_unit(game, neurolictor, 10.0, 10.0)
    _deploy_unit(game, tyr_attacker, 35.0, 10.0)
    _deploy_unit(game, enemy_target, 20.0, 10.0)
    game.rebuild_entity_registry()

    profile = _make_ranged_profile()
    enemy_target.is_battle_shocked = lambda: True
    mods_in_range = get_aura_attack_modifiers(tyr_attacker, enemy_target, profile, game_map=game.map)
    assert int(getattr(mods_in_range, "wound", 0) or 0) == 1

    for model in list(enemy_target.models or []):
        model.set_location(40.0, 10.0, 0.0, 0.0)
    mods_out_of_range = get_aura_attack_modifiers(tyr_attacker, enemy_target, profile, game_map=game.map)
    assert int(getattr(mods_out_of_range, "wound", 0) or 0) == 0
