from __future__ import annotations

from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        wounds: int = 2,
        toughness: int = 4,
        objective_control: int = 1,
        base_size: str = "32mm",
        model_count: int = 1,
    ) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        unit_label = "Test Model" if int(model_count) == 1 else "Test Models"
        cost_label = "model" if int(model_count) == 1 else "models"
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} {unit_label}"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} {cost_label}", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id is not None:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    wounds: int = 2,
    toughness: int = 4,
    objective_control: int = 1,
    base_size: str = "32mm",
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            objective_control=objective_control,
            base_size=base_size,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.can_be_attached_to_names = [bodyguard.name]
    leader.attach_to_unit(bodyguard)


def _find_request(game: Game, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return request
    return None


def test_high_marshal_helbrecht_crusade_of_wrath_boosts_attached_unit_melee_attacks_and_strength():
    _game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()

    helbrecht = _actual_unit("High Marshal Helbrecht", datasheet_id="000002794")
    bodyguard = _mock_unit(
        "Helbrecht Bodyguard",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=4,
    )
    target = _mock_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
        model_count=1,
    )

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(helbrecht)
    enemy_army.add_unit(target)

    attacker = bodyguard.models[0]
    profile = Wargear(
        {
            "name": "Close combat weapon",
            "type": "Melee",
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]

    baseline_count = profile.preview_attack_count(target, attacker)
    baseline_wound = profile._wound_target_with_tracking(
        target,
        attacker,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(baseline_count.num_attacks or 0) == 3
    assert int(baseline_wound.get("final_needed", 0) or 0) == 5

    _attach_leader(bodyguard, helbrecht)

    boosted_count = profile.preview_attack_count(target, attacker)
    boosted_wound = profile._wound_target_with_tracking(
        target,
        attacker,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(boosted_count.num_attacks or 0) == 4
    assert int(boosted_wound.get("final_needed", 0) or 0) == 4
    modifiers = [str(entry or "") for entry in list(boosted_wound.get("modifiers", []) or [])]
    assert any("crusade of wrath" in entry.lower() for entry in modifiers)


def test_high_marshal_helbrecht_high_marshal_queues_and_applies_model_count_bonus_mortal_table():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE

    helbrecht = _actual_unit("High Marshal Helbrecht", datasheet_id="000002794")
    bodyguard = _mock_unit(
        "Helbrecht Bodyguard",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=4,
    )
    target = _mock_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=3,
        toughness=4,
    )

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(helbrecht)
    enemy_army.add_unit(target)
    _attach_leader(bodyguard, helbrecht)

    _deploy(bodyguard, 0.0, 0.0)
    _deploy(helbrecht, 0.0, 0.0)
    _deploy(target, 0.5, 0.0)
    game.map.units = [bodyguard, helbrecht, target]
    game.rebuild_entity_registry()

    bodyguard._apply_mortal_wounds_to_unit = Mock()

    game.event_system.publish("phase_start", player=sm_player, phase=game.phase)
    request = _find_request(game, "fight_phase_select_engagement_mortal_table")
    assert request is not None
    assert int((request.context or {}).get("roll_bonus_per_models", 0) or 0) == 5
    assert int((request.context or {}).get("roll_bonus_per_step", 0) or 0) == 1

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(target))
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[1, 2]):
        outcome = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(outcome, "ok", False)) is True

    bodyguard._apply_mortal_wounds_to_unit.assert_called_once()
    call_args = bodyguard._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is target
    assert int(call_args.args[1] or 0) == 2
