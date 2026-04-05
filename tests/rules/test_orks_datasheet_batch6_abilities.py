from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


BUZZER_SQUIGS_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
    "hit by one or more of those attacks made with squig-launchas and roll one D6: on a 4+, until the end of your "
    "opponent's next turn, that enemy unit is hindered. While a unit is hindered, subtract 2\" from its Move "
    "characteristic and subtract 2 from Advance and Charge rolls made for it."
)

SQUIG_MINE_TEXT = (
    "Once per battle, at the start of any phase, select one enemy unit within 3\" of this model and roll one D6: "
    "on a 4+, that enemy unit suffers D6 mortal wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities: list[dict] | None = None,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        move: int = 6,
        toughness: int = 5,
        wounds: int = 4,
        leadership: int = 7,
    ) -> None:
        self.id = f"MOCK-{name}"
        self.name = name
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ORKS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id="ORK"))


def _mock_unit(
    name: str,
    *,
    abilities: list[dict],
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    move: int = 6,
    toughness: int = 5,
    wounds: int = 4,
    leadership: int = 7,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            move=move,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
        )
    )


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    return game, ork_army, enemy_army, ork_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _quarry_target_option(request, target: Unit):
    target_id = str(get_entity_id(target) or "")
    return next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == target_id
    )


def test_buzzer_squigs_parses_weapon_threshold_and_hindered_state():
    attacker = _mock_unit(
        "Rukkatrukk Squigbuggy",
        abilities=[
            {
                "name": "Buzzer Squigs",
                "description": BUZZER_SQUIGS_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
    )

    specs = attacker.unit_post_shoot_shocked_specs()

    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("weapon_key", "") or "") == "squig launchas"
    assert str(spec.get("weapon_name", "") or "") == "squig launchas"
    assert int(spec.get("roll_threshold", 0) or 0) == 4
    assert str(spec.get("state_name", "") or "") == "hindered"
    assert bool(spec.get("exclude_monster_vehicle")) is True


def test_buzzer_squigs_post_shoot_request_applies_only_to_squig_launchas_hits(monkeypatch):
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    attacker = _mock_unit(
        "Rukkatrukk Squigbuggy",
        abilities=[
            {
                "name": "Buzzer Squigs",
                "description": BUZZER_SQUIGS_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
    )
    enemy_infantry = _mock_unit("Enemy Infantry", abilities=[], keywords=["INFANTRY"], faction_keywords=["ENEMY"], move=6)
    enemy_vehicle = _mock_unit("Enemy Vehicle", abilities=[], keywords=["VEHICLE"], faction_keywords=["ENEMY"], move=10)
    ork_army.add_unit(attacker)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_vehicle)
    _deploy(attacker, 0.0, 0.0)
    _deploy(enemy_infantry, 12.0, 0.0)
    _deploy(enemy_vehicle, 14.0, 0.0)
    _register_units(game, attacker, enemy_infantry, enemy_vehicle)

    game._on_unit_shooting_resolved_post_shoot_shocked(
        attacker_unit=attacker,
        hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        hit_models_by_target_weapon={
            enemy_infantry: {"squig launchas": {attacker.models[0]}},
            enemy_vehicle: {"squig launchas": {attacker.models[0]}},
        },
    )

    request = _find_quarry_request(game, "post_shoot_shocked")
    assert request is not None
    assert str(request.context.get("state_name", "") or "") == "hindered"
    assert int(request.context.get("roll_threshold", 0) or 0) == 4
    option_target_ids = {
        str((getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "")
        for option in list(request.options or [])
    }
    assert str(get_entity_id(enemy_infantry) or "") in option_target_ids
    assert str(get_entity_id(enemy_vehicle) or "") not in option_target_ids

    option = _quarry_target_option(request, enemy_infantry)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda die: 4)
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is True
    sr = dict(getattr(enemy_infantry, "special_rules", {}) or {})
    assert bool(sr.get("shocked_active")) is True
    assert str(sr.get("shocked_source", "") or "") == "Buzzer Squigs"
    assert int(sr.get("shocked_move_penalty", 0) or 0) == -2


def test_buzzer_squigs_failed_threshold_roll_does_not_apply_hindered(monkeypatch):
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    attacker = _mock_unit(
        "Rukkatrukk Squigbuggy",
        abilities=[
            {
                "name": "Buzzer Squigs",
                "description": BUZZER_SQUIGS_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
    )
    enemy_infantry = _mock_unit("Enemy Infantry", abilities=[], keywords=["INFANTRY"], faction_keywords=["ENEMY"], move=6)
    ork_army.add_unit(attacker)
    enemy_army.add_unit(enemy_infantry)
    _deploy(attacker, 0.0, 0.0)
    _deploy(enemy_infantry, 12.0, 0.0)
    _register_units(game, attacker, enemy_infantry)

    game._on_unit_shooting_resolved_post_shoot_shocked(
        attacker_unit=attacker,
        hits_by_target={enemy_infantry: 1},
        hit_models_by_target_weapon={enemy_infantry: {"squig launchas": {attacker.models[0]}}},
    )

    request = _find_quarry_request(game, "post_shoot_shocked")
    option = _quarry_target_option(request, enemy_infantry)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda die: 3)
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert not bool(getattr(enemy_infantry, "special_rules", {}).get("shocked_active"))


def test_squig_mine_queues_and_applies_once_per_battle(monkeypatch):
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    buggy = _mock_unit(
        "Rukkatrukk Squigbuggy",
        abilities=[
            {
                "name": "Squig Mine",
                "description": SQUIG_MINE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
    )
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(buggy)
    enemy_army.add_unit(enemy)
    _deploy(buggy, 0.0, 0.0)
    _deploy(enemy, 2.0, 0.0)
    _register_units(game, buggy, enemy)

    specs = buggy.model_start_any_phase_enemy_range_mortal_threshold_specs(buggy.models[0])
    assert len(specs) == 1
    ability_key = str(specs[0].get("ability_key", "") or "")

    applied: dict[str, object] = {}

    def _apply(self, target, amount, game_map=None, attacker_unit=None, attacker_model=None, damage_source=None):
        applied["target"] = target
        applied["amount"] = int(amount or 0)
        applied["damage_source"] = damage_source
        return 0

    buggy._apply_mortal_wounds_to_unit = types.MethodType(_apply, buggy)

    game._on_phase_start_optional_abilities(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "squig_mine")
    assert request is not None
    assert any(str((option.payload or {}).get("action", "") or "") == "skip" for option in list(request.options or []))

    option = _quarry_target_option(request, enemy)
    rolls = iter([4, 3])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda die: next(rolls))
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert buggy.models[0].has_used_once_per_battle(ability_key) is True
    assert applied["target"] is enemy
    assert int(applied["amount"] or 0) == 3
    assert str(applied["damage_source"] or "") == "Squig Mine"

    game._on_phase_start_optional_abilities(player=ork_player, phase=game.phase)
    assert _find_quarry_request(game, "squig_mine") is None


def test_squig_mine_validation_rejects_target_that_moves_out_of_range():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    buggy = _mock_unit(
        "Rukkatrukk Squigbuggy",
        abilities=[
            {
                "name": "Squig Mine",
                "description": SQUIG_MINE_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE"],
    )
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(buggy)
    enemy_army.add_unit(enemy)
    _deploy(buggy, 0.0, 0.0)
    _deploy(enemy, 2.0, 0.0)
    _register_units(game, buggy, enemy)

    game._on_phase_start_optional_abilities(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "squig_mine")
    assert request is not None

    _deploy(enemy, 10.0, 0.0)

    option = _quarry_target_option(request, enemy)
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is False
    assert any("within range" in str(error or "").lower() for error in list(getattr(result, "errors", []) or []))


def test_waaagh_effigy_aura_modifies_friendly_battleshock_tests():
    game, ork_army, enemy_army, _ork_player, _enemy_player = _build_game()
    stompa = _actual_unit("Stompa")
    boyz = _actual_unit("Boyz")
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(stompa)
    ork_army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    _deploy(stompa, 0.0, 0.0)
    _deploy(boyz, 8.0, 0.0)
    _deploy(enemy, 30.0, 0.0)
    _register_units(game, stompa, boyz, enemy)

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=7):
        in_aura_passed = boyz.pass_leadership_check()

    _deploy(stompa, 40.0, 0.0)
    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=7):
        out_of_aura_passed = boyz.pass_leadership_check()

    assert bool(in_aura_passed) is False
    assert bool(out_of_aura_passed) is True


def test_drive_by_dakka_improves_ap_within_nine_inches_only():
    game, ork_army, enemy_army, _ork_player, _enemy_player = _build_game()
    warbikers = _actual_unit("Warbikers")
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(warbikers)
    enemy_army.add_unit(enemy)
    _deploy(warbikers, 0.0, 0.0)
    _deploy(enemy, 8.0, 0.0)
    _register_units(game, warbikers, enemy)

    profile = next(iter(next(wg for wg in warbikers.models[0].wargear if wg.name == "Twin dakkagun").profiles.values()))

    within_ap = profile.get_effective_ap(warbikers.models[0], enemy)
    _deploy(enemy, 14.0, 0.0)
    outside_ap = profile.get_effective_ap(warbikers.models[0], enemy)

    assert int(within_ap) == int(outside_ap) - 1


def test_super_runts_grants_leading_scouts_hit_wound_and_defensive_wound_penalty():
    zodgrod = _actual_unit("Zodgrod Wortsnagga")
    bodyguard = _actual_unit("Boyz")
    target = _actual_unit("Boyz")

    profile = next(iter(next(wg for wg in bodyguard.models[0].wargear if wg.name == "Slugga").profiles.values()))
    attack_instance = {
        "attacker_model": bodyguard.models[0],
        "target_unit": target,
        "_aura_attack_mods": SimpleNamespace(),
    }

    baseline_hit = profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        dict(attack_instance),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    baseline_wound = profile._wound_target_with_tracking(
        target,
        bodyguard.models[0],
        dict(attack_instance),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(baseline_hit.get("hit", False)) is False
    assert bool(baseline_wound.get("wound", False)) is False
    assert bodyguard.has_scout() == (False, 0.0)

    zodgrod.can_attach_to = lambda _bodyguard: True
    zodgrod.attach_to_unit(bodyguard)

    attached_hit = profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        dict(attack_instance),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    attached_wound = profile._wound_target_with_tracking(
        target,
        bodyguard.models[0],
        dict(attack_instance),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(attached_hit.get("hit", False)) is True
    assert bool(attached_wound.get("wound", False)) is True
    assert bodyguard.has_scout() == (True, 9.0)
    defensive_entries = list(getattr(bodyguard, "special_rules", {}).get("defensive_wound_mods", []) or [])
    assert any(
        isinstance(entry, dict)
        and str(entry.get("source", "") or "") == "Super Runts"
        and int(entry.get("value", 0) or 0) == 1
        for entry in defensive_entries
    )

    zodgrod.detach_from_unit()
    assert bodyguard.has_scout() == (False, 0.0)


def test_unstable_oracle_adds_attacks_and_hazardous_to_eyez_of_mork(monkeypatch):
    game, ork_army, enemy_army, _ork_player, _enemy_player = _build_game()
    wurrboy = _actual_unit("Wurrboy")
    bodyguard = _actual_unit("Boyz")
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(wurrboy)
    ork_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _deploy(bodyguard, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, wurrboy, bodyguard, enemy)

    wurrboy.can_attach_to = lambda _bodyguard: True
    wurrboy.attach_to_unit(bodyguard)

    profile = next(iter(next(wg for wg in wurrboy.models[0].wargear if wg.name == "Eyez of Mork").profiles.values()))
    bonus = bodyguard.leading_scaled_weapon_bonus_for_weapon("Eyez of Mork", attacker_model=wurrboy.models[0])

    assert int(bonus.get("attacks_bonus", 0) or 0) == 4
    assert bool(bonus.get("hazardous", False)) is True
    assert any("Unstable Oracle" in str(entry) for entry in list(bonus.get("reasons") or []))

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda die: 1)
    result = profile.attack(enemy, wurrboy.models[0], game_map=game.map)

    assert result is not None
    assert int(result.hazardous_roll or 0) == 1
    assert int(result.hazardous_damage or 0) == 3
    assert any("Unstable Oracle" in str(entry) for entry in list(result.attacks_special_modifiers or []))
