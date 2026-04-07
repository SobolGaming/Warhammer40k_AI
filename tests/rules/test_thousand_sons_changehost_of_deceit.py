from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        save: str = "4",
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(save),
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    cost: int = 100,
    save: str = "4",
    abilities=None,
) -> Unit:
    ds = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
        save=save,
        abilities=abilities,
    )
    unit = Unit(ds)
    unit.deployed = True
    return unit


def _make_profile(*, ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not ranged,
        is_ranged=lambda: ranged,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _set_location(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "SM"
    player = Player("Player", PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    return game, army, enemy_army, player, enemy_player


def _apply_changehost_enhancement(unit: Unit, *, enh_id: str, name: str) -> None:
    Enhancement(
        id=enh_id,
        name=name,
        faction_id="TS",
        detachment="Changehost of Deceit",
        points=25,
        description="",
    ).apply_to_unit(unit)


def test_changehost_daemonic_illusions_grants_4_invuln_vs_ranged():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        save="6",
    )
    source = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(target)
    army.add_unit(source)
    _set_location(target, 0.0, 0.0)
    _set_location(source, 4.0, 0.0)

    profile = _make_profile(ranged=True)
    save_res = profile._save_with_tracking(target.models[0], {}, ap=0, roll_value=1)
    assert int(save_res.get("final_save", 0) or 0) == 4


def test_changehost_daemonic_illusions_does_not_apply_to_melee():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        save="6",
    )
    source = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(target)
    army.add_unit(source)
    _set_location(target, 0.0, 0.0)
    _set_location(source, 4.0, 0.0)

    profile = _make_profile(ranged=False)
    save_res = profile._save_with_tracking(target.models[0], {}, ap=0, roll_value=1)
    assert int(save_res.get("final_save", 0) or 0) == 6


def test_changehost_mortal_sorcery_grants_cabal_to_nearby_scintillating_legions_psyker():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit")
    army.faction_id = "TS"
    ts_source = _make_unit(
        "Exalted Sorcerer",
        keywords=["THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
    )
    sl_psyker = _make_unit(
        "Kairos Fateweaver",
        keywords=["SCINTILLATING LEGIONS", "PSYKER"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    army.add_unit(ts_source)
    army.add_unit(sl_psyker)
    _set_location(ts_source, 0.0, 0.0)
    _set_location(sl_psyker, 4.0, 0.0)

    mgr = army.cabal_of_sorcerers
    assert mgr._unit_has_cabal(sl_psyker)

    _set_location(sl_psyker, 20.0, 0.0)
    assert not mgr._unit_has_cabal(sl_psyker)


def test_changehost_restriction_enforces_scintillating_legions_points_cap():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit", points_limit=2000)
    army.faction_id = "TS"
    sl_1 = _make_unit(
        "Pink Horrors A",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=600,
    )
    sl_2 = _make_unit(
        "Pink Horrors B",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=600,
    )
    army.add_unit(sl_1)
    army.add_unit(sl_2)

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_changehost_restriction_disallows_scintillating_legions_warlord():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit", points_limit=2000)
    army.faction_id = "TS"
    warlord = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=100,
    )
    warlord.is_warlord = True
    army.warlord = warlord
    army.add_unit(warlord)

    with pytest.raises(ArmyValidationError):
        army.validate_detachment_rules()


def test_changehost_restriction_valid_case_passes():
    army = Army.with_detachment("Thousand Sons", "Changehost of Deceit", points_limit=1000)
    army.faction_id = "TS"
    ts_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS"],
        faction_keywords=["THOUSAND SONS"],
        cost=200,
    )
    sl_unit = _make_unit(
        "Pink Horrors",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
        cost=400,
    )
    ts_unit.is_warlord = True
    army.warlord = ts_unit
    army.add_unit(ts_unit)
    army.add_unit(sl_unit)

    army.validate_detachment_rules()


def test_changehost_nethershriek_mind_eater_queues_and_applies_mortals():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    bearer = _make_unit(
        "Exalted Sorcerer",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(bearer)
    enemy_army.add_unit(target)
    _apply_changehost_enhancement(
        bearer,
        enh_id="000010197002",
        name="Nethershriek Mind-eater",
    )
    bearer._has_line_of_sight_to_target = lambda _model, _target, _map: True
    target.pass_leadership_check = lambda: False
    target.models[0].wounds = 5
    target.models[0]._wounds = 5
    target.models[0]._base_wounds = 5
    _set_location(bearer, 0.0, 0.0)
    _set_location(target, 10.0, 0.0)
    game.map.units = [bearer, target]
    game.rebuild_entity_registry()

    before_wounds = int(target.models[0].wounds or 0)
    game._on_phase_start_shooting_phase_visible_battleshock(player=player, phase=game.phase)

    pending = [
        req for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
    ]
    assert len(pending) == 1
    request = pending[0]
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("ability_name", "") or "") == "Nethershriek Mind-eater"
    assert bool(ctx.get("use_leadership_test", False))
    assert int(ctx.get("fail_mortal_wounds", 0) or 0) == 3

    resolved = resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)
    assert bool(getattr(resolved, "ok", False))
    assert int(target.models[0].wounds or 0) == before_wounds - 3
    assert bool(target.is_battle_shocked())


def test_changehost_diabolic_savant_adds_channel_bonus_when_near_scintillating_legions():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    scintillating = _make_unit(
        "Pink Horrors",
        faction_name="Scintillating Legions",
        keywords=["SCINTILLATING LEGIONS"],
        faction_keywords=["SCINTILLATING LEGIONS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(caster)
    army.add_unit(scintillating)
    enemy_army.add_unit(target)
    _apply_changehost_enhancement(
        caster,
        enh_id="000010197003",
        name="Diabolic Savant",
    )
    _set_location(caster, 0.0, 0.0)
    _set_location(scintillating, 4.0, 0.0)
    _set_location(target, 10.0, 0.0)
    game.map.units = [caster, scintillating, target]

    mgr = army.cabal_of_sorcerers
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
        mp.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 12.0)
        result = mgr.attempt_ritual(
            game,
            caster_model=caster.models[0],
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[1, 1, 2],
            channel_decision=True,
            mortal_roll=0,
        )
    assert bool(result.get("success"))
    assert int(result.get("total", 0) or 0) == 5

    _set_location(scintillating, 20.0, 0.0)
    army.cabal_of_sorcerers = type(mgr)(army)
    mgr = army.cabal_of_sorcerers
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
        mp.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 12.0)
        result = mgr.attempt_ritual(
            game,
            caster_model=caster.models[0],
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[1, 1, 2],
            channel_decision=True,
            mortal_roll=0,
        )
    assert not bool(result.get("success"))
    assert int(result.get("total", 0) or 0) == 4


def test_changehost_tome_of_true_names_queues_and_applies_bearer_invulnerable_save():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.turn = 2

    bearer = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(bearer)
    _apply_changehost_enhancement(
        bearer,
        enh_id="000010197005",
        name="Tome of True Names",
    )
    _set_location(bearer, 0.0, 0.0)
    game.map.units = [bearer]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=player, phase=game.phase)

    pending = [
        req for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str(dict(getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Tome of True Names"
    ]
    assert len(pending) == 1
    request = pending[0]
    use_option = next(
        opt for opt in list(request.options or [])
        if bool(dict(getattr(opt, "payload", {}) or {}).get("choice"))
    )
    resolved = resolve_decision_command(game, request, use_option.option_id, player_id=player.id)
    assert bool(getattr(resolved, "ok", False))

    invuln, source = bearer.models[0].get_temporary_invulnerable_save()
    assert int(invuln or 0) == 2
    assert str(source or "") == "Tome of True Names"
    assert bearer.models[0].has_used_once_per_battle("start_any_phase_invuln:tome_of_true_names")
