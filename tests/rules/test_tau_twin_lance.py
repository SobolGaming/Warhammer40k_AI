from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")
_EXEMPLARS_OF_MONTKA_DESCRIPTION = (
    "Each time a model in this unit makes a ranged attack that targets the closest eligible target, "
    "that attack has the [SUSTAINED HITS 1] and [IGNORES COVER] abilities."
)
_RETRO_THRUSTERS_DESCRIPTION = (
    "At the end of the Fight phase, this unit can either make a Normal move of up to 6\" or a Fall Back move."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "7",
                "Sv": "3",
                "W": "8",
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
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


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _first_option(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Detachment")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "EN"
    tau_player = Player("TAU", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    return game, tau_player, enemy_player


def test_exemplars_of_montka_applies_sustained_hits_and_ignores_cover_to_closest_target_only():
    game, tau_player, enemy_player = _build_game()
    attacker = _make_unit(
        "The Twin Lance",
        abilities=[
            {
                "name": "Exemplars of Mont'ka",
                "description": _EXEMPLARS_OF_MONTKA_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    close_target = _make_unit("Close Target")
    far_target = _make_unit("Far Target")
    tau_player.army.add_unit(attacker)
    enemy_player.army.add_unit(close_target)
    enemy_player.army.add_unit(far_target)
    attacker.deployed = True
    close_target.deployed = True
    far_target.deployed = True
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    close_target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    far_target.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, close_target, far_target]

    parent = SimpleNamespace(name="Test Carbine", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={"range": "24", "A": "1", "BS_WS": "3+", "S": "5", "AP": "0", "D": "1", "description": ""},
        parent_wargear=parent,
    )

    close_attack = {"_aura_attack_mods": _aura_stub()}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        profile._hit_target_with_tracking(
            close_target,
            attacker.models[0],
            close_attack,
            allow_rerolls=False,
            log_roll=False,
        )
    assert bool(close_attack.get("ignores_cover", False))
    assert int(close_attack.get("sustained_hit", 0) or 0) == 1

    far_attack = {"_aura_attack_mods": _aura_stub()}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        profile._hit_target_with_tracking(
            far_target,
            attacker.models[0],
            far_attack,
            allow_rerolls=False,
            log_roll=False,
        )
    assert not bool(far_attack.get("ignores_cover", False))
    assert int(far_attack.get("sustained_hit", 0) or 0) == 0


def test_retro_thrusters_not_engaged_offers_normal_move_and_queues_move_decision():
    game, tau_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    unit = _make_unit(
        "The Twin Lance",
        abilities=[
            {
                "name": "Retro-thrusters",
                "description": _RETRO_THRUSTERS_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_player.army.add_unit(unit)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    game.map.units = [unit]

    game._on_phase_end_raid_and_run(player=tau_player, phase=BattleRoundPhases.FIGHT_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "retro_thrusters"
    )
    modes = {
        str((opt.payload or {}).get("retro_thrusters_mode", ""))
        for opt in list(request.options or [])
        if (opt.payload or {}).get("retro_thrusters_mode")
    }
    assert "normal_move" in modes
    assert "fall_back_move" not in modes

    move_opt = _first_option(request, lambda payload: str(payload.get("retro_thrusters_mode", "")) == "normal_move")
    assert move_opt is not None
    resolve_decision_command(game, request, move_opt.option_id, player_id=tau_player.id)

    move_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("reactive_move_kind", "")) == "retro_thrusters"
    )
    ctx = dict(move_request.context or {})
    assert str(ctx.get("movement_type", "")) == "move"
    assert int(ctx.get("max_distance", 0) or 0) == 6


def test_retro_thrusters_engaged_offers_fall_back_mode():
    game, tau_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    unit = _make_unit(
        "The Twin Lance",
        abilities=[
            {
                "name": "Retro-thrusters",
                "description": _RETRO_THRUSTERS_DESCRIPTION,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tau_player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    unit.deployed = True
    unit.reserve_status = "deployed"
    enemy.deployed = True
    enemy.reserve_status = "deployed"
    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [unit, enemy]

    game._on_phase_end_raid_and_run(player=tau_player, phase=BattleRoundPhases.FIGHT_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "retro_thrusters"
    )
    modes = {
        str((opt.payload or {}).get("retro_thrusters_mode", ""))
        for opt in list(request.options or [])
        if (opt.payload or {}).get("retro_thrusters_mode")
    }
    assert "fall_back_move" in modes
    assert "normal_move" not in modes


def test_mv15_gun_drone_grants_twin_pulse_blaster_to_each_bearer_model():
    datasheet = _WAHA.get_datasheet("The Twin Lance", datasheet_id="000004203", faction_id="TAU")
    assert datasheet is not None
    unit = Unit(datasheet)
    assert len(list(unit.models or [])) == 2

    for model in list(unit.models or []):
        wargear_names = [str(getattr(wg, "name", "") or "") for wg in list(getattr(model, "wargear", []) or [])]
        twin_pulse_count = sum(1 for name in wargear_names if name.strip().lower() == "twin pulse blaster")
        assert twin_pulse_count == 1
