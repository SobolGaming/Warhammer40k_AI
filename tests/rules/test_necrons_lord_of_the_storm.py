from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        wounds: int = 5,
        movement: int = 6,
        toughness: int = 5,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    cost: int = 100,
    wounds: int = 5,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
            wounds=wounds,
        )
    )
    unit.possible_abilities = list(abilities or [])
    unit._ability_cache = {}
    return unit


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    necron_army = Army("Necrons", "Other")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    return game, necron_player, enemy_player


def _pending_yes_no_for_ability(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key or ""):
            return request
    return None


def _resolve_yes(game: Game, request, player: Player):
    yes_option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            yes_option_id = option.option_id
            break
    assert yes_option_id is not None
    return resolve_decision_command(game, request, yes_option_id, player_id=player.id)


def test_lord_of_the_storm_queues_and_applies_mortal_table():
    game, necron_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 1

    lord_of_the_storm = Ability(
        "Lord of the Storm",
        "NEC",
        (
            "Once per battle, at the end of your Command phase, this model can use this ability. If it does, roll one "
            "D6 for each enemy unit within 12\" of this model: on a 2-5, that enemy unit suffers D3 mortal wounds; "
            "on a 6, that enemy unit suffers D3+3 mortal wounds."
        ),
        "Datasheet",
        "",
    )
    imotekh = _make_unit(
        "Imotekh The Stormlord",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=[lord_of_the_storm],
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy")
    enemy_b = _make_unit("Enemy B", faction_name="Enemy")
    enemy_c = _make_unit("Enemy C", faction_name="Enemy")

    necron_player.army.add_unit(imotekh)
    enemy_player.army.add_unit(enemy_a)
    enemy_player.army.add_unit(enemy_b)
    enemy_player.army.add_unit(enemy_c)

    _deploy_unit(game, imotekh, 0.0, 0.0)
    _deploy_unit(game, enemy_a, 10.0, 0.0)
    _deploy_unit(game, enemy_b, 0.0, 11.0)
    _deploy_unit(game, enemy_c, 20.0, 0.0)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_end", player=necron_player, phase=game.phase)
    request = _pending_yes_no_for_ability(game, "lord_of_the_storm")
    assert request is not None

    invalid = resolve_decision_command(
        game,
        request,
        "invalid-option-id",
        player_id=necron_player.id,
    )
    assert not bool(getattr(invalid, "ok", False))

    request = _pending_yes_no_for_ability(game, "lord_of_the_storm")
    assert request is not None

    applied_mortals: list[tuple[str, int]] = []
    imotekh._apply_mortal_wounds_to_unit = (
        lambda target, mortal, game_map=None: applied_mortals.append((str(getattr(target, "name", "") or ""), int(mortal)))
    )

    with patch(
        "warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin.get_roll",
        side_effect=[2, 3, 6, 2],
    ):
        result = _resolve_yes(game, request, necron_player)
    assert bool(getattr(result, "ok", False))

    assert imotekh.models[0].has_used_once_per_battle("lord_of_the_storm")
    assert sorted(int(mw) for _name, mw in list(applied_mortals or [])) == [3, 5]
    assert {name for name, _mw in list(applied_mortals or [])} == {"Enemy A", "Enemy B"}

    game.event_system.publish("phase_end", player=necron_player, phase=game.phase)
    assert _pending_yes_no_for_ability(game, "lord_of_the_storm") is None

