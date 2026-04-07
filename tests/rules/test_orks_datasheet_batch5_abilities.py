from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _KommandosWithDistractionGrotDatasheet:
    def __init__(self) -> None:
        self.id = "ORK-KOMMANDOS-MOCK"
        self.name = "Kommandos"
        self.faction_data = {"name": "Orks"}
        self.keywords = ["INFANTRY", "KOMMANDOS"]
        self.faction_keywords = ["ORKS"]
        self.datasheets_unit_composition = [{"description": "10 Kommandos"}]
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
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "ability_data": {
                    "name": "Distraction Grot",
                    "faction_id": "ORK",
                    "description": (
                        "Once per battle, in your opponent's Shooting phase, before making a saving throw for a model "
                        "in this unit, it can deploy the distraction grot. If it does, until the end of the phase, "
                        "models in this unit have a 5+ invulnerable save."
                    ),
                    "legend": "",
                },
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: slugga; choppa."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities: list[dict] | None = None,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
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
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
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


def _mock_unit(name: str, *, abilities: list[dict], keywords: list[str] | None = None) -> Unit:
    return Unit(_MockDatasheet(name, abilities=abilities, keywords=keywords))


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
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


def _find_pending_suppression_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET:
            continue
        return request
    return None


def test_distraction_grot_option_activates_unit_invulnerable_save_for_opponent_shooting_phase():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    kommandos = Unit(_KommandosWithDistractionGrotDatasheet())
    shooter = _actual_unit("Boyz")
    ork_army.add_unit(kommandos)
    enemy_army.add_unit(shooter)
    _deploy(kommandos, 0.0, 0.0)
    _deploy(shooter, 12.0, 0.0)
    _register_units(game, kommandos, shooter)

    ork_player.set_next_optional_decision("DISTRACTION_GROT", True)

    slugga = next(iter(next(wg for wg in shooter.models[0].wargear if wg.name == "Slugga").profiles.values()))
    save_result = slugga._save_with_tracking(
        kommandos.models[0],
        {
            "attacker_model": shooter.models[0],
            "attacker_unit": shooter,
            "target_unit": kommandos,
            "_aura_attack_mods": SimpleNamespace(),
        },
        ap=-2,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert str(save_result.get("save_type", "")) == "invulnerable"
    assert bool(save_result.get("saved", False)) is True
    assert kommandos.has_used_unit_once_per_battle("distraction_grot") is True
    for model in list(kommandos.models or []):
        inv_value, inv_source = model.get_temporary_invulnerable_save()
        assert int(inv_value or 0) == 5
        assert str(inv_source or "") == "Distraction Grot"


def test_distraction_grot_skip_leaves_save_unmodified_and_preserves_once_per_battle_use():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    kommandos = Unit(_KommandosWithDistractionGrotDatasheet())
    shooter = _actual_unit("Boyz")
    ork_army.add_unit(kommandos)
    enemy_army.add_unit(shooter)
    _deploy(kommandos, 0.0, 0.0)
    _deploy(shooter, 12.0, 0.0)
    _register_units(game, kommandos, shooter)

    ork_player.set_next_optional_decision("DISTRACTION_GROT", False)

    slugga = next(iter(next(wg for wg in shooter.models[0].wargear if wg.name == "Slugga").profiles.values()))
    save_result = slugga._save_with_tracking(
        kommandos.models[0],
        {
            "attacker_model": shooter.models[0],
            "attacker_unit": shooter,
            "target_unit": kommandos,
            "_aura_attack_mods": SimpleNamespace(),
        },
        ap=-2,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert str(save_result.get("save_type", "")) == "armor"
    assert bool(save_result.get("saved", False)) is False
    assert kommandos.has_used_unit_once_per_battle("distraction_grot") is False
    inv_value, _inv_source = kommandos.models[0].get_temporary_invulnerable_save()
    assert int(inv_value or 0) == 0


def test_rivetin_dakka_suppression_applies_only_to_ranged_attacks():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    boosta = _actual_unit("Kustom Boosta-blasta")
    suppressed = _actual_unit("Boyz")
    ork_army.add_unit(boosta)
    enemy_army.add_unit(suppressed)
    _deploy(boosta, 0.0, 0.0)
    _deploy(suppressed, 10.0, 0.0)
    _register_units(game, boosta, suppressed)

    shooter = boosta.models[0]
    game._on_unit_shooting_resolved_post_shoot_suppression(
        attacker_unit=boosta,
        hits_by_target={suppressed: 1},
        hit_models_by_target={suppressed: {shooter}},
        hit_models_by_target_weapon={suppressed: {"rivet kannon": {shooter}}},
    )

    request = _find_pending_suppression_request(game)
    assert request is not None
    assert list(request.context.get("attack_types", []) or []) == ["ranged"]

    target_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("unit_id") or "") == str(get_entity_id(suppressed) or "")
    )
    result = resolve_decision_command(game, request, target_option.option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False)) is True

    slugga_profile = next(iter(next(wg for wg in suppressed.models[0].wargear if wg.name == "Slugga").profiles.values()))
    melee_profile = next(iter(next(wg for wg in suppressed.models[0].wargear if wg.name == "Big choppa").profiles.values()))

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[5]):
        ranged_hit = slugga_profile._hit_target_with_tracking(
            boosta,
            suppressed.models[0],
            {"attacker_model": suppressed.models[0], "target_unit": boosta, "_aura_attack_mods": SimpleNamespace()},
        )
    assert bool(ranged_hit.get("hit", False)) is False
    assert any("Suppressed" in str(entry) for entry in list(ranged_hit.get("modifiers", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[3]):
        melee_hit = melee_profile._hit_target_with_tracking(
            boosta,
            suppressed.models[0],
            {"attacker_model": suppressed.models[0], "target_unit": boosta, "_aura_attack_mods": SimpleNamespace()},
        )
    assert bool(melee_hit.get("hit", False)) is True
    assert not any("Suppressed" in str(entry) for entry in list(melee_hit.get("modifiers", []) or []))


def test_drill_through_charge_end_six_deals_flat_three_mortal_wounds(monkeypatch):
    game, ork_army, enemy_army, _ork_player, _enemy_player = _build_game()
    scrapjet = _actual_unit("Megatrakk Scrapjet")
    enemy = _actual_unit("Boyz")
    ork_army.add_unit(scrapjet)
    enemy_army.add_unit(enemy)
    _deploy(scrapjet, 0.0, 0.0)
    _deploy(enemy, 2.0, 0.0)
    _register_units(game, scrapjet, enemy)

    scrapjet._refresh_charge_end_mortal_wounds_flags()
    spec = next(
        entry
        for entry in list(scrapjet.special_rules.get("charge_end_mortal_wounds", []) or [])
        if str(entry.get("kind", "") or "") == "table_d6_2_5_6_flat3"
    )

    applied: dict[str, object] = {}

    def _apply(self, target, amount, game_map=None):
        applied["target"] = target
        applied["amount"] = int(amount or 0)
        return 0

    scrapjet._apply_mortal_wounds_to_unit = types.MethodType(_apply, scrapjet)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda die: 6)

    game.resolve_charge_end_mortal_wounds(scrapjet, enemy, spec)

    assert applied["target"] is enemy
    assert int(applied["amount"] or 0) == 3


def test_one_last_kill_exposes_four_plus_melee_fight_on_death_rule():
    mozrog = _mock_unit(
        "Mozrog Skragbad",
        abilities=[
            {
                "name": "One Last Kill",
                "description": (
                    "While this model is leading a unit, each time a model in that unit is destroyed by a melee attack, "
                    "if it has not fought this phase, roll one D6: on a 4+, do not remove it from play. The destroyed "
                    "model can fight after the attacking unit has finished making its attacks, and is then removed from play."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER"],
    )

    rule = mozrog.get_melee_fight_on_death_after_attacks_rule(model=mozrog.models[0])

    assert rule is not None
    assert int(rule.get("threshold", 0) or 0) == 4
    assert str(rule.get("source", "") or "") == "One Last Kill"


def test_da_bigger_dey_iz_applies_plus_one_vs_vehicle_and_plus_two_vs_titanic():
    mozrog = _actual_unit("Mozrog Skragbad")
    trukk = _actual_unit("Trukk")
    stompa = _actual_unit("Stompa")
    profile = next(iter(next(wg for wg in mozrog.models[0].wargear if wg.name == "Gutrippa").profiles.values()))

    vehicle_damage = profile._damage_target_with_tracking(
        trukk.models[0],
        mozrog.models[0],
        {"attacker_model": mozrog.models[0], "target_unit": trukk, "_aura_attack_mods": SimpleNamespace()},
    )
    titanic_damage = profile._damage_target_with_tracking(
        stompa.models[0],
        mozrog.models[0],
        {"attacker_model": mozrog.models[0], "target_unit": stompa, "_aura_attack_mods": SimpleNamespace()},
    )

    assert int(vehicle_damage.get("damage_applied", 0) or 0) == 4
    assert "+1D vs MONSTER/VEHICLE (melee)" in list(vehicle_damage.get("special_effects", []) or [])
    assert int(titanic_damage.get("damage_applied", 0) or 0) == 5
    assert "+2D vs TITANIC (melee)" in list(titanic_damage.get("special_effects", []) or [])


def test_hold_still_and_say_aargh_adds_d6_mortals_on_critical_wound_only_vs_non_vehicle(monkeypatch):
    painboy = _actual_unit("Painboy")
    infantry_target = _actual_unit("Boyz")
    vehicle_target = _actual_unit("Trukk")
    syringe = next(iter(next(wg for wg in painboy.models[0].wargear if wg.name == "'Urty syringe").profiles.values()))

    infantry_attack = {"_aura_attack_mods": SimpleNamespace()}
    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda die: 4)
    infantry_wound = syringe._wound_target_with_tracking(
        infantry_target,
        painboy.models[0],
        infantry_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(infantry_wound.get("wound", False)) is True
    assert int(infantry_attack.get("successful_wound_extra_mortal_wounds", 0) or 0) == 4
    assert any("Hold Still and Say 'Aargh!'" in str(entry) for entry in list(infantry_wound.get("special_effects", []) or []))

    vehicle_attack = {"_aura_attack_mods": SimpleNamespace()}
    vehicle_wound = syringe._wound_target_with_tracking(
        vehicle_target,
        painboy.models[0],
        vehicle_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(vehicle_wound.get("wound", False)) is True
    assert int(vehicle_attack.get("successful_wound_extra_mortal_wounds", 0) or 0) == 0
