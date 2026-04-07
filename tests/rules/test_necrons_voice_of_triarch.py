from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.necrons_voice_of_triarch import (
    KEY_PHAERON_OF_THE_BLADES,
    KEY_PHAERON_OF_THE_STARS,
    KEY_RELENTLESS_MARCH,
    get_active_voice_of_triarch_key,
    set_active_voice_of_triarch,
)
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import (
    get_aura_attack_modifiers,
    get_aura_move_characteristic_bonus,
    get_aura_strength_bonus,
)
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


VOICE_OF_TRIARCH_TEXT = (
    "At the start of the battle round, select one Triarch ability (see left). "
    "Until the start of the next battle round, this unit has that ability."
)
PHAERON_OF_THE_STARS_TEXT = (
    "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, each time a model in that "
    "unit makes an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
)
PHAERON_OF_THE_BLADES_TEXT = (
    "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, you can re-roll Charge rolls "
    "made for that unit and each time a model in that unit makes a melee attack, add 1 to the Strength "
    "characteristic of that attack."
)
RELENTLESS_MARCH_TEXT = (
    "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, add 2\" to the Move "
    "characteristic of models in that unit."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "2",
                "W": "8",
                "Ld": "7",
                "OC": "1",
                "base_size": "60mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    necrons = Army.with_detachment("Necrons", "Detachment")
    necrons.faction_id = "NEC"
    enemy = Army.with_detachment("Enemy", "Detachment")
    enemy.faction_id = "EN"

    p1 = Player("Necron Player", control=PlayerControl.LOCAL, army=necrons)
    p2 = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    necrons.configure_rule_managers(force=True)
    return game, necrons, enemy, p1, p2


def _deploy(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    set_reserve_status = getattr(unit, "set_reserve_status", None)
    if callable(set_reserve_status):
        set_reserve_status("deployed")
    else:
        unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _find_voice_of_triarch_request(game: Game, *, source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if request.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "voice_of_triarch":
            continue
        if source_id and str(context.get("source_unit_id", "") or "") != source_id:
            continue
        return request
    return None


def _option_id_for_choice(request, choice_key: str) -> str:
    token = str(choice_key or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == token:
            return str(option.option_id)
    return ""


def _ranged_profile():
    parent = SimpleNamespace(is_melee=lambda: False, is_ranged=lambda: True)
    return SimpleNamespace(parent_wargear=parent)


def _melee_profile():
    parent = SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False)
    return SimpleNamespace(parent_wargear=parent)


def _silent_king_abilities() -> list[dict]:
    return [
        _ability("Voice of the Triarch", VOICE_OF_TRIARCH_TEXT),
        _ability("Phaeron of the Stars (Aura)", PHAERON_OF_THE_STARS_TEXT),
        _ability("Phaeron of the Blades (Aura)", PHAERON_OF_THE_BLADES_TEXT),
        _ability("Relentless March (Aura)", RELENTLESS_MARCH_TEXT),
    ]


def test_voice_of_triarch_queues_and_applies_stars_choice_with_invalid_rejected():
    game, necrons, enemy, p1, _p2 = _build_game()
    source = _make_unit("The Silent King", abilities=_silent_king_abilities(), keywords=["NECRONS"], faction_keywords=["NECRONS"])
    source.models[0].name = "Szarekh"
    target = _make_unit("Necron Unit", keywords=["NECRONS"], faction_keywords=["NECRONS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    necrons.add_unit(source)
    necrons.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    necrons.on_battle_round_start(1)
    request = _find_voice_of_triarch_request(game, source_unit=source)
    assert request is not None
    assert len(list(request.options or [])) == 3

    invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
    assert not bool(getattr(invalid, "ok", False))

    option_id = _option_id_for_choice(request, KEY_PHAERON_OF_THE_STARS)
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert get_active_voice_of_triarch_key(source, game=game, battle_round=1) == KEY_PHAERON_OF_THE_STARS

    attack_mods = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert bool(attack_mods.reroll_hit_ones)
    assert bool(attack_mods.reroll_wound_ones)
    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 0
    strength_bonus, _strength_reasons = get_aura_strength_bonus(target, _melee_profile(), game_map=game.map)
    assert int(strength_bonus) == 0
    assert not bool(target.can_reroll_charge_roll(game_map=game.map))


def test_voice_of_triarch_blades_choice_enables_only_blades_aura_effects():
    game, necrons, enemy, p1, _p2 = _build_game()
    source = _make_unit("The Silent King", abilities=_silent_king_abilities(), keywords=["NECRONS"], faction_keywords=["NECRONS"])
    source.models[0].name = "Szarekh"
    target = _make_unit("Necron Unit", keywords=["NECRONS"], faction_keywords=["NECRONS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    necrons.add_unit(source)
    necrons.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    necrons.on_battle_round_start(1)
    request = _find_voice_of_triarch_request(game, source_unit=source)
    assert request is not None
    option_id = _option_id_for_choice(request, KEY_PHAERON_OF_THE_BLADES)
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert get_active_voice_of_triarch_key(source, game=game, battle_round=1) == KEY_PHAERON_OF_THE_BLADES

    strength_bonus, _strength_reasons = get_aura_strength_bonus(target, _melee_profile(), game_map=game.map)
    assert int(strength_bonus) == 1
    assert bool(target.can_reroll_charge_roll(game_map=game.map))

    attack_mods = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert not bool(attack_mods.reroll_hit_ones)
    assert not bool(attack_mods.reroll_wound_ones)
    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 0


def test_voice_of_triarch_clears_previous_choice_each_battle_round():
    game, necrons, enemy, p1, _p2 = _build_game()
    source = _make_unit("The Silent King", abilities=_silent_king_abilities(), keywords=["NECRONS"], faction_keywords=["NECRONS"])
    source.models[0].name = "Szarekh"
    target = _make_unit("Necron Unit", keywords=["NECRONS"], faction_keywords=["NECRONS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    necrons.add_unit(source)
    necrons.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    set_active_voice_of_triarch(source, KEY_RELENTLESS_MARCH, start_round=1, expires_round=2, player_id=p1.id)
    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 2

    game.turn = 2
    necrons.on_battle_round_start(2)
    assert get_active_voice_of_triarch_key(source, game=game, battle_round=2) is None
    request = _find_voice_of_triarch_request(game, source_unit=source)
    assert request is not None
    assert int((request.context or {}).get("battle_round", 0) or 0) == 2

    move_bonus_after, _move_reasons_after = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus_after) == 0
    attack_mods_after = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert not bool(attack_mods_after.reroll_hit_ones)
    assert not bool(attack_mods_after.reroll_wound_ones)
    strength_bonus_after, _strength_reasons_after = get_aura_strength_bonus(target, _melee_profile(), game_map=game.map)
    assert int(strength_bonus_after) == 0
    assert not bool(target.can_reroll_charge_roll(game_map=game.map))
