from __future__ import annotations

from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
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
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
        wounds: int = 4,
        attached_to: list[str] | None = None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
    wounds: int = 4,
    possible_abilities: list[str] | None = None,
    attached_to: list[str] | None = None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
            wounds=wounds,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if possible_abilities:
        unit.possible_abilities = list(possible_abilities)
    return unit


def _build_game(*, points_limit: int = 2000) -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army.with_detachment("Genestealer Cults", "Final Day", points_limit=points_limit)
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _find_psionic_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "final_day_psionic_parasitism":
            return req
    return None


def _pair_option_id(request, *, gsc_unit: Unit | None = None, tyranids_unit: Unit | None = None) -> str:
    gsc_id = str(get_entity_id(gsc_unit) or "") if gsc_unit is not None else ""
    tyr_id = str(get_entity_id(tyranids_unit) or "") if tyranids_unit is not None else ""
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if gsc_unit is None and tyranids_unit is None:
            if str(payload.get("action", "") or "") == "skip":
                return str(getattr(opt, "option_id", "") or "")
            continue
        if str(payload.get("gsc_unit_id", "") or "") == gsc_id and str(payload.get("tyranids_unit_id", "") or "") == tyr_id:
            return str(getattr(opt, "option_id", "") or "")
    return ""


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * 1.5), float(y), 0.0, 0.0)


def _apply_final_day_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="GC",
        detachment="Final Day",
        points=20,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    if bearer_id:
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                return model
    for model in list(getattr(unit, "models", []) or []):
        is_alive = getattr(model, "is_alive", True)
        if callable(is_alive):
            is_alive = is_alive()
        if bool(is_alive):
            return model
    return None


def _stratagem_manager(player: Player):
    manager = getattr(player, "stratagems", None)
    assert manager is not None
    return manager


def _pending_reaction_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(getattr(stratagems, "_pending_reactions", []) or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_melee_profile(*, strength: str = "5", ap: str = "0") -> WargearProfile:
    parent = type(
        "_ParentMeleeWargear",
        (),
        {
            "name": "Monstrous Talons",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile(*, name: str = "Autogun") -> WargearProfile:
    parent = type(
        "_ParentRangedWargear",
        (),
        {
            "name": str(name),
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "24",
            "A": "2",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_final_day_enhancement_descriptors_exist():
    expected = {
        "000009827002": ("Synaptic Auger", "double_psionic_parasitism_healing_for_bearer"),
        "000009827003": ("Enraptured Damnation", "prevent_enemy_fire_overwatch_against_bearers_unit"),
        "000009827004": ("Vanguard Tyrant", "bearer_melee_strength_ap_bonus"),
        "000009827005": ("Inhuman Integration", "grant_sustained_hits_one_vs_enemies_near_friendly_tyranids"),
    }

    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_final_day_psionic_parasitism_decision_applies_mortals_heal_and_bonus():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 0

    synapse = _make_unit(
        "Winged Tyranid Prime",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "SYNAPSE", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_target = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=2,
    )
    tyranids_target = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds=5,
    )
    gsc_army.add_unit(synapse)
    gsc_army.add_unit(gsc_target)
    gsc_army.add_unit(tyranids_target)
    game.rebuild_entity_registry()

    tyr_model = tyranids_target.models[0]
    tyr_model.wounds = max(1, int(getattr(tyr_model, "wounds", 1) or 1) - 2)
    wounds_before = int(tyr_model.wounds or 0)
    base_wounds = int(getattr(tyr_model, "_base_wounds", wounds_before) or wounds_before)

    mgr = gsc_army.genestealer_cults_detachments
    mgr.final_day_psionic_parasitism_pair_candidates_for_synapse = (
        lambda *_args, **_kwargs: [(gsc_target, tyranids_target)]
    )
    mgr.final_day_psionic_parasitism_pair_eligible = lambda *_args, **_kwargs: True

    game._on_phase_end_genestealer_cults_final_day_psionic_parasitism(
        player=gsc_player,
        phase=BattleRoundPhases.MOVEMENT_PHASE,
    )
    req = _find_psionic_request(game)
    assert req is not None
    assert bool((req.context or {}).get("optional")) is True
    assert str((req.context or {}).get("unit_id", "") or "") == str(get_entity_id(synapse) or "")

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        option_id = _pair_option_id(req, gsc_unit=gsc_target, tyranids_unit=tyranids_target)
        assert option_id
        resolve_decision_command(game, req, option_id, player_id=gsc_player.id)

    healed_expected = min(3, max(0, base_wounds - wounds_before))
    assert int(tyr_model.wounds or 0) == int(wounds_before + healed_expected)
    tyr_sr = dict(getattr(tyranids_target, "special_rules", {}) or {})
    assert bool(tyr_sr.get("gsc_final_day_psionic_parasitism_active")) is True
    assert int(tyr_sr.get("gsc_final_day_psionic_parasitism_hit_bonus", 0) or 0) == 1


def test_final_day_hit_bonuses_apply_and_cleanup_on_next_movement_phase_start():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    synapse = _make_unit(
        "Winged Tyranid Prime",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "SYNAPSE", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_target = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyranids_attacker = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_attacker = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(synapse)
    gsc_army.add_unit(gsc_target)
    gsc_army.add_unit(tyranids_attacker)
    gsc_army.add_unit(gsc_attacker)
    enemy_army.add_unit(enemy)

    mgr = gsc_army.genestealer_cults_detachments
    out = mgr.apply_final_day_psionic_parasitism_choice(
        synapse,
        gsc_unit=gsc_target,
        tyranids_unit=tyranids_attacker,
        skip=False,
        game=None,
        player=gsc_player,
        mortal_wounds=0,
    )
    assert isinstance(out, dict)

    psionic_bonus, _psionic_source = mgr.final_day_psionic_parasitism_hit_bonus(
        tyranids_attacker.models[0],
        game=game,
    )
    assert int(psionic_bonus or 0) == 1

    game.map.get_distance_between_units = lambda unit_a, unit_b: 5.0 if unit_b is enemy else 99.0
    catalyst_bonus, catalyst_source = mgr.final_day_catalyst_hit_bonus(
        gsc_attacker.models[0],
        enemy,
        game=game,
    )
    assert int(catalyst_bonus or 0) == 1
    assert "catalyst" in str(catalyst_source or "").lower()

    game.turn = 3
    game._on_phase_start_genestealer_cults_final_day_cleanup(
        player=gsc_player,
        phase=BattleRoundPhases.MOVEMENT_PHASE,
    )
    tyr_sr_after = dict(getattr(tyranids_attacker, "special_rules", {}) or {})
    assert bool(tyr_sr_after.get("gsc_final_day_psionic_parasitism_active")) is False


def test_final_day_pair_candidates_enforce_synapse_range_visibility_and_exclusions():
    game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    synapse = _make_unit(
        "Winged Tyranid Prime",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "SYNAPSE", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_ok = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_excluded = _make_unit(
        "Purestrain Genestealers",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyr_ok = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_army.add_unit(synapse)
    gsc_army.add_unit(gsc_ok)
    gsc_army.add_unit(gsc_excluded)
    gsc_army.add_unit(tyr_ok)

    good_ids = {
        str(get_entity_id(gsc_ok) or ""),
        str(get_entity_id(tyr_ok) or ""),
    }
    game.map.get_distance_between_units = (
        lambda source, target: 5.0
        if source is synapse and str(get_entity_id(target) or "") in good_ids
        else 20.0
    )
    synapse._attacking_unit_has_any_los_to_target_unit = lambda target, _game_map: str(get_entity_id(target) or "") in good_ids

    mgr = gsc_army.genestealer_cults_detachments
    pairs = list(mgr.final_day_psionic_parasitism_pair_candidates_for_synapse(synapse, game=game) or [])
    assert any(pair[0] is gsc_ok and pair[1] is tyr_ok for pair in pairs)
    assert not any(pair[0] is gsc_excluded for pair in pairs)


def test_final_day_restrictions_enforce_tyranid_caps_unit_limits_and_warlord_rule():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game(points_limit=1000)

    invalid_tyranid = _make_unit(
        "Harpy",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "AIRCRAFT"],
        faction_keywords=["TYRANIDS"],
        points=600,
    )
    gsc_unit = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(invalid_tyranid)
    gsc_army.add_unit(gsc_unit)
    gsc_army.warlord = invalid_tyranid

    mgr = gsc_army.genestealer_cults_detachments
    errors = list(mgr.validate_detachment_rules() or [])
    combined = "\n".join(str(msg or "") for msg in errors)
    assert "MISSING VANGUARD INVADER" in combined
    assert "AIRCRAFT" in combined
    assert "Incursion cap of 500" in combined
    assert "no TYRANIDS models from your army can be your WARLORD" in combined

    with pytest.raises(ArmyValidationError):
        gsc_army.validate_detachment_rules()


def test_synaptic_auger_doubles_psionic_parasitism_healing_for_bearer():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()

    synapse = _make_unit(
        "Winged Tyranid Prime",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "SYNAPSE", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_target = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyranid_bearer = _make_unit(
        "Winged Hive Tyrant",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        wounds=6,
    )
    gsc_army.add_unit(synapse)
    gsc_army.add_unit(gsc_target)
    gsc_army.add_unit(tyranid_bearer)

    _apply_final_day_enhancement(
        tyranid_bearer,
        enhancement_id="000009827002",
        name="Synaptic Auger",
        description=(
            "Tyranids model only. Each time the bearer would regain one or more lost wounds from the Psionic "
            "Parasitism Detachment rule, it regains up to twice that number of lost wounds instead."
        ),
    )

    tyranid_model = tyranid_bearer.models[0]
    tyranid_model.wounds = 2

    result = gsc_army.genestealer_cults_detachments.apply_final_day_psionic_parasitism_choice(
        synapse,
        gsc_unit=gsc_target,
        tyranids_unit=tyranid_bearer,
        skip=False,
        game=game,
        player=gsc_player,
        mortal_wounds=2,
    )

    assert isinstance(result, dict)
    assert int(result.get("healed_wounds", 0) or 0) == 4
    assert int(tyranid_model.wounds or 0) == 6


def test_enraptured_damnation_blocks_fire_overwatch_against_bearers_attached_unit_while_alive():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()

    bodyguard = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    leader = _make_unit(
        "Magus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(bodyguard)
    gsc_army.add_unit(leader)
    enemy_army.add_unit(enemy)
    leader.attach_to_unit(bodyguard)
    _set_unit_position(bodyguard, 10.0, 10.0)
    _set_unit_position(enemy, 18.0, 10.0)
    game.map.units = [bodyguard, leader, enemy]
    game.rebuild_entity_registry()

    _apply_final_day_enhancement(
        leader,
        enhancement_id="000009827003",
        name="Enraptured Damnation",
        description="Genestealer Cults model only. Enemy units cannot use the Fire Overwatch Stratagem to shoot at the bearer's unit.",
    )

    assert bool(bodyguard.is_overwatch_prevented_against(enemy, game=game)) is True

    leader_model = leader.models[0]
    leader_model.wounds = 0
    invalidate_leader = getattr(leader, "_invalidate_ability_cache", None)
    invalidate_bodyguard = getattr(bodyguard, "_invalidate_ability_cache", None)
    if callable(invalidate_leader):
        invalidate_leader()
    if callable(invalidate_bodyguard):
        invalidate_bodyguard()

    assert bool(bodyguard.is_overwatch_prevented_against(enemy, game=game)) is False


def test_vanguard_tyrant_improves_bearers_melee_strength_and_ap():
    _game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()

    bearer_unit = _make_unit(
        "Winged Hive Tyrant",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        wounds=6,
    )
    enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
        wounds=6,
    )
    gsc_army.add_unit(bearer_unit)
    enemy_army.add_unit(enemy)

    _apply_final_day_enhancement(
        bearer_unit,
        enhancement_id="000009827004",
        name="Vanguard Tyrant",
        description="Winged Hive Tyrant model only. Improve the Strength and Armour Penetration characteristics of melee weapons equipped by the bearer by 1.",
    )

    bearer = _bearer_model(bearer_unit)
    assert bearer is not None
    melee_profile = _make_melee_profile(strength="5", ap="0")

    assert int(melee_profile.get_effective_ap(attacker=bearer, target=enemy) or 0) == -1
    wound_result = melee_profile._wound_target_with_tracking(
        enemy,
        bearer,
        attack_instance={},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Vanguard Tyrant" in str(modifier or "") for modifier in list(wound_result.get("modifiers", []) or []))


def test_inhuman_integration_grants_sustained_hits_when_target_is_near_friendly_tyranids():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()

    bodyguard = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    leader = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    tyranid_ally = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    gsc_army.add_unit(bodyguard)
    gsc_army.add_unit(leader)
    gsc_army.add_unit(tyranid_ally)
    enemy_army.add_unit(enemy)
    leader.attach_to_unit(bodyguard)
    game.map.units = [bodyguard, leader, tyranid_ally, enemy]
    game.rebuild_entity_registry()

    _apply_final_day_enhancement(
        leader,
        enhancement_id="000009827005",
        name="Inhuman Integration",
        description=(
            "Genestealer Cults model only. Weapons equipped by models in the bearer's unit have the "
            "[SUSTAINED HITS 1] ability while targeting an enemy unit within 6\" of one or more friendly Tyranids units."
        ),
    )

    game.map.get_distance_between_units = lambda unit_a, unit_b: 5.0 if unit_a is tyranid_ally and unit_b is enemy else 99.0

    near_bonus = bodyguard.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=bodyguard.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
        game_map=game.map,
    )
    assert int(near_bonus.get("sustained_hits_value", 0) or 0) == 1

    leader.models[0].wounds = 0
    invalidate_leader = getattr(leader, "_invalidate_ability_cache", None)
    invalidate_bodyguard = getattr(bodyguard, "_invalidate_ability_cache", None)
    if callable(invalidate_leader):
        invalidate_leader()
    if callable(invalidate_bodyguard):
        invalidate_bodyguard()

    dead_bearer_bonus = bodyguard.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=bodyguard.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
        game_map=game.map,
    )
    assert int(dead_bearer_bonus.get("sustained_hits_value", 0) or 0) == 0


def test_final_day_stratagem_descriptors_exist():
    expected = {
        "000009828004": ("AVENGE THE STAR CHILDREN", "mark_destroying_enemy_for_gsc_hit_and_wound_bonus"),
        "000009828006": ("DARTING ATTACKS", "shoot_and_charge_after_fall_back"),
        "000009828005": ("DIVINE IMPERATIVE", "target_locked_charge_bonus_and_reroll"),
        "000009828002": ("HYPERFEROCITY", "reroll_wound_ones_or_full_near_friendly_tyranids"),
        "000009828003": ("PSI SURGE", "increase_catalyst_aura_range_and_lock_stratagem"),
        "000009828007": ("RESISTANCE TUNNELS", "enter_strategic_reserves"),
    }

    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_avenge_the_star_children_marks_enemy_and_grants_hit_and_wound_bonuses():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    destroyed_tyranid = _make_unit(
        "Winged Tyranid Prime",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "SYNAPSE", "CHARACTER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_attacker = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(destroyed_tyranid)
    gsc_army.add_unit(gsc_attacker)
    enemy_army.add_unit(enemy)
    game.map.units = [destroyed_tyranid, gsc_attacker, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    _stratagem_manager(gsc_player).refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    destroyed_tyranid.models = []
    game.event_system.publish("unit_destroyed", unit=destroyed_tyranid, destroyed_by_unit=enemy)

    manager = _stratagem_manager(gsc_player)
    pending = _pending_reaction_by_name(manager, "AVENGE THE STAR CHILDREN")
    assert pending is not None

    used = manager.use(
        "AVENGE THE STAR CHILDREN",
        destroyed_unit=destroyed_tyranid,
        enemy_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert int(gsc_player.command_points or 0) == 2

    profile = _make_ranged_profile(name="Autogun")
    hit_result = profile._hit_target_with_tracking(
        enemy,
        gsc_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Avenge the Star Children" in str(item or "") for item in list(hit_result.get("modifiers", []) or []))

    wound_result = profile._wound_target_with_tracking(
        enemy,
        gsc_attacker.models[0],
        dict(hit_result, hit=True),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Avenge the Star Children" in str(item or "") for item in list(wound_result.get("modifiers", []) or []))


def test_darting_attacks_allows_shooting_and_charging_after_fall_back_in_selected_phase():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    tyranid_unit = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    gsc_army.add_unit(tyranid_unit)
    game.map.units = [tyranid_unit]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    manager = _stratagem_manager(gsc_player)
    manager.refresh_available()
    gsc_player.command_points = 4

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)
    used_shooting = manager.use("DARTING ATTACKS", unit=tyranid_unit, phase_name="Shooting phase")
    assert bool(used_shooting) is True
    assert bool(tyranid_unit.can_shoot_after_fall_back(_make_ranged_profile(name="Devourer"))) is True

    game.event_system.publish("phase_end", player=gsc_player, phase=game.phase)
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)
    used_charge = manager.use("DARTING ATTACKS", unit=tyranid_unit, phase_name="Charge phase")
    assert bool(used_charge) is True
    assert bool(tyranid_unit.can_charge_after_fall_back()) is True


def test_divine_imperative_applies_charge_bonus_and_reroll_only_against_locked_enemy():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

    gsc_charger = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyranid_anchor = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_locked = _make_unit("Enemy Locked", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(gsc_charger)
    gsc_army.add_unit(tyranid_anchor)
    enemy_army.add_unit(enemy_locked)
    enemy_army.add_unit(enemy_other)
    _set_unit_position(gsc_charger, 0.0, 0.0)
    _set_unit_position(tyranid_anchor, 10.0, 10.0)
    _set_unit_position(enemy_locked, 10.5, 10.0)
    _set_unit_position(enemy_other, 30.0, 30.0)
    game.map.units = [gsc_charger, tyranid_anchor, enemy_locked, enemy_other]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)

    manager = _stratagem_manager(gsc_player)
    manager.refresh_available()
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    used = manager.use(
        "DIVINE IMPERATIVE",
        unit=gsc_charger,
        enemy_unit=enemy_locked,
        phase_name="Charge phase",
    )
    assert bool(used) is True

    mgr = gsc_army.genestealer_cults_detachments
    bonus, source = mgr.final_day_divine_imperative_charge_roll_bonus(
        gsc_charger,
        target_units=[enemy_locked],
        game=game,
    )
    assert int(bonus or 0) == 1
    assert "divine imperative" in str(source or "").lower()
    assert bool(gsc_charger.can_reroll_charge_roll(target_unit=enemy_locked, game=game, game_map=game.map)) is True
    assert bool(gsc_charger.can_reroll_charge_roll(target_unit=enemy_other, game=game, game_map=game.map)) is False


def test_hyperferocity_grants_wound_reroll_ones_or_full_when_enemy_is_near_friendly_tyranids():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

    fighter = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyranid_anchor = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    near_enemy = _make_unit("Near Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    far_enemy = _make_unit("Far Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(fighter)
    gsc_army.add_unit(tyranid_anchor)
    enemy_army.add_unit(near_enemy)
    enemy_army.add_unit(far_enemy)
    _set_unit_position(fighter, 0.0, 0.0)
    _set_unit_position(tyranid_anchor, 10.0, 10.0)
    _set_unit_position(near_enemy, 10.5, 10.0)
    _set_unit_position(far_enemy, 25.0, 25.0)
    game.map.units = [fighter, tyranid_anchor, near_enemy, far_enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)

    manager = _stratagem_manager(gsc_player)
    manager.refresh_available()
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    used = manager.use("HYPERFEROCITY", unit=fighter, phase_name="Fight phase")
    assert bool(used) is True

    melee = _make_melee_profile()
    near_mods = fighter.get_unit_wound_reroll_modifiers(
        "melee",
        target=near_enemy,
        attacker_model=fighter.models[0],
        weapon_profile=melee,
    )
    far_mods = fighter.get_unit_wound_reroll_modifiers(
        "melee",
        target=far_enemy,
        attacker_model=fighter.models[0],
        weapon_profile=melee,
    )
    assert bool(near_mods.get("reroll_wound_full")) is True
    assert bool(far_mods.get("reroll_wound_full")) is False
    assert 1 in tuple(far_mods.get("reroll_wound_values", ()) or ())


def test_psi_surge_extends_catalyst_range_until_next_command_phase_start_and_enforces_cooldown():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 4

    gsc_attacker = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    tyranid_anchor = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(gsc_attacker)
    gsc_army.add_unit(tyranid_anchor)
    enemy_army.add_unit(enemy)
    game.map.units = [gsc_attacker, tyranid_anchor, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)

    game.map.get_distance_between_units = lambda unit_a, unit_b: 8.0 if unit_a is tyranid_anchor and unit_b is enemy else 99.0
    manager = _stratagem_manager(gsc_player)
    manager.refresh_available()
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)

    profile = _make_ranged_profile(name="Autogun")
    base_hit = profile._hit_target_with_tracking(
        enemy,
        gsc_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("Catalyst" in str(item or "") for item in list(base_hit.get("modifiers", []) or []))

    used = manager.use("PSI SURGE", unit=tyranid_anchor, phase_name="Shooting phase")
    assert bool(used) is True

    surged_hit = profile._hit_target_with_tracking(
        enemy,
        gsc_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Catalyst" in str(item or "") for item in list(surged_hit.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=gsc_player, phase=game.phase)
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)
    assert bool(manager.use("PSI SURGE", unit=tyranid_anchor, phase_name="Fight phase")) is False

    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.turn = 3
    game.event_system.publish("phase_start", player=gsc_player, phase=game.phase)
    cleared_hit = profile._hit_target_with_tracking(
        enemy,
        gsc_attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("Catalyst" in str(item or "") for item in list(cleared_hit.get("modifiers", []) or []))


def test_resistance_tunnels_queues_end_of_opponent_fight_phase_and_places_unit_in_strategic_reserves():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    target = _make_unit(
        "Raveners",
        faction_name="Tyranids",
        keywords=["TYRANIDS", "VANGUARD INVADER", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _set_unit_position(target, 0.0, 0.0)
    _set_unit_position(enemy, 20.0, 20.0)
    game.map.units = [target, enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)

    manager = _stratagem_manager(gsc_player)
    manager.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    pending = _pending_reaction_by_name(manager, "RESISTANCE TUNNELS")
    assert pending is not None

    used = manager.use(
        "RESISTANCE TUNNELS",
        unit=target,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert str(getattr(target, "reserve_status", "") or "") == "strategic_reserves"
    assert target not in list(getattr(game.map, "units", []) or [])
