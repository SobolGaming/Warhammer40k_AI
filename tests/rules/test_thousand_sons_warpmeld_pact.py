from __future__ import annotations

import pytest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "8",
        oc: str = "1",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": str(oc),
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
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
    wounds: str = "8",
    oc: str = "1",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            oc=oc,
        )
    )
    unit.deployed = True
    return unit


def _make_profile(*, ranged: bool, strength: str = "4") -> WargearProfile:
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
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_simple_game(*, armies: list[Army], phase_name: str, current_player_index: int = 0):
    players = []
    for idx, army in enumerate(list(armies or [])):
        player = SimpleNamespace(
            id=f"P{idx + 1}",
            name=f"P{idx + 1}",
            game=None,
            has_control=lambda: False,
            get_army=lambda a=army: a,
        )
        army.player = player
        players.append(player)
    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        players=players,
        map=SimpleNamespace(roll_reroll_provider=None),
        get_current_player=lambda: players[int(current_player_index)],
    )
    for player in list(players or []):
        player.game = game
    return game


def _build_engine_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("P1", "Warpmeld Pact")
    army1.faction_id = "TS"
    army2 = Army.with_detachment("P2", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TS",
        detachment="Warpmeld Pact",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _option_with_choice(request, choice: bool):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return opt
    raise AssertionError(f"No option with choice={choice}.")


def _wire_same_army(*units: Unit) -> Army:
    army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    for unit in units:
        army.add_unit(unit)
    return army


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def test_warpmeld_pact_validation_applies_tzaangors_battleline_keyword():
    army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(tzaangors)

    army.validate_detachment_rules()

    keywords = [str(k or "").strip().lower() for k in list(getattr(tzaangors, "keywords", []) or [])]
    assert "battleline" in keywords


def test_warpmeld_pact_tzaangor_oc_bonus_requires_not_battle_shocked():
    army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        oc="1",
    )
    army.add_unit(tzaangors)
    army.validate_detachment_rules()

    model = tzaangors.models[0]
    assert int(model.objective_control) == 2

    tzaangors.status_effects = [BattleShockEffect(current_turn=1)]
    assert int(model.objective_control) == 1


def test_warpmeld_sacrifice_offense_adds_wound_bonus():
    army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    attacker_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game = _build_simple_game(armies=[army, enemy_army], phase_name="SHOOTING_PHASE", current_player_index=0)

    mgr = army.thousand_sons_detachments
    assert mgr.activate_warpmeld_sacrifice(attacker_unit, mode="offense", game=game)

    profile = _make_profile(ranged=True, strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result["wound"] is True
    assert any("Warpmeld Sacrifice" in str(entry) for entry in wound_result.get("modifiers", []))


def test_warpmeld_sacrifice_defense_subtracts_from_enemy_wound_roll():
    defender_army = Army.with_detachment("Thousand Sons", "Warpmeld Pact")
    defender_army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    defender_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
    )
    attacker_unit = _make_unit(
        "Enemy Shooter",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    defender_army.add_unit(defender_unit)
    enemy_army.add_unit(attacker_unit)
    game = _build_simple_game(armies=[defender_army, enemy_army], phase_name="SHOOTING_PHASE", current_player_index=1)

    mgr = defender_army.thousand_sons_detachments
    assert mgr.activate_warpmeld_sacrifice(defender_unit, mode="defense", game=game)

    profile = _make_profile(ranged=True, strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        defender_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result["wound"] is False
    assert any("Warpmeld Sacrifice" in str(entry) and "-1" in str(entry) for entry in wound_result.get("modifiers", []))


def test_warpmeld_prompt_resolution_and_phase_end_mortals(monkeypatch):
    game, army1, army2, p1, _p2 = _build_engine_game()
    warpmeld_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        wounds="8",
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="8",
    )
    army1.add_unit(warpmeld_unit)
    army2.add_unit(enemy_unit)
    game.map.units = [warpmeld_unit, enemy_unit]
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_thousand_sons_warpmeld_sacrifice(
        attacking_unit=warpmeld_unit,
        target_units=[enemy_unit],
    )

    unit_id = str(get_entity_id(warpmeld_unit) or "")
    requests = [
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((r.context or {}).get("ability", "") or "") == "warpmeld_sacrifice"
        and str((r.context or {}).get("ability_mode", "") or "") == "offense"
        and str((r.context or {}).get("unit_id", "") or "") == unit_id
    ]
    assert requests
    request = requests[0]
    use_opt = _option_with_choice(request, True)
    resolved = resolve_decision_command(game, request, use_opt.option_id, player_id=p1.id)
    assert bool(getattr(resolved, "ok", False))

    mgr = army1.thousand_sons_detachments
    assert int(mgr.warpmeld_sacrifice_attacker_wound_bonus(warpmeld_unit.models[0], game=game) or 0) == 1

    before = int(warpmeld_unit.models[0].wounds)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _dice: 2)
    game._on_phase_end_thousand_sons_warpmeld_sacrifice(
        player=game.get_current_player(),
        phase=BattleRoundPhases.SHOOTING_PHASE,
    )
    after = int(warpmeld_unit.models[0].wounds)

    assert int(before - after) == 2
    assert int(mgr.warpmeld_sacrifice_attacker_wound_bonus(warpmeld_unit.models[0], game=game) or 0) == 0


def test_warpmeld_dagger_adds_bonus_equal_to_mortal_wounds_suffered_on_ritual():
    game, army, enemy_army, _p1, _p2 = _build_engine_game()
    caster = _make_unit(
        "Tzaangor Shaman",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        wounds="4",
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    army.add_unit(caster)
    enemy_army.add_unit(target)
    game.map.units = [caster, target]
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()
    _apply_enhancement(caster, enhancement_id="000010201002", enhancement_name="Warpmeld Dagger")

    mgr = army.cabal_of_sorcerers
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
        mp.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 12.0)
        result = mgr.attempt_ritual(
            game,
            caster_model=caster.models[0],
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[1, 2],
            channel_decision=False,
            warpmeld_dagger_choice=True,
            warpmeld_dagger_mortal_roll=2,
        )

    assert bool(result.get("success")) is True
    assert bool(result.get("warpmeld_dagger_used")) is True
    assert int(result.get("warpmeld_dagger_roll", 0) or 0) == 2
    assert int(result.get("warpmeld_dagger_mortal_wounds", 0) or 0) == 2
    assert int(result.get("warpmeld_dagger_bonus", 0) or 0) == 2
    assert int(result.get("total", 0) or 0) == 5
    assert int(caster.models[0].wounds or 0) == 2


def test_warpmeld_diamond_of_distortion_applies_minus_one_to_hit_while_leading():
    bodyguard = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    leader = _make_unit(
        "Tzaangor Shaman",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    _wire_same_army(bodyguard, leader)
    _apply_enhancement(leader, enhancement_id="000010201003", enhancement_name="Diamond of Distortion")
    _attach_leader(bodyguard, leader)

    penalty, reasons = bodyguard.get_target_hit_roll_penalty("ranged")

    assert int(penalty) == 1
    assert any("Diamond of Distortion" in str(reason) for reason in list(reasons or ()))


def test_warpmeld_diamond_of_distortion_inactive_when_not_leading():
    leader = _make_unit(
        "Tzaangor Shaman",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    _wire_same_army(leader)
    _apply_enhancement(leader, enhancement_id="000010201003", enhancement_name="Diamond of Distortion")

    penalty, reasons = leader.get_target_hit_roll_penalty("ranged")

    assert int(penalty) == 0
    assert tuple(reasons or ()) == ()


def test_bray_lord_grants_scouts_and_tzaangor_attachment_override():
    leader = _make_unit(
        "Sorcerer",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    leader.can_be_attached_to = ["existing-bodyguard-placeholder"]
    bodyguard = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    _wire_same_army(leader, bodyguard)
    _apply_enhancement(leader, enhancement_id="000010201004", enhancement_name="Bray Lord")

    has_scout, scout_distance = leader.has_scout()

    assert bool(has_scout) is True
    assert float(scout_distance) == 6.0
    assert "Tzaangors" in list(getattr(leader, "can_be_attached_to_names", []) or [])
    assert leader.can_attach_to(bodyguard)


def test_flowing_flesh_sets_bearer_wounds_to_five_and_grants_fnp_four_plus():
    bearer_unit = _make_unit(
        "Tzaangor Shaman",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        wounds="4",
    )
    _wire_same_army(bearer_unit)
    _apply_enhancement(bearer_unit, enhancement_id="000010201005", enhancement_name="Flowing Flesh")

    bearer = bearer_unit.models[0]
    fnp_entries = list(bearer_unit.has_feel_no_pain(target_model=bearer) or [])

    assert int(getattr(bearer, "_base_wounds", 0) or 0) == 5
    assert int(getattr(bearer, "_wounds", 0) or 0) == 5
    assert (4, None) in fnp_entries
