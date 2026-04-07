from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        leadership: str = "7",
        toughness: str = "5",
    ):
        self.id = str(datasheet_id)
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
                "Sv": "3",
                "W": "4",
                "Ld": str(leadership),
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
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


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    faction_keywords,
    keywords=None,
    abilities=None,
    leadership: str = "7",
    toughness: str = "5",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            leadership=leadership,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army.with_detachment("Death Guard", "Plague Company")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_army, enemy_army, dg_player, enemy_player


def _deploy(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _make_ranged_profile(name: str, *, blast: bool = False) -> WargearProfile:
    desc = "[BLAST]" if blast else ""
    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": "1",
            "description": desc,
        },
    )
    profile.parent_wargear = SimpleNamespace(
        name=name,
        is_ranged=lambda: True,
        is_melee=lambda: False,
    )
    return profile


def test_blight_bombardment_marks_target_and_enables_hit_rerolls():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Blight Bombardment",
        "description": (
            "At the start of your Shooting phase, select one enemy unit within 30\" of and visible to this model. "
            "Until the end of the phase, each time a friendly Death Guard model makes a ranged attack that targets that "
            "unit, re-roll a Hit roll of 1 (if that attack is made with a Blast weapon, you can re-roll the Hit roll instead)."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Lord of Virulence",
        "dg-lov",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "CHARACTER"],
        abilities=[ability],
    )
    target = _make_unit(
        "Enemy Target",
        "en-target",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy(source, target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    source._has_line_of_sight_to_target = lambda _model, _target, _map: True

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    game._on_phase_start_shooting_phase_blight_bombardment(player=dg_player, phase=game.phase)

    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "blight_bombardment"
    )
    resolve_decision_command(game, request, request.options[0].option_id, player_id=dg_player.id)

    sr = getattr(target, "special_rules", {})
    assert bool(sr.get("blight_bombardment_active")) is True

    blast_profile = _make_ranged_profile("Plagueburst mortar", blast=True)
    non_blast_profile = _make_ranged_profile("Twin plague spewer", blast=False)
    blast_rule = blast_profile._blight_bombardment_hit_reroll_rule(source.models[0], target)
    non_blast_rule = non_blast_profile._blight_bombardment_hit_reroll_rule(source.models[0], target)

    assert bool((blast_rule or {}).get("reroll_full")) is True
    assert tuple((non_blast_rule or {}).get("reroll_values", ())) == (1,)


def test_eater_plague_excludes_lone_operative_beyond_12_and_applies_mortals():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Eater Plague (Psychic)",
        "description": (
            "In your Shooting phase, you can select one enemy unit within 18\" of and visible to this PSYKER "
            "(excluding units with the Lone Operative ability that are not part of an Attached unit and are not within "
            "12\" of this PSYKER) and roll one D6: on a 1, this PSYKER's unit suffers D3 mortal wounds; on a 2-5, "
            "that enemy unit suffers D6 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Typhus",
        "dg-typhus",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "PSYKER", "CHARACTER"],
        abilities=[ability],
    )
    normal_target = _make_unit(
        "Normal Target",
        "en-normal",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    lone_target = _make_unit(
        "Lone Target",
        "en-lone",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    lone_target.has_lone_operative = lambda: True

    dg_army.add_unit(source)
    enemy_army.add_unit(normal_target)
    enemy_army.add_unit(lone_target)
    _deploy(source, normal_target, lone_target)
    game.map.units = [source, normal_target, lone_target]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    normal_target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    lone_target.models[0].set_location(16.0, 0.0, 0.0, 0.0)
    source._has_line_of_sight_to_target = lambda _model, _target, _map: True

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    game._on_phase_start_shooting_phase_eater_plague(player=dg_player, phase=game.phase)
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "eater_plague"
    )
    option_payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
    target_ids = {str(p.get("target_unit_id", "") or "") for p in option_payloads}
    assert str(normal_target._id) in target_ids
    assert str(lone_target._id) not in target_ids

    chosen = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(normal_target._id)
    )
    applied = []
    source._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    rolls = iter([2, 4])
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=lambda _spec: next(rolls)):
        resolve_decision_command(game, request, chosen.option_id, player_id=dg_player.id)

    assert applied == [(normal_target, 4)]


def test_metalophagic_infection_queues_and_applies_afflicted_bonus():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Metalophagic Infection",
        "description": (
            "In your Shooting phase, after this model has shot, select one enemy MONSTER or VEHICLE unit hit by one or more "
            "of those attacks. Roll one D6, adding 1 to the result if that unit is Afflicted; on a 5+, that unit suffers D3 "
            "mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Chaos Predator Annihilator",
        "dg-pred",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["VEHICLE"],
        abilities=[ability],
    )
    target = _make_unit(
        "Enemy Vehicle",
        "en-veh",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["VEHICLE"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy(source, target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    model = source.models[0]
    game._on_unit_shooting_resolved_post_shoot_monster_vehicle_mortal_threshold(
        attacker_unit=source,
        hits_by_target={target: 1},
        hit_models_by_target={target: {model}},
    )

    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "metalophagic_infection"
    )
    source._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: setattr(source, "_last_metalophagic", (unit, int(amount)))

    rolls = iter([4, 2])
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=lambda _spec: next(rolls)), patch(
        "warhammer40k_ai.rules.nurgles_gift.NurglesGiftManager.get_afflicted_plague_for_unit",
        return_value=object(),
    ):
        resolve_decision_command(game, request, request.options[0].option_id, player_id=dg_player.id)

    assert getattr(source, "_last_metalophagic", None) == (target, 2)


def test_spore_laced_shock_waves_applies_once_and_does_not_repeat_on_later_turns():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Spore-laced Shock Waves",
        "description": (
            "In your Shooting phase, each time you select a target for this model's Plagueburst mortar, roll one D6 for the "
            "target unit and every other enemy unit within 3\" of the target unit, adding 1 to that roll if the unit being "
            "rolled for is Afflicted. On a 6+, the unit being rolled for is struck by spores; after resolving all of this model's "
            "attacks against the target unit, each unit struck by spores suffers D3 mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Plagueburst Crawler",
        "dg-pbc",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["VEHICLE"],
        abilities=[ability],
    )
    target = _make_unit(
        "Target",
        "en-target",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    nearby = _make_unit(
        "Nearby",
        "en-near",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    far = _make_unit(
        "Far",
        "en-far",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(target)
    enemy_army.add_unit(nearby)
    enemy_army.add_unit(far)
    _deploy(source, target, nearby, far)
    game.map.units = [source, target, nearby, far]
    game.rebuild_entity_registry()

    target.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    nearby.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    far.models[0].set_location(8.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    profile = _make_ranged_profile("Plagueburst mortar")
    declaration = {
        "weapon_profile": profile,
        "target_unit": target,
        "models": [source.models[0]],
    }

    applied = []
    source._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    rolls = iter([6, 6, 2, 2])
    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", side_effect=lambda _spec: next(rolls)):
        game._on_shooting_targets_selected_spore_laced_shock_waves(
            attacking_unit=source,
            target_units=[target],
            weapon_declarations=[declaration],
        )
        entries = list(getattr(source, "special_rules", {}).get("spore_laced_shock_waves_pending_entries", []) or [])
        assert len(entries) == 1
        game._on_unit_shooting_resolved_spore_laced_shock_waves(attacker_unit=source)

    assert len(applied) == 2
    assert {u for u, _amt in applied} == {target, nearby}
    assert {amt for _u, amt in applied} == {2}
    special_rules = getattr(source, "special_rules", {}) or {}
    assert "spore_laced_shock_waves_pending_entries" not in special_rules
    assert "spore_laced_shock_waves_owner" not in special_rules
    assert "spore_laced_shock_waves_turn" not in special_rules

    game.turn = 3
    game._on_unit_shooting_resolved_spore_laced_shock_waves(attacker_unit=source)
    assert len(applied) == 2


def test_blistering_fusillade_applies_strength_and_ap_vs_afflicted():
    ability = {
        "name": "Blistering Fusillade",
        "description": (
            "If this unit has a Starting Strength of 5 or more, or if a Character is leading this unit, then each time a "
            "model in this unit makes a ranged attack that targets an Afflicted unit, improve the Strength and Armour "
            "Penetration characteristics of that attack by 1."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Blightlord Terminators",
        "dg-blightlords",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[ability],
    )
    leader = _make_unit(
        "Leader",
        "dg-leader",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["CHARACTER"],
    )
    source.attached_leaders = [leader]
    leader.attached_to = source

    target = _make_unit(
        "Afflicted Target",
        "en-afflicted",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
        toughness="5",
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(target)
    _deploy(source, target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    profile = _make_ranged_profile("Combi-bolter")
    attacker = source.models[0]

    with patch(
        "warhammer40k_ai.rules.nurgles_gift.NurglesGiftManager.get_afflicted_plague_for_unit",
        return_value=object(),
    ):
        ap_val = profile.get_effective_ap(attacker, target)
        wound = profile._wound_target_with_tracking(
            target,
            attacker,
            {"target_unit": target, "attacker_model": attacker},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )

    assert int(ap_val) == -2
    assert bool(wound.get("wound")) is True


def test_putrefying_stink_blocks_advance_start_or_end_within_range():
    from warhammer40k_ai.engine.decision_handlers.movement import _validate_advance_start_end_denial

    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    denial = {
        "name": "Putrefying Stink",
        "description": "Enemy models cannot start or end an Advance move within 9\" of this model.",
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Foul Blightspawn",
        "dg-fb",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "CHARACTER"],
        abilities=[denial],
    )
    mover = _make_unit(
        "Enemy Mover",
        "en-mover",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(mover)
    _deploy(source, mover)
    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    mover.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    game.map.units = [source, mover]

    blocked_start = _validate_advance_start_end_denial(
        game,
        mover,
        [{"model_id": str(mover.models[0]._id), "position": [11.0, 0.0, 0.0], "facing": 0.0}],
    )
    assert blocked_start

    mover.models[0].set_location(12.0, 0.0, 0.0, 0.0)
    blocked_end = _validate_advance_start_end_denial(
        game,
        mover,
        [{"model_id": str(mover.models[0]._id), "position": [8.0, 0.0, 0.0], "facing": 0.0}],
    )
    assert blocked_end


def test_bio_minefield_blocks_advance_start_or_end_within_range_for_multi_model_source():
    from warhammer40k_ai.engine.decision_handlers.movement import _validate_advance_start_end_denial

    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    denial = {
        "name": "Bio-minefield",
        "description": "Enemy units cannot start or end an Advance move within 6\" of this unit.",
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Spore Mines",
        "tyr-spore-mines",
        faction_name="Tyranids",
        faction_keywords=["TYRANIDS"],
        keywords=["INFANTRY"],
        abilities=[denial],
    )
    source_donor = _make_unit(
        "Spore Mines",
        "tyr-spore-mines-donor",
        faction_name="Tyranids",
        faction_keywords=["TYRANIDS"],
        keywords=["INFANTRY"],
    )
    source.add_model(source_donor.models[0])
    mover = _make_unit(
        "Enemy Mover",
        "en-mover",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(mover)
    _deploy(source, mover)
    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    source.models[1].set_location(2.0, 0.0, 0.0, 0.0)
    mover.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    game.map.units = [source, mover]

    specs = source.unit_no_advance_start_or_end_within_specs()
    assert len(specs) == 1
    assert specs[0]["source"] == "Bio-minefield"
    assert specs[0]["range"] == 6

    blocked_start = _validate_advance_start_end_denial(
        game,
        mover,
        [{"model_id": str(mover.models[0]._id), "position": [9.0, 0.0, 0.0], "facing": 0.0}],
    )
    assert blocked_start

    mover.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    blocked_end = _validate_advance_start_end_denial(
        game,
        mover,
        [{"model_id": str(mover.models[0]._id), "position": [4.0, 0.0, 0.0], "facing": 0.0}],
    )
    assert blocked_end


def test_death_approaches_deep_strike_distance_split():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Death Approaches",
        "description": (
            "In your Movement phase, when this unit is set up on the battlefield using the Deep Strike ability, it can be "
            "set up anywhere on the battlefield that is more than 6\" horizontally away from all Afflicted enemy units, and "
            "more than 9\" horizontally away from all other enemy units."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    arriving = _make_unit(
        "Deathshroud Terminators",
        "dg-deathshroud",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[ability],
    )
    afflicted_enemy = _make_unit(
        "Afflicted Enemy",
        "en-afflicted",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        "en-other",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    arriving.reserve_status = "reserves"
    arriving.deployed = False
    dg_army.add_unit(arriving)
    enemy_army.add_unit(afflicted_enemy)
    enemy_army.add_unit(other_enemy)
    _deploy(afflicted_enemy, other_enemy)

    afflicted_enemy.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    other_enemy.models[0].set_location(25.0, 0.0, 0.0, 0.0)
    game.map.units = [afflicted_enemy, other_enemy]

    def _afflicted_side_effect(unit, **_kwargs):
        if unit is afflicted_enemy:
            return object()
        return None

    with patch(
        "warhammer40k_ai.rules.nurgles_gift.NurglesGiftManager.get_afflicted_plague_for_unit",
        side_effect=_afflicted_side_effect,
    ):
        assert game.can_place_unit_arriving_from_reserves(arriving, (8.0, 0.0, 0.0)) is True
        assert game.can_place_unit_arriving_from_reserves(arriving, (7.0, 0.0, 0.0)) is False
        assert game.can_place_unit_arriving_from_reserves(arriving, (15.0, 0.0, 0.0)) is False


def test_host_of_plagues_end_movement_applies_afflicted_bonus_threshold():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Host of Plagues",
        "description": (
            "At the end of your Movement phase, roll one D6 for each enemy unit within 6\" of this model, adding 1 to the "
            "result if that enemy unit is Afflicted: on a 3+, that enemy unit suffers D3 mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Mortarion",
        "dg-mortarion",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "CHARACTER"],
        abilities=[ability],
    )
    afflicted_target = _make_unit(
        "Afflicted Enemy",
        "en-afflicted",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    non_afflicted_target = _make_unit(
        "Non Afflicted Enemy",
        "en-non-afflicted",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    far_target = _make_unit(
        "Far Enemy",
        "en-far",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(afflicted_target)
    enemy_army.add_unit(non_afflicted_target)
    enemy_army.add_unit(far_target)
    _deploy(source, afflicted_target, non_afflicted_target, far_target)
    game.map.units = [source, afflicted_target, non_afflicted_target, far_target]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    afflicted_target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    non_afflicted_target.models[0].set_location(5.2, 0.0, 0.0, 0.0)
    far_target.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    applied = []
    source._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    def _afflicted_side_effect(unit, **_kwargs):
        if unit is afflicted_target:
            return object()
        return None

    with patch(
        "warhammer40k_ai.rules.nurgles_gift.NurglesGiftManager.get_afflicted_plague_for_unit",
        side_effect=_afflicted_side_effect,
    ), patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game._on_phase_end_movement_phase_mortal_table(player=dg_player, phase=game.phase)

    assert {u for u, _amt in applied} == {afflicted_target}
    assert {amt for _u, amt in applied} == {2}


def test_horrifying_visage_select_one_decision_and_apply():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    ability = {
        "name": "Horrifying Visage",
        "description": (
            "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it; that enemy unit "
            "must take a Battle-shock test, subtracting 1 from that test."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Deathshroud Terminators",
        "dg-source",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
        abilities=[ability],
    )
    enemy_a = _make_unit(
        "Enemy A",
        "en-a",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_b = _make_unit(
        "Enemy B",
        "en-b",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy(source, enemy_a, enemy_b)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0

    game.map.get_enemy_units = lambda _unit: [enemy_a, enemy_b]
    game.map.is_within_engagement_range = lambda _a, _b: True

    enemy_a._tests = []
    enemy_a.take_battle_shock_test = lambda turn: enemy_a._tests.append(int(turn))

    game._on_unit_move_ended_charge_battleshock(unit=source, action="charge")

    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "charge_end_select_one_battleshock"
    )
    choice = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(enemy_a._id)
    )
    resolve_decision_command(game, request, choice.option_id, player_id=dg_player.id)

    assert enemy_a._tests == [2]
    assert int(getattr(enemy_a, "special_rules", {}).get("battle_shock_test_modifier", 0) or 0) == -1


def test_lord_of_the_death_guard_boon_of_death_applies_and_is_once_per_turn():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Mortarion",
        "dg-mortarion",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "CHARACTER"],
        abilities=[
            {"name": "Lord of the Death Guard", "description": "Once per turn, this model can use one of the Lord of the Death Guard abilities (see left).", "type": "Datasheet", "parameter": ""},
            {"name": "Boon of Death", "description": "In your opponent's Fight phase, after an enemy unit has selected its targets, select one friendly DEATH GUARD unit within 6\" of this model selected as a target of one or more of those attacks. Until the end of the phase, each time a model in that unit is destroyed by a melee attack, if that model has not fought this phase, roll one D6: on a 2+, do not remove it from play; that destroyed model can fight after the attacking unit has finished making its attacks, and is then removed from play.", "type": "Datasheet", "parameter": ""},
        ],
    )
    friendly = _make_unit(
        "Plague Marines",
        "dg-friendly",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    enemy_attacker = _make_unit(
        "Enemy Attacker",
        "en-attacker",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(friendly)
    enemy_army.add_unit(enemy_attacker)
    _deploy(source, friendly, enemy_attacker)
    game.map.units = [source, friendly, enemy_attacker]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_attacker.models[0].set_location(2.5, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    game._on_fight_targets_selected_boon_of_death(attacking_unit=enemy_attacker, target_units=[friendly])
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "")) == DECISION_CHOOSE_QUARRY
        and str((getattr(r, "context", {}) or {}).get("ability", "")) == "boon_of_death"
    )
    option = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(friendly._id)
    )
    cmd_result = resolve_decision_command(game, request, option.option_id, player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is True

    sr = getattr(friendly, "special_rules", {})
    assert bool(sr.get("boon_of_death_active")) is True
    assert source.lord_of_death_guard_used_this_turn(game=game) is True

    game._on_fight_targets_selected_boon_of_death(attacking_unit=enemy_attacker, target_units=[friendly])
    pending = [
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "boon_of_death"
    ]
    assert pending == []


def test_lord_of_the_death_guard_boon_of_death_invalid_option_is_rejected():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Mortarion",
        "dg-mortarion",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "CHARACTER"],
        abilities=[
            {"name": "Lord of the Death Guard", "description": "Once per turn, this model can use one of the Lord of the Death Guard abilities (see left).", "type": "Datasheet", "parameter": ""},
            {"name": "Boon of Death", "description": "Reactive boon.", "type": "Datasheet", "parameter": ""},
        ],
    )
    friendly = _make_unit(
        "Plague Marines",
        "dg-friendly",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    enemy_attacker = _make_unit(
        "Enemy Attacker",
        "en-attacker",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(friendly)
    enemy_army.add_unit(enemy_attacker)
    _deploy(source, friendly, enemy_attacker)
    game.map.units = [source, friendly, enemy_attacker]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_attacker.models[0].set_location(2.5, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    game._on_fight_targets_selected_boon_of_death(attacking_unit=enemy_attacker, target_units=[friendly])
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "boon_of_death"
    )
    cmd_result = resolve_decision_command(game, request, "invalid-option-id", player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is False
    assert source.lord_of_death_guard_used_this_turn(game=game) is False


def test_inflamed_infections_queues_and_marks_target():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Plague Surgeon",
        "dg-surgeon",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "CHARACTER"],
        abilities=[
            {
                "name": "Inflamed Infections",
                "description": (
                    "At the start of the Fight phase, you can select one enemy unit within Engagement Range of this model. "
                    "Until the end of the phase, each time this model makes an attack that targets that unit, an unmodified "
                    "Hit roll of 5+ scores a Critical Hit (or 4+ if that unit is Below Half-strength)."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "en-unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy(source, enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(1.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    game._on_phase_start_inflamed_infections(player=dg_player, phase=game.phase)
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "inflamed_infections"
    )
    choice = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(enemy._id)
    )
    cmd_result = resolve_decision_command(game, request, choice.option_id, player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is True

    sr = getattr(enemy, "special_rules", {})
    assert bool(sr.get("inflamed_infections_active")) is True
    assert int(sr.get("inflamed_infections_crit_hit_threshold", 0) or 0) == 5
    assert int(sr.get("inflamed_infections_crit_hit_threshold_below_half", 0) or 0) == 4


def test_diseased_influence_queues_reactive_move():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Mortarion",
        "dg-mortarion",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "CHARACTER"],
        abilities=[
            {"name": "Lord of the Death Guard", "description": "Once per turn, this model can use one of the Lord of the Death Guard abilities (see left).", "type": "Datasheet", "parameter": ""},
            {"name": "Diseased Influence", "description": "Reactive move.", "type": "Datasheet", "parameter": ""},
        ],
    )
    friendly = _make_unit(
        "Death Guard Unit",
        "dg-friendly",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    mover = _make_unit(
        "Enemy Mover",
        "en-mover",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(friendly)
    enemy_army.add_unit(mover)
    _deploy(source, friendly, mover)
    game.map.units = [source, friendly, mover]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    mover.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    game.map.get_enemy_units = lambda unit: [mover] if unit is friendly else []
    game.map.is_within_engagement_range = lambda _a, _b: False

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1

    game._on_unit_move_ended_diseased_influence(unit=mover, action="move")
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "diseased_influence"
    )
    choice = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(friendly._id)
    )

    captured = {}

    def _capture_reactive_move(**kwargs):
        captured.update(kwargs)

    game._queue_reactive_move_movement_decision = _capture_reactive_move
    cmd_result = resolve_decision_command(game, request, choice.option_id, player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is True
    assert captured.get("unit") is friendly
    assert int(captured.get("max_distance", 0) or 0) == 5
    assert str(captured.get("kind", "")) == "diseased_influence"
    assert source.lord_of_death_guard_used_this_turn(game=game) is True


def test_inflamed_reprisal_triggers_reactive_shooting_after_enemy_resolves():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Mortarion",
        "dg-mortarion",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["MONSTER", "CHARACTER"],
        abilities=[
            {"name": "Lord of the Death Guard", "description": "Once per turn, this model can use one of the Lord of the Death Guard abilities (see left).", "type": "Datasheet", "parameter": ""},
            {"name": "Inflamed Reprisal", "description": "Reactive shooting.", "type": "Datasheet", "parameter": ""},
        ],
    )
    friendly = _make_unit(
        "Death Guard Unit",
        "dg-friendly",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY"],
    )
    enemy_attacker = _make_unit(
        "Enemy Shooter",
        "en-attacker",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(friendly)
    enemy_army.add_unit(enemy_attacker)
    _deploy(source, friendly, enemy_attacker)
    game.map.units = [source, friendly, enemy_attacker]
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_attacker.models[0].set_location(8.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    game._on_shooting_targets_selected_inflamed_reprisal(attacking_unit=enemy_attacker, target_units=[friendly])
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "inflamed_reprisal"
    )
    choice = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("target_unit_id", "")) == str(friendly._id)
    )
    cmd_result = resolve_decision_command(game, request, choice.option_id, player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is True

    game._setup_reactive_can_shoot_target = lambda _u, _t: True
    captured = {}

    def _queue_reactive_shoot(*, player, unit, target_unit, source):
        captured["player"] = player
        captured["unit"] = unit
        captured["target_unit"] = target_unit
        captured["source"] = source
        return SimpleNamespace(context={})

    game._queue_setup_reactive_shooting_decision = _queue_reactive_shoot
    game._on_unit_shooting_resolved_inflamed_reprisal(attacker_unit=enemy_attacker)

    assert captured.get("unit") is friendly
    assert captured.get("target_unit") is enemy_attacker
    assert str(captured.get("source", "")) == "Inflamed Reprisal"


def test_curse_of_walking_pox_tracks_kills_and_returns_models():
    game, dg_army, enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Poxwalkers",
        "dg-pox",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "POXWALKER"],
        abilities=[
            {
                "name": "Curse of the Walking Pox",
                "description": "Each time a model in this unit destroys an enemy model, return destroyed Poxwalkers.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "en-unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy(source, enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    source_model = source.models[0]
    target_model = enemy.models[0]
    game._on_model_destroyed_curse_of_the_walking_pox(
        attacker_model=source_model,
        attacker_unit=source,
        target_model=target_model,
        target_unit=enemy,
    )
    assert int(getattr(source, "special_rules", {}).get("curse_of_walking_pox_pending_kills", 0) or 0) == 1

    destroyed_model = SimpleNamespace(
        has_any_keyword=lambda kw: str(kw or "").strip().upper() == "POXWALKER",
        has_keyword=lambda kw: str(kw or "").strip().upper() == "POXWALKER",
    )
    source.models_lost = [destroyed_model]
    source.return_destroyed_bodyguard_models = lambda count, **_kwargs: int(count)

    game._on_unit_shooting_resolved_curse_of_the_walking_pox(attacker_unit=source)
    request = next(
        r
        for r in list(game.decision_queue.list() or [])
        if str((getattr(r, "context", {}) or {}).get("ability", "")) == "curse_of_walking_pox"
    )
    option = next(opt for opt in list(request.options or []) if int((opt.payload or {}).get("returns", 0) or 0) == 1)
    cmd_result = resolve_decision_command(game, request, option.option_id, player_id=dg_player.id)
    assert bool(getattr(cmd_result, "ok", False)) is True
    assert int(getattr(source, "special_rules", {}).get("curse_of_walking_pox_pending_kills", 0) or 0) == 0


def test_lethal_ichor_applies_mortals_after_fight_sequence():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    defender = _make_unit(
        "Chaos Spawn",
        "dg-spawn",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["BEAST"],
        abilities=[{"name": "Lethal Ichor", "description": "When attacks are allocated, roll and deal mortals.", "type": "Datasheet", "parameter": ""}],
    )
    attacker = _make_unit(
        "Enemy Attacker",
        "en-attacker",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy(defender, attacker)
    game.map.units = [defender, attacker]
    game.rebuild_entity_registry()
    game.map.get_enemy_units = lambda unit: [defender] if unit is attacker else [attacker]

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1

    attacker_id = str(attacker._id)
    defender.special_rules["lethal_ichor_allocations"] = {attacker_id: 3}
    defender.special_rules["lethal_ichor_source"] = "Lethal Ichor"
    applied = []
    defender._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    rolls = iter([4, 2, 5])
    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", side_effect=lambda _spec: next(rolls)):
        game._on_fight_sequence_complete_lethal_ichor(unit=attacker)

    assert applied == [(attacker, 2)]
    assert "lethal_ichor_allocations" not in getattr(defender, "special_rules", {})


def test_explosive_blight_marks_nearby_enemy_units_as_afflicted():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    attacker = _make_unit(
        "Foetid Bloat-drone with Heavy Blight Launcher",
        "dg-drone",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["VEHICLE"],
        abilities=[{"name": "Explosive Blight", "description": "Destroyed unit explosion afflicts nearby enemies.", "type": "Datasheet", "parameter": ""}],
    )
    destroyed = _make_unit(
        "Destroyed Unit",
        "en-destroyed",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    nearby = _make_unit(
        "Nearby Enemy",
        "en-nearby",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    far = _make_unit(
        "Far Enemy",
        "en-far",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(attacker)
    enemy_army.add_unit(destroyed)
    enemy_army.add_unit(nearby)
    enemy_army.add_unit(far)
    _deploy(attacker, destroyed, nearby, far)
    game.map.units = [attacker, destroyed, nearby, far]
    game.rebuild_entity_registry()

    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    destroyed.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    nearby.models[0].set_location(7.0, 0.0, 0.0, 0.0)
    far.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", return_value=5), patch(
        "warhammer40k_ai.rules.nurgles_gift.NurglesGiftManager.get_afflicted_plague_for_unit",
        return_value=None,
    ):
        game._on_unit_destroyed_explosive_blight(
            unit=destroyed,
            destroyed_by_unit=attacker,
            destroyed_by_model=attacker.models[0],
            last_model=destroyed.models[0],
        )

    assert bool(getattr(nearby, "special_rules", {}).get("post_shoot_afflicted_active")) is True
    assert bool(getattr(far, "special_rules", {}).get("post_shoot_afflicted_active", False)) is False


def test_extraction_of_fresh_disease_increases_oc_once_per_model():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    attacker = _make_unit(
        "Biologus Putrifier",
        "dg-putrifier",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
        keywords=["INFANTRY", "CHARACTER"],
        abilities=[{"name": "Extraction of Fresh Disease", "description": "Once per battle, gain +6 OC after melee kill.", "type": "Datasheet", "parameter": ""}],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "en-unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    dg_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy(attacker, enemy)
    game.map.units = [attacker, enemy]
    game.rebuild_entity_registry()

    wp = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))
    model = attacker.models[0]
    start_oc = int(getattr(model, "_objective_control", getattr(model, "objective_control", 0)) or 0)

    game._on_unit_destroyed_extraction_of_fresh_disease(
        unit=enemy,
        destroyed_by_unit=attacker,
        destroyed_by_weapon_profile=wp,
    )
    first_oc = int(getattr(model, "_objective_control", getattr(model, "objective_control", 0)) or 0)
    assert first_oc == start_oc + 6

    game._on_unit_destroyed_extraction_of_fresh_disease(
        unit=enemy,
        destroyed_by_unit=attacker,
        destroyed_by_weapon_profile=wp,
    )
    second_oc = int(getattr(model, "_objective_control", getattr(model, "objective_control", 0)) or 0)
    assert second_oc == first_oc
