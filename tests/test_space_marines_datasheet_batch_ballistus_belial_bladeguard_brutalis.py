from __future__ import annotations

from types import MethodType, SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BLADEGUARD_STANCE, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        save: str = "3",
        inv_save: str = "7",
        wounds: str = "4",
    ):
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": str(inv_save),
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


class _MockWeapon:
    def __init__(self, name: str, weapon_id: str, *, is_melee: bool = True):
        self.id = weapon_id
        self._id = weapon_id
        self.name = name
        self._is_melee = bool(is_melee)

    def is_melee(self) -> bool:
        return self._is_melee

    def is_ranged(self) -> bool:
        return not self._is_melee


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    save: str = "3",
    inv_save: str = "7",
    wounds: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            model_count=model_count,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            save=save,
            inv_save=inv_save,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", "Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.current_player_idx = 0
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 0.2), float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _set_melee_weapons(unit: Unit, weapon_name: str) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model_id = str(get_entity_id(model) or "")
        model.wargear = [_MockWeapon(weapon_name, f"{model_id}:{weapon_name.lower().replace(' ', '_')}")]


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


def _find_request(game: Game, decision_type: str, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != decision_type:
            continue
        if ability is None:
            return req
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip() == ability:
            return req
    return None


def _choose_option(game: Game, request, player: Player, choice_key: str):
    choice_key = str(choice_key or "").strip().upper()
    option_id = None
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("choice", "") or "").strip().upper() == choice_key:
            option_id = opt.option_id
            break
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is True
    return result


def _make_profile(*, weapon_name: str, weapon_type: str, skill: str = "3+", ap: str = "0") -> WargearProfile:
    is_melee = weapon_type.lower() == "melee"
    parent = SimpleNamespace(name=weapon_name, is_melee=lambda: is_melee, is_ranged=lambda: not is_melee)
    return WargearProfile(
        profile_name=weapon_type,
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": skill,
            "S": "5",
            "AP": ap,
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_ballistus_strike_rerolls_failed_ranged_hit_vs_target_not_below_half_strength(monkeypatch) -> None:
    attacker = _make_unit(
        "Ballistus Dreadnought",
        "000000091",
        abilities=[
            _ability(
                "Ballistus Strike",
                "Each time this model makes a ranged attack that targets a unit that is not Below Half-strength, you can re-roll the Hit roll.",
            )
        ],
        keywords=["VEHICLE"],
    )
    target = _make_unit("Target", "enemy_target")
    target.is_below_half_strength = lambda: False

    profile = _make_profile(weapon_name="Ballistus lascannon", weapon_type="Ranged")
    rolls = iter([2, 5])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: next(rolls))

    result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})

    assert bool(result.get("hit", False)) is True
    assert int(result.get("roll", 0) or 0) == 5


def test_grand_master_of_the_deathwing_grants_precision_on_critical_hits_while_leading(monkeypatch) -> None:
    bodyguard = _make_unit("Deathwing Knights", "bodyguard_ds", model_count=3, keywords=["INFANTRY"])
    belial = _make_unit(
        "Belial",
        "000000219",
        abilities=[
            _ability(
                "Grand Master of the Deathwing",
                "While this model is leading a unit, each time a model in that unit makes an attack, if a Critical Hit is scored, that attack has the [PRECISION] ability.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
    )
    target = _make_unit("Enemy Unit", "enemy_ds")
    _attach_leader(bodyguard, belial)

    profile = _make_profile(weapon_name="Mace of absolution", weapon_type="Melee")

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: 6)
    crit_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(target, bodyguard.models[0], crit_attack)
    assert bool(crit_attack.get("bonus_precision", False)) is True

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: 4)
    normal_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(target, bodyguard.models[0], normal_attack)
    assert bool(normal_attack.get("bonus_precision", False)) is False


def test_strikes_of_retribution_tracks_allocations_and_deals_mortals_after_fight_sequence(monkeypatch) -> None:
    from warhammer40k_ai.engine.game_mixins import shooting_fight_handlers_mixin as fight_mod

    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    belial = _make_unit(
        "Belial",
        "000000219",
        abilities=[
            _ability(
                "Strikes of Retribution",
                "Each time a melee attack is allocated to this model, after the attacking model’s unit has finished making its attacks, roll one D6 (to a maximum of six D6 per attacking unit): for each 4+, the attacking unit suffers 1 mortal wound.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
    )
    attacker = _make_unit("Enemy Fighters", "enemy_attackers", model_count=2, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(belial)
    enemy_army.add_unit(attacker)
    _deploy(belial, 0.0, 0.0)
    _deploy(attacker, 1.0, 0.0)
    game.map.units = [belial, attacker]
    game.rebuild_entity_registry()

    applied = {}

    def _apply(self, target_unit, amount, game_map=None, attacker_unit=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    belial._apply_mortal_wounds_to_unit = MethodType(_apply, belial)

    attack_rolls = iter([4, 4, 2])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: next(attack_rolls))
    profile = _make_profile(weapon_name="Chainsword", weapon_type="Melee")
    profile.attack(belial, attacker.models[0], game.map)

    sr = getattr(belial, "special_rules", {})
    allocations_by_key = dict(sr.get("allocated_melee_retaliation_allocations", {}) or {})
    assert allocations_by_key
    first_allocations = next(iter(allocations_by_key.values()))
    assert int(first_allocations.get(str(get_entity_id(attacker) or ""), 0) or 0) == 1

    monkeypatch.setattr(fight_mod, "get_roll", lambda _die: 4)
    game._on_fight_sequence_complete_allocated_melee_mortal_retaliation(unit=attacker)

    assert applied.get("target") is attacker
    assert int(applied.get("amount", 0) or 0) == 1
    assert "allocated_melee_retaliation_allocations" not in getattr(belial, "special_rules", {})


def test_deeds_of_heroism_queues_and_applies_unit_melee_attacks_bonus() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    bodyguard = _make_unit("Bladeguard Veteran Squad", "000000071", model_count=3, keywords=["INFANTRY"])
    ancient = _make_unit(
        "Bladeguard Ancient",
        "000001165",
        abilities=[
            _ability(
                "Deeds of Heroism",
                "Once per battle, when this model is selected to fight, it can use this ability. If it does, until the end of the phase, add 1 to the Attacks characteristic of melee weapons equipped by models in this model’s unit.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
    )
    enemy = _make_unit("Enemy Unit", "enemy_ds")
    _attach_leader(bodyguard, ancient)
    _set_melee_weapons(bodyguard, "Master-crafted power weapon")
    _set_melee_weapons(ancient, "Close combat weapon")

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(ancient)
    enemy_army.add_unit(enemy)
    _deploy(bodyguard, 0.0, 0.0)
    _deploy(ancient, 0.2, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [bodyguard, ancient, enemy]
    game.rebuild_entity_registry()

    game._on_fight_unit_selected_deeds_of_heroism(unit=bodyguard, selecting_player=sm_player)

    request = _find_request(game, DECISION_CONFIRM_YES_NO, "deeds_of_heroism")
    assert request is not None
    _choose_option(game, request, sm_player, "TRUE")

    assert int(bodyguard.models[0].get_temporary_weapon_attacks_bonus("Master-crafted power weapon")[0] or 0) == 1
    assert int(ancient.models[0].get_temporary_weapon_attacks_bonus("Close combat weapon")[0] or 0) == 1
    buff_key = str(((request.context or {}).get("buff_key", "") or "")).strip()
    assert bool(ancient.models[0].has_used_once_per_battle(buff_key)) is True


def test_bladeguard_stance_queues_and_swords_of_the_chapter_rerolls_hit_ones(monkeypatch) -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veteran Squad",
        "000000071",
        model_count=3,
        abilities=[
            _ability(
                "Bladeguard",
                "At the start of the Fight phase, you can select one of the following abilities to apply to models in this unit until the end of the phase: Swords of the Chapter: Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. Shields of the Chapter: Each time an invulnerable saving throw is made for a model in this unit, re-roll a saving throw of 1.",
            )
        ],
        keywords=["INFANTRY"],
        inv_save="4",
    )
    enemy = _make_unit("Enemy Unit", "enemy_ds")
    sm_army.add_unit(bladeguard)
    enemy_army.add_unit(enemy)
    _deploy(bladeguard, 0.0, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [bladeguard, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
    request = _find_request(game, DECISION_CHOOSE_BLADEGUARD_STANCE)
    assert request is not None
    _choose_option(game, request, sm_player, "SWORDS")
    assert str(getattr(bladeguard, "special_rules", {}).get("bladeguard_choice", "") or "") == "SWORDS"

    profile = _make_profile(weapon_name="Master-crafted power weapon", weapon_type="Melee")
    rolls = iter([1, 6])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: next(rolls))

    result = profile._hit_target_with_tracking(enemy, bladeguard.models[0], {"_aura_attack_mods": _aura_stub()})

    assert int(result.get("roll", 0) or 0) == 6
    assert int(result.get("reroll_of_one", 0) or 0) == 1


def test_bladeguard_shields_of_the_chapter_rerolls_invulnerable_save_ones(monkeypatch) -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veteran Squad",
        "000000071",
        model_count=3,
        abilities=[
            _ability(
                "Bladeguard",
                "At the start of the Fight phase, you can select one of the following abilities to apply to models in this unit until the end of the phase: Swords of the Chapter: Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. Shields of the Chapter: Each time an invulnerable saving throw is made for a model in this unit, re-roll a saving throw of 1.",
            )
        ],
        keywords=["INFANTRY"],
        inv_save="4",
    )
    enemy = _make_unit("Enemy Unit", "enemy_ds")
    sm_army.add_unit(bladeguard)
    enemy_army.add_unit(enemy)
    _deploy(bladeguard, 0.0, 0.0)
    _deploy(enemy, 1.0, 0.0)
    game.map.units = [bladeguard, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
    request = _find_request(game, DECISION_CHOOSE_BLADEGUARD_STANCE)
    assert request is not None
    _choose_option(game, request, sm_player, "SHIELDS")

    profile = _make_profile(weapon_name="Bolt rifle", weapon_type="Ranged", ap="-3")
    rolls = iter([1, 5])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _die: next(rolls))

    save_result = profile._save_with_tracking(
        bladeguard.models[0],
        {
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
            "target_unit": bladeguard,
            "_aura_attack_mods": _aura_stub(),
        },
        ap=-3,
        log_roll=False,
    )

    assert str(save_result.get("save_type", "") or "") == "invulnerable"
    assert int(save_result.get("roll", 0) or 0) == 5
    assert int(save_result.get("reroll_of_one", 0) or 0) == 1
    assert any("Bladeguard" in str(effect or "") for effect in list(save_result.get("special_effects", []) or []))


def test_brutalis_charge_parses_and_resolves_new_mortal_wound_table(monkeypatch) -> None:
    unit = _make_unit(
        "Brutalis Dreadnought",
        "000000136",
        abilities=[
            _ability(
                "Brutalis Charge",
                "Each time this model ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6: on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds.",
            )
        ],
        keywords=["VEHICLE"],
    )
    enemy = _make_unit("Enemy Unit", "enemy_ds")
    unit._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(unit, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    spec = next(spec for spec in specs if str(spec.get("kind", "") or "") == "table_d6_2_3_d3_4_5_3_6_d3_3")

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = MethodType(_apply, unit)

    def _fake_get_roll(die):
        return 4 if str(die or "").upper() == "D6" else 1

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    sm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [unit, enemy]
    game.rebuild_entity_registry()

    game.resolve_charge_end_mortal_wounds(unit, enemy, spec)

    assert applied.get("target") is enemy
    assert int(applied.get("amount", 0) or 0) == 3
