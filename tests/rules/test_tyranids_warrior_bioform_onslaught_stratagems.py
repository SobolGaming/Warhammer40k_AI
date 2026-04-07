from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        toughness: int = 5,
        base_size: str = "32mm",
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": str(int(toughness)),
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": str(base_size),
                "inv_sv": "0",
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
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    toughness: int = 5,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    tyr_army = Army.with_detachment("Tyranids", "Warrior Bioform Onslaught")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    tyr_player.command_points = 10
    enemy_player.command_points = 10
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    try:
        phase = BattleRoundPhases[str(phase_name or "").strip().upper()]
    except KeyError:
        phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _find_quarry_request(game: Game, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _option_for_target(request, *, target_unit):
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


def _option_for_objective(request, *, objective):
    objective_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("objective_id", "") or "") == objective_id:
            return option
    return None


def _weapon_stub(name: str, *, is_melee: bool):
    return SimpleNamespace(
        _id=f"weapon:{str(name).lower().replace(' ', '_')}:{'melee' if is_melee else 'ranged'}",
        name=str(name),
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )


def _make_objective(name: str, x: float, y: float) -> Objective:
    return Objective(
        str(name),
        ObjectiveCategory.PRIMARY,
        0,
        "",
        lambda _game: False,
        location=ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0),
    )


def _assign_weapons(unit: Unit, *, ranged_names=None, melee_names=None) -> None:
    ranged_names = list(ranged_names or [])
    melee_names = list(melee_names or [])
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [
            *[_weapon_stub(name, is_melee=False) for name in ranged_names],
            *[_weapon_stub(name, is_melee=True) for name in melee_names],
        ]


def _make_profile(*, weapon_name: str, is_melee: bool, strength: str = "4", skill: str = "4+") -> WargearProfile:
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_weapon_stub(weapon_name, is_melee=is_melee),
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


def test_warrior_bioform_onslaught_stratagem_descriptors_registered():
    expected = {
        "000009738002": ("Synaptic Amplification", "reroll_wound_rolls_of_1_and_conditional_tyranid_warriors_reroll_hit_rolls_of_1", 1),
        "000009738003": ("Spontaneous Hypercorrosion", "ranged_plus_two_strength_and_conditional_melee_plus_one_strength", 1),
        "000009738004": ("Restorative Impulse", "return_one_destroyed_non_character_model", 1),
        "000009738005": ("Synaptic Micronodes", "sticky_objective", 1),
        "000009738006": ("Parasitic Payload", "ranged_ignores_cover_and_post_shoot_no_cover", 1),
        "000009738007": ("Synaptic Shield", "conditional_minus_one_to_wound_from_ranged_attacks", 1),
    }
    for stratagem_id, (name, effect, cp_cost) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == name
        assert by_id.effect == effect
        assert int(by_id.cp_cost or 0) == cp_cost
        assert by_name.name == name


def test_synaptic_micronodes_queues_objective_selection_and_makes_selected_objective_sticky():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(warriors)
    _deploy_unit(game, warriors, 10.0, 10.0)
    game.map.objectives = [
        _make_objective("Objective A", 10.0, 10.0),
        _make_objective("Objective B", 11.0, 10.0),
    ]
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    objective_a, objective_b = list(game.map.objectives[:2])
    objective_a.location.controlling_player = tyr_player
    objective_b.location.controlling_player = tyr_player
    objective_a.location.sticky_controller = None
    objective_b.location.sticky_controller = None

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("SYNAPTIC MICRONODES", unit=warriors, phase_name="Movement phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9

    request = _find_quarry_request(game, "tyranids_synaptic_micronodes_objective")
    assert request is not None
    choice = _option_for_objective(request, objective=objective_b)
    assert choice is not None
    resolved = resolve_decision_command(game, request, choice.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True
    assert objective_b.location.sticky_controller is tyr_player
    assert objective_a.location.sticky_controller is None


def test_synaptic_amplification_applies_primary_and_optional_secondary_reroll_ones():
    from warhammer40k_ai.units import wargear as wargear_mod

    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Ranged Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
    )
    gaunts = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(warriors)
    tyr_army.add_unit(gaunts)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, gaunts, 14.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    warrior_profile = _make_profile(weapon_name="Deathspitter", is_melee=False, strength="4")
    gaunt_profile = _make_profile(weapon_name="Fleshborer", is_melee=False, strength="4")

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use("SYNAPTIC AMPLIFICATION", unit=warriors, phase_name="Shooting phase")
    assert ok is True
    request = _find_quarry_request(game, "tyranids_synaptic_amplification_secondary")
    assert request is not None
    choice = _option_for_target(request, target_unit=gaunts)
    assert choice is not None
    resolved = resolve_decision_command(game, request, choice.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    original_roll = wargear_mod.get_roll
    rolls = iter([5, 5, 5])
    wargear_mod.get_roll = lambda _dice: next(rolls)
    try:
        warrior_hit = warrior_profile._hit_target_with_tracking(
            enemy,
            warriors.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        warrior_wound = warrior_profile._wound_target_with_tracking(
            enemy,
            warriors.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        gaunt_hit = gaunt_profile._hit_target_with_tracking(
            enemy,
            gaunts.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        gaunt_wound = gaunt_profile._wound_target_with_tracking(
            enemy,
            gaunts.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(warrior_hit.get("reroll_of_one", 0) or 0) == 1
    assert int(warrior_wound.get("reroll_of_one", 0) or 0) == 1
    assert int(gaunt_hit.get("reroll_of_one", 0) or 0) == 0
    assert int(gaunt_wound.get("reroll_of_one", 0) or 0) == 1


def test_restorative_impulse_returns_non_character_model_only():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
        model_count=2,
    )
    character_unit = _make_unit(
        "Winged Tyranid Prime",
        keywords=["INFANTRY", "CHARACTER", "TYRANIDS", "WINGED TYRANID PRIME"],
        faction_keywords=["TYRANIDS"],
    )
    character_model = character_unit.models[0]
    destroyed_warrior = warriors.models.pop()
    warriors.models_lost = [character_model, destroyed_warrior]
    tyr_army.add_unit(warriors)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use("RESTORATIVE IMPULSE", unit=warriors, phase_name="Command phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert destroyed_warrior in list(warriors.models or [])
    assert destroyed_warrior not in list(warriors.models_lost or [])
    assert character_model in list(warriors.models_lost or [])


def test_parasitic_payload_grants_ignores_cover_and_post_shoot_no_cover_until_turn_end():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Ranged Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _assign_weapons(warriors, ranged_names=["Deathspitter"])
    tyr_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use("PARASITIC PAYLOAD", unit=warriors, phase_name="Shooting phase")
    assert ok is True
    keyword_bonuses = warriors.models[0].get_temporary_weapon_keyword_bonuses("Deathspitter")
    assert any(str(entry.get("keyword", "") or "").upper() == "IGNORES COVER" for entry in list(keyword_bonuses or []))

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=warriors,
        hits_by_target={enemy: 1},
    )
    request = _find_quarry_request(game, "post_shoot_no_cover")
    assert request is not None
    assert str(getattr(request, "context", {}).get("expires_timing", "") or "") == "TURN_END"
    choice = _option_for_target(request, target_unit=enemy)
    assert choice is not None
    resolved = resolve_decision_command(game, request, choice.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True
    assert bool(getattr(enemy, "special_rules", {}).get("post_shoot_no_cover_active", False)) is True
    assert str(getattr(enemy, "special_rules", {}).get("post_shoot_no_cover_expires_timing", "") or "") == "TURN_END"

    fight_phase = _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    assert bool(getattr(enemy, "special_rules", {}).get("post_shoot_no_cover_active", False)) is True
    game.event_system.publish("phase_end", player=tyr_player, phase=fight_phase)
    assert bool(getattr(enemy, "special_rules", {}).get("post_shoot_no_cover_active", False)) is False


def test_spontaneous_hypercorrosion_applies_ranged_and_conditional_melee_strength_bonuses():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )
    _assign_weapons(warriors, ranged_names=["Devourer"], melee_names=["Boneswords"])
    tyr_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    ranged_profile = _make_profile(weapon_name="Devourer", is_melee=False, strength="4")
    melee_profile = _make_profile(weapon_name="Boneswords", is_melee=True, strength="4")

    before_ranged = ranged_profile._wound_target_with_tracking(enemy, warriors.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    before_melee = melee_profile._wound_target_with_tracking(enemy, warriors.models[0], {}, roll_value=4, allow_rerolls=False, log_roll=False)
    assert bool(before_ranged.get("wound", False)) is False
    assert bool(before_melee.get("wound", False)) is False

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use("SPONTANEOUS HYPERCORROSION", unit=warriors, phase_name="Shooting phase")
    assert ok is True

    after_ranged = ranged_profile._wound_target_with_tracking(enemy, warriors.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    after_melee = melee_profile._wound_target_with_tracking(enemy, warriors.models[0], {}, roll_value=4, allow_rerolls=False, log_roll=False)
    assert bool(after_ranged.get("wound", False)) is True
    assert bool(after_melee.get("wound", False)) is True

    game_2, tyr_player_2, enemy_player_2, tyr_army_2, enemy_army_2 = _build_game()
    gaunts = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_2 = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )
    _assign_weapons(gaunts, ranged_names=["Fleshborer"], melee_names=["Claws"])
    tyr_army_2.add_unit(gaunts)
    enemy_army_2.add_unit(enemy_2)
    _deploy_unit(game_2, gaunts, 10.0, 10.0)
    _deploy_unit(game_2, enemy_2, 18.0, 10.0)
    _finalize_game(game_2, tyr_army_2, enemy_army_2, players=[tyr_player_2, enemy_player_2])

    gaunt_ranged = _make_profile(weapon_name="Fleshborer", is_melee=False, strength="4")
    gaunt_melee = _make_profile(weapon_name="Claws", is_melee=True, strength="4")
    _set_phase(game_2, tyr_player_2, "SHOOTING_PHASE", 0)
    ok = tyr_player_2.stratagems.use("SPONTANEOUS HYPERCORROSION", unit=gaunts, phase_name="Shooting phase")
    assert ok is True
    gaunt_ranged_after = gaunt_ranged._wound_target_with_tracking(enemy_2, gaunts.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    gaunt_melee_after = gaunt_melee._wound_target_with_tracking(enemy_2, gaunts.models[0], {}, roll_value=4, allow_rerolls=False, log_roll=False)
    assert bool(gaunt_ranged_after.get("wound", False)) is True
    assert bool(gaunt_melee_after.get("wound", False)) is False


def test_synaptic_shield_reacts_to_enemy_target_selection_and_applies_secondary_protection():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        keywords=["INFANTRY", "TYRANIDS", "TYRANID WARRIORS"],
        faction_keywords=["TYRANIDS"],
    )
    gaunts = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(warriors)
    tyr_army.add_unit(gaunts)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, gaunts, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    enemy_profile = _make_profile(weapon_name="Enemy Rifle", is_melee=False, strength="6")
    before_primary = enemy_profile._wound_target_with_tracking(warriors, enemy.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    before_secondary = enemy_profile._wound_target_with_tracking(gaunts, enemy.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    assert bool(before_primary.get("wound", False)) is True
    assert bool(before_secondary.get("wound", False)) is True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[warriors])
    pending = _pending_by_name(tyr_player.stratagems, "SYNAPTIC SHIELD")
    assert pending is not None

    ok = tyr_player.stratagems.use(
        "SYNAPTIC SHIELD",
        unit=warriors,
        attacking_unit=enemy,
        target_units=[warriors],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    request = _find_quarry_request(game, "tyranids_synaptic_shield_secondary")
    assert request is not None
    choice = _option_for_target(request, target_unit=gaunts)
    assert choice is not None
    resolved = resolve_decision_command(game, request, choice.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    after_primary = enemy_profile._wound_target_with_tracking(warriors, enemy.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    after_secondary = enemy_profile._wound_target_with_tracking(gaunts, enemy.models[0], {}, roll_value=3, allow_rerolls=False, log_roll=False)
    assert bool(after_primary.get("wound", False)) is False
    assert bool(after_secondary.get("wound", False)) is False
