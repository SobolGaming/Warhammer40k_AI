from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.adepta_sororitas_relics_of_the_matriarchs import (
    KEY_CENSER_OF_THE_SACRED_ROSE,
    KEY_ICON_OF_THE_VALOROUS_HEART,
    KEY_PETALS_OF_THE_BLOODY_ROSE,
    KEY_SIMULACRUM_OF_THE_ARGENT_SHROUD,
    KEY_SIMULACRUM_OF_THE_EBON_CHALICE,
    KEY_THE_FIERY_HEART,
    get_active_relics_of_the_matriarchs_keys,
)
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import (
    get_aura_advance_charge_roll_modifiers,
    get_aura_attack_modifiers,
    get_aura_battleshock_test_reroll_sources,
    get_aura_fnp_entries,
    get_aura_melee_ap_bonus,
    get_aura_move_characteristic_bonus,
)
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.rules import acts_of_faith as acts_of_faith_rules


RELICS_OF_THE_MATRIARCHS_TEXT = (
    "At the start of the battle round, select up to two of the abilities in the Relics of the Matriarchs section "
    "(see left). Until the start of the next battle round, this model has those abilities."
)
THE_FIERY_HEART_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, add 2\" to that unit's Move "
    "characteristic and add 1 to Advance and Charge rolls made for that unit."
)
CENSER_OF_THE_SACRED_ROSE_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, you can re-roll Battle-shock tests "
    "taken for that unit."
)
SIMULACRUM_OF_THE_EBON_CHALICE_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, that unit can perform up to two Acts "
    "of Faith per phase, instead of only one."
)
SIMULACRUM_OF_THE_ARGENT_SHROUD_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, each time a model in that unit makes a "
    "ranged attack, re-roll a Wound roll of 1."
)
ICON_OF_THE_VALOROUS_HEART_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, models in that unit have the Feel No "
    "Pain 6+ ability."
)
PETALS_OF_THE_BLOODY_ROSE_TEXT = (
    "While a friendly ADEPTA SORORITAS unit is within 6\" of this model, improve the Armour Penetration "
    "characteristic of melee weapons equipped by models in that unit by 1."
)
ACTS_OF_FAITH_TEXT = "This unit can perform Acts of Faith."


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "6",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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


def _triumph_abilities() -> list[dict]:
    return [
        _ability("Relics of the Matriarchs", RELICS_OF_THE_MATRIARCHS_TEXT),
        _ability("The Fiery Heart (Aura)", THE_FIERY_HEART_TEXT),
        _ability("Censer of the Sacred Rose (Aura)", CENSER_OF_THE_SACRED_ROSE_TEXT),
        _ability("Simulacrum of the Ebon Chalice (Aura)", SIMULACRUM_OF_THE_EBON_CHALICE_TEXT),
        _ability("Simulacrum of the Argent Shroud (Aura)", SIMULACRUM_OF_THE_ARGENT_SHROUD_TEXT),
        _ability("Icon of the Valorous Heart (Aura)", ICON_OF_THE_VALOROUS_HEART_TEXT),
        _ability("Petals of the Bloody Rose (Aura)", PETALS_OF_THE_BLOODY_ROSE_TEXT),
    ]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sororitas = Army.with_detachment("Adepta Sororitas", "Detachment")
    sororitas.faction_id = "AS"
    enemy = Army.with_detachment("Enemy", "Detachment")
    enemy.faction_id = "EN"

    p1 = Player("Sororitas Player", control=PlayerControl.LOCAL, army=sororitas)
    p2 = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    sororitas.configure_rule_managers(force=True)
    return game, sororitas, enemy, p1, p2


def _deploy(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    set_reserve_status = getattr(unit, "set_reserve_status", None)
    if callable(set_reserve_status):
        set_reserve_status("deployed")
    else:
        unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _find_relics_request(game: Game, *, source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if request.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "relics_of_the_matriarchs":
            continue
        if source_id and str(context.get("source_unit_id", "") or "") != source_id:
            continue
        return request
    return None


def _option_id_for_choice_keys(request, choice_keys: list[str]) -> str:
    normalized = sorted(str(v or "").strip().upper() for v in list(choice_keys or []) if str(v or "").strip())
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        candidate = sorted(
            str(v or "").strip().upper()
            for v in list(payload.get("choice_keys", []) or [])
            if str(v or "").strip()
        )
        if candidate == normalized:
            return str(option.option_id)
    return ""


def _ranged_profile():
    parent = SimpleNamespace(is_melee=lambda: False, is_ranged=lambda: True)
    return SimpleNamespace(parent_wargear=parent)


def _melee_profile():
    parent = SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False)
    return SimpleNamespace(parent_wargear=parent)


def test_relics_of_the_matriarchs_queues_and_applies_fiery_plus_petals_with_invalid_rejected():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit("Battle Sisters", keywords=["ADEPTA SORORITAS"], faction_keywords=["ADEPTA SORORITAS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    assert len(list(request.options or [])) == 22

    invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
    assert not bool(getattr(invalid, "ok", False))

    choice = [KEY_THE_FIERY_HEART, KEY_PETALS_OF_THE_BLOODY_ROSE]
    option_id = _option_id_for_choice_keys(request, choice)
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert set(get_active_relics_of_the_matriarchs_keys(source, game=game, battle_round=1)) == set(choice)

    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 2
    advance_mods, charge_mods = get_aura_advance_charge_roll_modifiers(target, game_map=game.map)
    assert sum(int(v) for v, _reason in list(advance_mods or [])) == 1
    assert sum(int(v) for v, _reason in list(charge_mods or [])) == 1
    melee_ap, _melee_ap_reasons = get_aura_melee_ap_bonus(target, _melee_profile(), game_map=game.map)
    assert int(melee_ap) == 1
    attack_mods = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert not bool(attack_mods.reroll_wound_ones)
    assert not bool(get_aura_battleshock_test_reroll_sources(target, game_map=game.map))


def test_relics_of_the_matriarchs_censer_plus_argent_enable_only_those_auras():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit("Battle Sisters", keywords=["ADEPTA SORORITAS"], faction_keywords=["ADEPTA SORORITAS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    choice = [KEY_CENSER_OF_THE_SACRED_ROSE, KEY_SIMULACRUM_OF_THE_ARGENT_SHROUD]
    option_id = _option_id_for_choice_keys(request, choice)
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert set(get_active_relics_of_the_matriarchs_keys(source, game=game, battle_round=1)) == set(choice)

    reroll_sources = get_aura_battleshock_test_reroll_sources(target, game_map=game.map)
    assert any("Censer of the Sacred Rose (Aura)" in src for src in reroll_sources)
    attack_mods = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert bool(attack_mods.reroll_wound_ones)

    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 0
    melee_ap, _melee_ap_reasons = get_aura_melee_ap_bonus(target, _melee_profile(), game_map=game.map)
    assert int(melee_ap) == 0


def test_relics_of_the_matriarchs_none_selection_leaves_no_active_auras():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit("Battle Sisters", keywords=["ADEPTA SORORITAS"], faction_keywords=["ADEPTA SORORITAS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    option_id = _option_id_for_choice_keys(request, [])
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert get_active_relics_of_the_matriarchs_keys(source, game=game, battle_round=1) == ()

    move_bonus, _move_reasons = get_aura_move_characteristic_bonus(target, game_map=game.map)
    assert int(move_bonus) == 0
    attack_mods = get_aura_attack_modifiers(target, foe, _ranged_profile(), game_map=game.map)
    assert not bool(attack_mods.reroll_wound_ones)
    assert not bool(get_aura_battleshock_test_reroll_sources(target, game_map=game.map))
    melee_ap, _melee_ap_reasons = get_aura_melee_ap_bonus(target, _melee_profile(), game_map=game.map)
    assert int(melee_ap) == 0
    assert not bool(get_aura_fnp_entries(target, game_map=game.map))


def test_relics_of_the_matriarchs_damaged_profile_limits_choices_to_one():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    source.special_rules["relics_of_matriarchs_max_choices"] = 1
    target = _make_unit("Battle Sisters", keywords=["ADEPTA SORORITAS"], faction_keywords=["ADEPTA SORORITAS"])
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    assert len(list(request.options or [])) == 7

    has_multi_pick = False
    for option in list(request.options or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if len(list(payload.get("choice_keys", []) or [])) > 1:
            has_multi_pick = True
            break
    assert not has_multi_pick

    option_id = _option_id_for_choice_keys(request, [KEY_THE_FIERY_HEART])
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert get_active_relics_of_the_matriarchs_keys(source, game=game, battle_round=1) == (KEY_THE_FIERY_HEART,)


def test_relics_of_the_matriarchs_ebon_plus_icon_allows_two_acts_of_faith_and_grants_fnp():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit(
        "Battle Sisters",
        abilities=[_ability("Acts of Faith", ACTS_OF_FAITH_TEXT)],
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    choice = [KEY_SIMULACRUM_OF_THE_EBON_CHALICE, KEY_ICON_OF_THE_VALOROUS_HEART]
    option_id = _option_id_for_choice_keys(request, choice)
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))
    assert set(get_active_relics_of_the_matriarchs_keys(source, game=game, battle_round=1)) == set(choice)

    fnp_entries = get_aura_fnp_entries(target, game_map=game.map)
    assert (6, None) in fnp_entries

    acts_mgr = getattr(sororitas, "acts_of_faith", None)
    assert acts_mgr is not None
    acts_mgr.miracle_dice = [6, 5, 4]

    assert bool(acts_mgr.can_use_act_of_faith(target, game=game))
    assert bool(acts_mgr._consume_miracle_die(target, 6, roll_type="hit", game=game))
    assert bool(acts_mgr.can_use_act_of_faith(target, game=game))
    assert bool(acts_mgr._consume_miracle_die(target, 5, roll_type="wound", game=game))
    assert not bool(acts_mgr.can_use_act_of_faith(target, game=game))


def test_relics_of_the_matriarchs_ebon_chalice_still_substitutes_only_one_die_in_a_single_roll():
    game, sororitas, enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Triumph of Saint Katherine",
        abilities=_triumph_abilities(),
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    target = _make_unit(
        "Battle Sisters",
        abilities=[_ability("Acts of Faith", ACTS_OF_FAITH_TEXT)],
        keywords=["ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    foe = _make_unit("Enemy Unit", keywords=["ADEPTUS ASTARTES"], faction_keywords=["ADEPTUS ASTARTES"])
    sororitas.add_unit(source)
    sororitas.add_unit(target)
    enemy.add_unit(foe)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    _deploy(foe, 12.0, 0.0)
    game.map.units = [source, target, foe]
    game.rebuild_entity_registry()

    sororitas.on_battle_round_start(1)
    request = _find_relics_request(game, source_unit=source)
    assert request is not None
    option_id = _option_id_for_choice_keys(request, [KEY_SIMULACRUM_OF_THE_EBON_CHALICE])
    assert option_id
    applied = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(applied, "ok", False))

    acts_mgr = getattr(sororitas, "acts_of_faith", None)
    assert acts_mgr is not None
    acts_mgr.miracle_dice = [6, 5]
    game.map.miracle_dice_provider = lambda **kwargs: max(list(kwargs.get("pool", []) or []), default=None)

    old_get_dice_roll = acts_of_faith_rules.get_dice_roll
    acts_of_faith_rules.get_dice_roll = lambda _faces=6: 1
    try:
        total, dice, used = acts_mgr.resolve_roll(
            target,
            roll_type="charge",
            dice_count=2,
            die_faces=6,
            game=game,
        )
    finally:
        acts_of_faith_rules.get_dice_roll = old_get_dice_roll

    assert bool(used)
    assert total == 7
    assert dice == [6, 1]
    assert list(acts_mgr.miracle_dice) == [5]
    assert bool(acts_mgr.can_use_act_of_faith(target, game=game))
