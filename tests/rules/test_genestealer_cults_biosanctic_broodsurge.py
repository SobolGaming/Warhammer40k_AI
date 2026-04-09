from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Genestealer Cults",
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        model_count: int = 1,
        wounds: int = 4,
        objective_control: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Genestealer Cults",
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    model_count: int = 1,
    wounds: int = 4,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army.with_detachment("Genestealer Cults", "Biosanctic Broodsurge")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.battle_round_starting_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    gsc_army.configure_rule_managers(force=True)
    return game, gsc_army, enemy_army, gsc_player, enemy_player


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="GC",
        detachment="Biosanctic Broodsurge",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(name="Mutant Claws", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _stratagem_manager(player: Player):
    manager = getattr(player, "stratagems", None)
    assert manager is not None
    return manager


def _find_request(game: Game, *, decision_type: str, ability: str):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type or ""):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def _option_with_marker(request, *, relocation_mode: str | None = None):
    target_mode = str(relocation_mode or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        marker_id = str(payload.get("marker_id", "") or "").strip()
        if not marker_id:
            continue
        if target_mode and str(payload.get("relocation_mode", "") or "").strip().lower() != target_mode:
            continue
        return option
    return None


def test_biosanctic_broodsurge_enhancement_descriptors_registered() -> None:
    predatory = get_enhancement_tool_descriptor(enhancement_id="000009075002")
    assert predatory is not None
    assert predatory.name == "Predatory Instincts"
    assert predatory.effect_params.get("usage_scope") == "battle_round"

    biomorph = get_enhancement_tool_descriptor(enhancement_id="000009075003")
    assert biomorph is not None
    assert biomorph.name == "Biomorph Adaptation"
    assert biomorph.effect == "bearer_melee_ap_damage_bonus"

    regeneration = get_enhancement_tool_descriptor(enhancement_id="000009075004")
    assert regeneration is not None
    assert regeneration.name == "Mutagenic Regeneration"
    assert int(regeneration.effect_params.get("regain_wounds", 0) or 0) == 1

    majesty = get_enhancement_tool_descriptor(enhancement_id="000009075005")
    assert majesty is not None
    assert majesty.name == "Alien Majesty"
    assert majesty.effect == "enemy_objective_control_penalty_minimum"


def test_biosanctic_broodsurge_stratagem_descriptors_registered() -> None:
    expected = {
        "000009076002": ("EVASIVE VANGUARD", "relocate_cult_ambush_marker"),
        "000009076003": ("SAINTLY PAROXYSM", "roll_d6_then_deal_mortal_wounds_to_destroying_enemy"),
        "000009076004": ("GENE-TWISTED MUSCLE", "wound_roll_bonus_against_monster_or_vehicle"),
        "000009076005": ("HYPER-METABOLIC VIGOUR", "pile_in_and_consolidate_distance_override"),
        "000009076006": ("STIMULATED BIO-SURGE", "conditional_charge_roll_bonus_per_selected_target"),
        "000009076007": (
            "BIO-HORROR REVELATION",
            "enemy_shooters_within_9_take_leadership_test_or_suffer_hit_penalty_against_target",
        ),
    }

    for stratagem_id, (name, effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect


def test_bio_horror_revelation_queues_and_applies_attacker_scoped_hit_penalty() -> None:
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1
    gsc_player.command_points = 3

    aberrants = _make_unit(
        "Aberrants",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=3,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=2,
    )
    gsc_army.add_unit(aberrants)
    enemy_army.add_unit(enemy)
    _set_model_location(aberrants, 0.0, 0.0)
    _set_model_location(enemy, 5.0, 0.0)
    game.map.units = [aberrants, enemy]
    game.rebuild_entity_registry()

    manager = _stratagem_manager(gsc_player)
    manager._on_phase_start(enemy_player, BattleRoundPhases.SHOOTING_PHASE)
    assert any(
        str(entry.get("stratagem", "") or "").strip().upper() == "BIO-HORROR REVELATION"
        for entry in list(getattr(manager, "_pending_reactions", []) or [])
    )

    assert bool(manager.use("BIO-HORROR REVELATION", phase_name="Shooting phase", unit=aberrants))

    enemy.pass_leadership_check = lambda game=None: False
    manager._on_shooting_targets_selected(attacking_unit=enemy, target_units=[aberrants])

    effects = list(getattr(aberrants, "special_rules", {}).get("defensive_hit_mods", []) or [])
    assert len(effects) == 1
    effect = effects[0]
    assert int(effect.get("value", 0) or 0) == 1
    assert str(effect.get("attack_type", "") or "") == "ranged"
    assert str(effect.get("attacker_key", "") or "").strip()
    assert "BIO-HORROR REVELATION" in str(effect.get("source", "") or "")


def test_gene_twisted_muscle_grants_wound_bonus_against_vehicle_targets() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    gsc_player.command_points = 3

    aberrants = _make_unit(
        "Aberrants",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=3,
    )
    aberrants.round_state.charged_this_round = True
    vehicle = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )
    gsc_army.add_unit(aberrants)
    enemy_army.add_unit(vehicle)
    _set_model_location(aberrants, 0.0, 0.0)
    _set_model_location(vehicle, 0.75, 0.0)
    game.map.units = [aberrants, vehicle]
    game.rebuild_entity_registry()

    manager = _stratagem_manager(gsc_player)
    assert bool(manager.use("GENE-TWISTED MUSCLE", phase_name="Fight phase", unit=aberrants))

    wound_mods = aberrants.get_unit_wound_reroll_modifiers("melee", target=vehicle)
    assert int(wound_mods.get("wound", 0) or 0) >= 1
    assert any("GENE-TWISTED MUSCLE" in str(reason or "") for reason in list(wound_mods.get("wound_reasons", ()) or ()))


def test_hyper_metabolic_vigour_sets_and_cleans_fight_move_overrides() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    gsc_player.command_points = 3

    purestrains = _make_unit(
        "Purestrain Genestealers",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=2,
    )
    purestrains.round_state.charged_this_round = True
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)
    gsc_army.add_unit(purestrains)
    enemy_army.add_unit(enemy)
    _set_model_location(purestrains, 0.0, 0.0)
    _set_model_location(enemy, 0.75, 0.0)
    game.map.units = [purestrains, enemy]
    game.rebuild_entity_registry()

    manager = _stratagem_manager(gsc_player)
    assert bool(manager.use("HYPER-METABOLIC VIGOUR", phase_name="Fight phase", unit=purestrains))

    sr = dict(getattr(purestrains, "special_rules", {}) or {})
    assert float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0) == 6.0
    assert float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0) == 6.0
    assert str(sr.get("stratagem_choreographer_of_war_source", "") or "") == "HYPER-METABOLIC VIGOUR"

    gsc_army.genestealer_cults_detachments.cleanup_on_phase_end(BattleRoundPhases.FIGHT_PHASE, gsc_player)
    cleaned = dict(getattr(purestrains, "special_rules", {}) or {})
    assert "stratagem_pile_in_distance_override" not in cleaned
    assert "stratagem_consolidate_distance_override" not in cleaned
    assert "stratagem_choreographer_of_war_source" not in cleaned


def test_saintly_paroxysm_queues_and_rolls_2d3_for_patriarch() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    gsc_player.command_points = 3

    patriarch = _make_unit(
        "Patriarch",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=6,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=6)
    gsc_army.add_unit(patriarch)
    enemy_army.add_unit(enemy)
    _set_model_location(patriarch, 0.0, 0.0)
    _set_model_location(enemy, 0.75, 0.0)
    game.map.units = [patriarch, enemy]
    game.rebuild_entity_registry()

    patriarch._last_destroyed_by_unit = enemy
    patriarch._apply_mortal_wounds_to_unit = lambda target_unit, mortal_wound_amount, **_kwargs: setattr(
        target_unit, "_saintly_mortal_wounds", int(mortal_wound_amount)
    )

    manager = _stratagem_manager(gsc_player)
    manager._on_model_destroyed_before_removal(unit=patriarch, model=patriarch.models[0])
    assert any(
        str(entry.get("stratagem", "") or "").strip().upper() == "SAINTLY PAROXYSM"
        for entry in list(getattr(manager, "_pending_reactions", []) or [])
    )

    with patch("warhammer40k_ai.rules.stratagems_genestealer_cults.dice_module.get_roll", side_effect=[2, 2, 2]):
        assert bool(manager.use("SAINTLY PAROXYSM", phase_name="Fight phase"))
    assert int(getattr(enemy, "_saintly_mortal_wounds", 0) or 0) == 4


def test_stimulated_bio_surge_adds_bonus_per_selected_target_when_closest_is_included() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    gsc_player.command_points = 3

    purestrains = _make_unit(
        "Purestrain Genestealers",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=2,
    )
    closest_enemy = _make_unit("Closest Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=4)
    second_enemy = _make_unit("Second Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=4)
    gsc_army.add_unit(purestrains)
    enemy_army.add_unit(closest_enemy)
    enemy_army.add_unit(second_enemy)
    _set_model_location(purestrains, 0.0, 0.0)
    _set_model_location(closest_enemy, 5.0, 0.0)
    _set_model_location(second_enemy, 7.0, 0.0)
    game.map.units = [purestrains, closest_enemy, second_enemy]
    game.rebuild_entity_registry()

    manager = _stratagem_manager(gsc_player)
    assert bool(manager.use("STIMULATED BIO-SURGE", phase_name="Charge phase", unit=purestrains))

    modifiers = list(game._collect_charge_modifiers(purestrains, target_unit=[closest_enemy, second_enemy]) or [])
    stimulated = [item for item in modifiers if str(item[1] or "").strip().upper() == "STIMULATED BIO-SURGE"]
    assert stimulated == [(2, "STIMULATED BIO-SURGE")]

    without_closest = list(game._collect_charge_modifiers(purestrains, target_unit=[second_enemy]) or [])
    assert not any(str(item[1] or "").strip().upper() == "STIMULATED BIO-SURGE" for item in without_closest)


def test_evasive_vanguard_requests_marker_relocation_and_spends_cp_on_apply() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1
    gsc_player.command_points = 2

    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=4)
    enemy_army.add_unit(enemy)
    _set_model_location(enemy, 40.0, 0.0)
    game.map.units = [enemy]
    game.rebuild_entity_registry()

    manager = gsc_army.cult_ambush
    marker = manager.place_marker_at(game, 10.0, 0.0)
    assert marker is not None

    _set_model_location(enemy, 18.0, 0.0)
    game.map.units = [enemy]
    game.rebuild_entity_registry()

    manager.on_enemy_unit_move_ended(enemy, game=game)
    request = _find_request(game, decision_type=DECISION_PICK_POINT, ability="evasive_vanguard_marker_relocation")
    assert request is not None

    marker_option = _option_with_marker(request)
    assert marker_option is not None

    result = resolve_decision_command(
        game,
        request,
        marker_option.option_id,
        result_payload={"point": [3.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True
    active_markers = list(manager.get_active_markers() or [])
    assert len(active_markers) == 1
    relocated = active_markers[0]
    assert float(getattr(relocated, "x", -1.0) or -1.0) == 3.0
    assert float(getattr(relocated, "y", -1.0)) == 0.0
    assert int(getattr(gsc_player, "command_points", 0) or 0) == 1


def test_predatory_instincts_grants_infiltrators_to_attached_unit_while_bearer_lives() -> None:
    game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Patriarch",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=6,
    )
    bodyguard = _make_unit(
        "Aberrants",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=3,
    )
    gsc_army.add_unit(leader)
    gsc_army.add_unit(bodyguard)
    _set_model_location(leader, 0.0, 0.0)
    _set_model_location(bodyguard, 0.0, 2.0)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000009075002",
        name="Predatory Instincts",
        description=(
            "Abominant, Biophagus or Patriarch model only. Models in the bearer's unit have the Infiltrators ability "
            "and, once per battle round, you can target the bearer's unit with the Heroic Intervention Stratagem for "
            "0CP, and can do so even if you have already targeted a different unit with that Stratagem this phase."
        ),
    )

    assert bool(leader.has_infiltrate())
    assert not bool(bodyguard.has_infiltrate())

    _attach_leader(bodyguard, leader)
    assert bool(bodyguard.has_infiltrate())

    bearer = _bearer_model(leader)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
    assert not bool(bodyguard.has_infiltrate())


def test_predatory_instincts_heroic_intervention_discount_is_once_per_battle_round() -> None:
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 1

    leader = _make_unit(
        "Patriarch",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=6,
    )
    bodyguard = _make_unit(
        "Purestrain Genestealers",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=2,
    )
    other_unit = _make_unit(
        "Neophyte Hybrids",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=2,
    )
    gsc_army.add_unit(leader)
    gsc_army.add_unit(bodyguard)
    gsc_army.add_unit(other_unit)
    game.map.units = [leader, bodyguard, other_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000009075002",
        name="Predatory Instincts",
        description=(
            "Abominant, Biophagus or Patriarch model only. Models in the bearer's unit have the Infiltrators ability "
            "and, once per battle round, you can target the bearer's unit with the Heroic Intervention Stratagem for "
            "0CP, and can do so even if you have already targeted a different unit with that Stratagem this phase."
        ),
    )
    _attach_leader(bodyguard, leader)

    rule = bodyguard.get_snarling_protector_heroic_intervention_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("usage_key", "") or "") == "PREDATORY_INSTINCTS_HEROIC_INTERVENTION"
    assert str(rule.get("usage_scope", "") or "") == "battle_round"

    manager = StratagemManager(gsc_player)
    manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
    manager._record_heroic_intervention_use(other_unit)
    assert bool(manager._heroic_intervention_repeat_allowed(target_unit=bodyguard))

    stratagem = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
    gsc_player.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
    applied = gsc_player.apply_stratagem_cp_cost(stratagem, target_unit=bodyguard)
    assert int(applied.get("cost", -1)) == 0
    assert bool(applied.get("snarling_protector_heroic_intervention_use", False))

    gsc_player.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
    applied_again = gsc_player.apply_stratagem_cp_cost(stratagem, target_unit=bodyguard)
    assert int(applied_again.get("cost", -1)) == 1
    assert not bool(applied_again.get("snarling_protector_heroic_intervention_use", False))

    game.turn = 2
    gsc_player.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
    applied_next_round = gsc_player.apply_stratagem_cp_cost(stratagem, target_unit=bodyguard)
    assert int(applied_next_round.get("cost", -1)) == 0
    assert bool(applied_next_round.get("snarling_protector_heroic_intervention_use", False))


def test_biomorph_adaptation_improves_bearer_melee_ap_and_damage() -> None:
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()
    attacker_unit = _make_unit(
        "Abominant",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=6,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)
    gsc_army.add_unit(attacker_unit)
    enemy_army.add_unit(enemy)
    _set_model_location(attacker_unit, 0.0, 0.0)
    _set_model_location(enemy, 1.0, 0.0)
    game.map.units = [attacker_unit, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        attacker_unit,
        enhancement_id="000009075003",
        name="Biomorph Adaptation",
        description=(
            "Abominant or Patriarch model only. Improve the Armour Penetration and Damage characteristics of melee "
            "weapons equipped by the bearer by 1."
        ),
    )

    bearer = _bearer_model(attacker_unit)
    assert bearer is not None
    assert int(attacker_unit.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0) == 1
    assert int(attacker_unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0) == 1

    melee_profile = _make_melee_profile(ap=0)
    assert int(melee_profile.get_effective_ap(attacker=bearer, target=enemy) or 0) == -1

    attack_instance = {
        "_aura_attack_mods": SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        ),
        "mortal_wound": False,
        "mortal_wound_in_addition": False,
    }
    damage_result = melee_profile._damage_target_with_tracking(
        enemy.models[0],
        bearer,
        attack_instance,
        allow_rerolls=False,
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 2


def test_mutagenic_regeneration_heals_most_damaged_model_in_bearers_attached_unit() -> None:
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    leader = _make_unit(
        "Biophagus",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=5,
    )
    bodyguard = _make_unit(
        "Aberrants",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=3,
    )
    gsc_army.add_unit(leader)
    gsc_army.add_unit(bodyguard)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000009075004",
        name="Mutagenic Regeneration",
        description="Abominant, Biophagus or Patriarch model only. In each Command phase, one model in the bearer's unit regains 1 lost wound.",
    )
    _attach_leader(bodyguard, leader)

    bearer = _bearer_model(leader)
    assert bearer is not None
    bearer_base = int(getattr(bearer, "_base_wounds", getattr(bearer, "wounds", 0)) or 0)
    bearer.wounds = max(1, bearer_base - 1)

    damaged_bodyguard = bodyguard.models[0]
    bodyguard_base = int(getattr(damaged_bodyguard, "_base_wounds", getattr(damaged_bodyguard, "wounds", 0)) or 0)
    damaged_bodyguard.wounds = max(1, bodyguard_base - 2)

    game._apply_command_phase_regain_wounds(gsc_player, timing="start")
    assert int(damaged_bodyguard.wounds or 0) == bodyguard_base - 1
    assert int(bearer.wounds or 0) == bearer_base - 1

    damaged_bodyguard.wounds = max(1, bodyguard_base - 2)
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    game._apply_command_phase_regain_wounds(gsc_player, timing="start")
    assert int(damaged_bodyguard.wounds or 0) == bodyguard_base - 2


def test_alien_majesty_uses_bearers_attached_unit_for_engagement_range_oc_penalty() -> None:
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Patriarch",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        wounds=6,
    )
    bodyguard = _make_unit(
        "Purestrain Genestealers",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
        model_count=2,
        wounds=2,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], objective_control=2)
    enemy_low = _make_unit("Enemy Low", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], objective_control=1)
    gsc_army.add_unit(leader)
    gsc_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(enemy_low)

    _apply_enhancement(
        leader,
        enhancement_id="000009075005",
        name="Alien Majesty",
        description=(
            "Abominant, Biophagus or Patriarch model only. While an enemy unit is within Engagement Range of the "
            "bearer's unit, subtract 1 from the Objective Control characteristic of models in that enemy unit "
            "(to a minimum of 1)."
        ),
    )
    _attach_leader(bodyguard, leader)

    class _Map:
        def get_enemy_units(self, unit):
            if unit is enemy or unit is enemy_low:
                return [leader]
            return []

        def get_friendly_units(self, unit):
            if unit is enemy:
                return [enemy]
            if unit is enemy_low:
                return [enemy_low]
            if unit is leader or unit is bodyguard:
                return [leader, bodyguard]
            return []

        def is_within_engagement_range(self, unit_a, unit_b):
            pair = {unit_a, unit_b}
            return pair == {bodyguard, enemy} or pair == {bodyguard, enemy_low}

    assert int(enemy.get_effective_model_characteristic(enemy.models[0], "objective_control", game_map=_Map()) or 0) == 1
    assert int(enemy_low.get_effective_model_characteristic(enemy_low.models[0], "objective_control", game_map=_Map()) or 0) == 1
