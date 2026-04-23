from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decision_requests import build_patrol_squad_requests
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _KommandosDatasheet:
    def __init__(self) -> None:
        self.id = "000000025"
        self.name = "Kommandos"
        self.faction_data = {"name": "Orks"}
        self.keywords = ["INFANTRY", "KOMMANDOS"]
        self.faction_keywords = ["ORKS"]
        self.datasheets_unit_composition = [{"description": "9 Kommandos and 1 Boss Nob"}]
        self.datasheets_models_cost = [{"description": "10 models", "cost": 135}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "5",
                "W": "1",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "ability_data": {
                    "name": "PATROL SQUAD",
                    "faction_id": "ORK",
                    "description": (
                        "At the start of the Declare Battle Formations step this unit can be split into two units, "
                        "each containing five models."
                    ),
                    "legend": "",
                },
                "type": "Special",
                "parameter": "",
            },
            {
                "ability_data": {
                    "name": "Bomb Squigs",
                    "faction_id": "ORK",
                    "description": "Once per battle, this unit can use one Bomb Squig after ending a Normal move.",
                    "legend": "",
                },
                "type": "Special",
                "parameter": "",
            },
            {
                "ability_data": {
                    "name": "Distraction Grot",
                    "faction_id": "ORK",
                    "description": (
                        "Once per battle, in your opponent's Shooting phase, before making a saving throw for a "
                        "model in this unit, it can deploy the distraction grot."
                    ),
                    "legend": "",
                },
                "type": "Special",
                "parameter": "",
            },
        ]
        self.loadout = "This model is equipped with: slugga; choppa."


def _build_game_with_kommandos(quantity: int = 10) -> tuple[Game, Player, Army, Unit]:
    ork_army = Army.with_detachment("Orks", "War Horde")
    enemy_army = Army.with_detachment("Space Marines", "Gladius Task Force")
    ork_player = Player("Orks", PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    ork_army.set_player(ork_player)
    enemy_army.set_player(enemy_player)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[ork_player, enemy_player])
    unit = Unit(_KommandosDatasheet(), quantity=quantity)
    ork_army.add_unit(unit)
    game.rebuild_entity_registry()
    return game, ork_player, ork_army, unit


def _find_option_id(request, *, choice: bool) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if payload.get("choice") is bool(choice):
            return str(getattr(option, "option_id", "") or "")
    return ""


def test_patrol_squad_split_creates_two_five_model_units_and_disables_token_abilities_on_one() -> None:
    game, player, army, unit = _build_game_with_kommandos(quantity=10)
    original_model_ids = {get_entity_id(model) for model in list(unit.models or [])}

    requests = build_patrol_squad_requests(game, army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO

    split_option_id = _find_option_id(request, choice=True)
    assert split_option_id
    result = resolve_decision_command(game, request, split_option_id, player_id=player.id)
    assert result.ok is True

    split_units = [u for u in list(army.units or []) if str(getattr(u, "name", "") or "") == "Kommandos"]
    assert len(split_units) == 2
    assert all(len(getattr(u, "models", []) or []) == 5 for u in split_units)
    assert unit not in split_units

    split_model_ids = {
        get_entity_id(model)
        for split_unit in split_units
        for model in list(getattr(split_unit, "models", []) or [])
    }
    assert split_model_ids == original_model_ids

    disabled_unit = next(
        (
            split_unit
            for split_unit in split_units
            if list(getattr(split_unit, "special_rules", {}).get("disabled_ability_names", []) or [])
        ),
        None,
    )
    assert disabled_unit is not None
    disabled_names = set(str(name) for name in list(disabled_unit.special_rules.get("disabled_ability_names", []) or []))
    assert disabled_names == {"Bomb Squigs", "Distraction Grot"}

    active_names = {
        str(name or "").strip().lower()
        for name, _desc in disabled_unit._iter_ability_entries_for_rules(model=None)
    }
    assert "bomb squigs" not in active_names
    assert "distraction grot" not in active_names


def test_patrol_squad_keep_together_marks_unit_declared_and_does_not_split() -> None:
    game, player, army, unit = _build_game_with_kommandos(quantity=10)

    requests = build_patrol_squad_requests(game, army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]

    keep_option_id = _find_option_id(request, choice=False)
    assert keep_option_id
    result = resolve_decision_command(game, request, keep_option_id, player_id=player.id)
    assert result.ok is True

    kommandos_units = [u for u in list(army.units or []) if str(getattr(u, "name", "") or "") == "Kommandos"]
    assert len(kommandos_units) == 1
    assert kommandos_units[0] is unit
    assert len(getattr(unit, "models", []) or []) == 10
    assert bool(getattr(unit, "special_rules", {}).get("patrol_squad_declared", False)) is True

    followup = build_patrol_squad_requests(game, army.units, queue_requests=False)
    assert followup == []


def test_patrol_squad_invalid_option_is_rejected() -> None:
    game, player, army, unit = _build_game_with_kommandos(quantity=10)
    requests = build_patrol_squad_requests(game, army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]

    result = resolve_decision_command(game, request, "invalid-option-id", player_id=player.id)
    assert result.ok is False
    assert game.decision_queue.get(request.decision_id) is not None

    kommandos_units = [u for u in list(army.units or []) if str(getattr(u, "name", "") or "") == "Kommandos"]
    assert len(kommandos_units) == 1
    assert kommandos_units[0] is unit
    assert bool(getattr(unit, "special_rules", {}).get("patrol_squad_declared", False)) is False


def test_patrol_squad_request_requires_ten_alive_models() -> None:
    game, _player, army, unit = _build_game_with_kommandos(quantity=10)
    for model in list(unit.models or [])[:5]:
        model.wounds = 0
    requests = build_patrol_squad_requests(game, army.units, queue_requests=False)
    assert requests == []
