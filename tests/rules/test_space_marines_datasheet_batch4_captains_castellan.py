from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        wounds=4,
        toughness=4,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class _DummyMeleeWargear:
    def is_melee(self):
        return True


class _DummyMeleeProfile:
    def __init__(self):
        self.parent_wargear = _DummyMeleeWargear()


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    wounds=4,
    toughness=4,
    ) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sm_control=PlayerControl.LOCAL, enemy_control=PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Test")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=sm_control, army=sm_army)
    enemy_player = Player("Enemy", control=enemy_control, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()


def test_captain_sicarius_lead_from_the_front_grants_scouts_while_leading():
    _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
    captain = _make_unit(
        "Captain Sicarius",
        abilities=[
            _ability(
                "Lead From the Front",
                'While this model is leading a unit, models in that unit have the Scouts 6" ability and ranged weapons equipped by models in that unit have the [ASSAULT] ability.',
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    sm_army.add_unit(captain)
    sm_army.add_unit(bodyguard)
    _attach_leader(bodyguard, captain)

    captain._apply_leading_bodyguard_scouts(bodyguard)

    has_scout, distance = bodyguard.has_scout()
    assert bool(has_scout)
    assert int(distance or 0) == 6


@pytest.mark.parametrize(
    ("ability_name", "ability_text"),
    [
        (
            "Lightning Assault",
            'Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9" of this model, if this model’s unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to 6".',
        ),
        (
            "Knight Champion of Macragge",
            'Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9" of this model’s unit, if this unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to 6".',
        ),
    ],
)
def test_space_marine_reactive_move_wording_queues_remote_decision(ability_name: str, ability_text: str):
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game(sm_control=PlayerControl.REMOTE)

    reacting_unit = _make_unit(
        ability_name,
        abilities=[_ability(ability_name, ability_text)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    moving_unit = _make_unit(
        "Enemy Movers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(reacting_unit)
    enemy_army.add_unit(moving_unit)
    reacting_unit.deployed = True
    moving_unit.deployed = True
    _set_model_location(moving_unit, 0.0, 0.0)
    _set_model_location(reacting_unit, 8.0, 0.0)
    game.map.units = [moving_unit, reacting_unit]

    game.event_system.publish("unit_move_ended", unit=moving_unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    assert request.player_id == sm_player.id
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "loping_speed"
    assert str(context.get("reactive_move_unit_id", "") or "") == str(get_entity_id(reacting_unit))


def test_captain_titus_honour_of_ultramar_rule_includes_survival_rider():
    titus = _make_unit(
        "Captain Titus",
        abilities=[
            _ability(
                "Honour of Ultramar",
                "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6: on a 2+, do not remove it from play. This model can fight after the attacking unit has finished making its attacks. If one or more enemy models are destroyed as a result of those attacks, this model regains D3 lost wounds and is not destroyed; otherwise, it is removed from play.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
    )

    rule = titus.get_melee_fight_on_death_after_attacks_rule(model=titus.models[0])

    assert rule is not None
    assert int(rule.get("threshold", 0) or 0) == 2
    assert bool(rule.get("survive_if_enemy_models_destroyed", False))
    assert str(rule.get("heal_expr", "") or "") == "D3"


def test_captain_titus_honour_of_ultramar_survives_and_heals_if_enemy_model_dies():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    titus = _make_unit(
        "Captain Titus",
        abilities=[
            _ability(
                "Honour of Ultramar",
                "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6: on a 2+, do not remove it from play. This model can fight after the attacking unit has finished making its attacks. If one or more enemy models are destroyed as a result of those attacks, this model regains D3 lost wounds and is not destroyed; otherwise, it is removed from play.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(titus)
    enemy_army.add_unit(enemy)
    titus.deployed = True
    enemy.deployed = True
    game.map.units = [titus, enemy]

    titus.round_state.fought_this_phase = False
    titus._last_destroyed_by_weapon_profile = _DummyMeleeProfile()
    titus_model = titus.models[0]
    titus_model._wounds = 0

    destroyed_events = []
    game.event_system.subscribe("unit_destroyed", lambda **kwargs: destroyed_events.append(kwargs))

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
        titus._handle_model_destroyed(titus_model, game.map)
        titus.remove_model(titus_model, False, game_map=game.map)

    assert titus.models == []

    def _kill_enemy(*, model, game_map):
        if enemy.models:
            enemy.models.pop()
        return True

    with patch.object(titus, "_try_fight_on_death", side_effect=_kill_enemy):
        with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
            titus.end_attack_resolution(game_map=game.map)

    assert titus_model in titus.models
    assert int(getattr(titus_model, "wounds", 0) or 0) == 2
    assert not any(event.get("unit") is titus for event in destroyed_events)


def test_captain_titus_honour_of_ultramar_is_destroyed_if_no_enemy_model_dies():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    titus = _make_unit(
        "Captain Titus",
        abilities=[
            _ability(
                "Honour of Ultramar",
                "If this model is destroyed by a melee attack, if it has not fought this phase, roll one D6: on a 2+, do not remove it from play. This model can fight after the attacking unit has finished making its attacks. If one or more enemy models are destroyed as a result of those attacks, this model regains D3 lost wounds and is not destroyed; otherwise, it is removed from play.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(titus)
    enemy_army.add_unit(enemy)
    titus.deployed = True
    enemy.deployed = True
    game.map.units = [titus, enemy]

    titus.round_state.fought_this_phase = False
    titus._last_destroyed_by_weapon_profile = _DummyMeleeProfile()
    titus_model = titus.models[0]
    titus_model._wounds = 0

    destroyed_events = []
    game.event_system.subscribe("unit_destroyed", lambda **kwargs: destroyed_events.append(kwargs))

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
        titus._handle_model_destroyed(titus_model, game.map)
        titus.remove_model(titus_model, False, game_map=game.map)

    with patch.object(titus, "_try_fight_on_death", return_value=False):
        titus.end_attack_resolution(game_map=game.map)

    assert titus.models == []
    assert any(event.get("unit") is titus for event in destroyed_events)


def test_captain_with_jump_pack_angels_wrath_grants_attached_unit_melee_strength_on_charge_end():
    _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
    captain = _make_unit(
        "Captain With Jump Pack",
        abilities=[
            _ability(
                "Angel’s Wrath",
                "While this model is leading a unit, each time that unit ends a Charge move, until the end of the turn, add 1 to the Strength characteristic of melee weapons equipped by models in that unit.",
            )
        ],
        keywords=["CHARACTER", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Assault Intercessors With Jump Packs",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    sm_army.add_unit(captain)
    sm_army.add_unit(bodyguard)
    _attach_leader(bodyguard, captain)

    applied = bodyguard._apply_charge_end_unit_melee_strength_bonuses()

    assert bool(applied)
    bodyguard_bonus, bodyguard_reasons = bodyguard.models[0].get_temporary_melee_strength_bonus()
    captain_bonus, captain_reasons = captain.models[0].get_temporary_melee_strength_bonus()
    assert int(bodyguard_bonus or 0) == 1
    assert int(captain_bonus or 0) == 1
    assert any("Angel" in str(reason) for reason in list(bodyguard_reasons or []))
    assert any("Angel" in str(reason) for reason in list(captain_reasons or []))


def test_castellan_prioritised_eradication_gains_cp_on_4_plus():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    castellan = _make_unit(
        "Castellan",
        abilities=[
            _ability(
                "Prioritised Eradication",
                "Each time a model in this model’s unit makes a melee attack that destroys one or more enemy units, roll one D6: on a 4+, you gain 1CP.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(castellan)
    enemy_army.add_unit(enemy)
    cp_events = []
    game.event_system.subscribe("command_points_gained", lambda **kwargs: cp_events.append(kwargs))

    with patch("warhammer40k_ai.engine.game.get_roll", return_value=4):
        game._on_unit_destroyed_rules(
            unit=enemy,
            destroyed_by_unit=castellan,
            destroyed_by_model=castellan.models[0],
            destroyed_by_weapon_profile=_DummyMeleeProfile(),
        )

    assert int(sm_player.command_points or 0) == 1
    assert len(cp_events) == 1
    assert str(cp_events[0].get("reason", "") or "") == "Prioritised Eradication"


def test_castellan_vehement_aggression_grants_full_hit_rerolls_on_pass():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    castellan = _make_unit(
        "Castellan",
        abilities=[
            _ability(
                "Vehement Aggression",
                "While this model is leading a unit, each time that unit is selected to fight, take a Leadership test for that unit: if passed, until the end of the phase, each time a model in that unit makes an attack, you can re-roll the Hit roll; if failed, until the end of the phase, each time a model in that unit makes an attack, re-roll a Hit roll of 1.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Sword Brethren",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    sm_army.add_unit(castellan)
    sm_army.add_unit(bodyguard)
    _attach_leader(bodyguard, castellan)
    bodyguard.pass_leadership_check = lambda **_kwargs: True

    game._on_fight_unit_selected_vehement_aggression(unit=bodyguard, selecting_player=sm_player)
    mods = bodyguard.get_unit_hit_reroll_modifiers("melee")

    assert bool(mods.get("reroll_hit_full", False))
    assert any("Vehement Aggression" in str(reason) for reason in list(mods.get("reroll_hit_full_reasons", ()) or ()))


def test_castellan_vehement_aggression_grants_hit_reroll_ones_on_fail_and_cleans_up():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    castellan = _make_unit(
        "Castellan",
        abilities=[
            _ability(
                "Vehement Aggression",
                "While this model is leading a unit, each time that unit is selected to fight, take a Leadership test for that unit: if passed, until the end of the phase, each time a model in that unit makes an attack, you can re-roll the Hit roll; if failed, until the end of the phase, each time a model in that unit makes an attack, re-roll a Hit roll of 1.",
            )
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Sword Brethren",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    sm_army.add_unit(castellan)
    sm_army.add_unit(bodyguard)
    _attach_leader(bodyguard, castellan)
    bodyguard.pass_leadership_check = lambda **_kwargs: False

    game._on_fight_unit_selected_vehement_aggression(unit=bodyguard, selecting_player=sm_player)
    mods = bodyguard.get_unit_hit_reroll_modifiers("melee")

    assert 1 in tuple(mods.get("reroll_hit_values", ()) or ())
    assert any("Vehement Aggression" in str(reason) for reason in list(mods.get("reroll_hit_reasons", ()) or ()))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert "vehement_aggression_active" not in bodyguard.special_rules
    assert "vehement_aggression_active" not in castellan.special_rules
