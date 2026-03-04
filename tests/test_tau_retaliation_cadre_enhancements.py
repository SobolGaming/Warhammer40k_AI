from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Retaliation Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tau_player = Player("T'au", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, tau_army, enemy_army, tau_player, enemy_player


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
