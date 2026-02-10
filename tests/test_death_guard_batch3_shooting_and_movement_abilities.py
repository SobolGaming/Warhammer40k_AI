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
    dg_army = Army("Death Guard", "Plague Company")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
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


def test_spore_laced_shock_waves_marks_and_applies_mortals():
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
