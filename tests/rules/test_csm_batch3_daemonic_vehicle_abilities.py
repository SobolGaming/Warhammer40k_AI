from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
    DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES,
    DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.roll_handlers import handle_advance_roll, handle_charge_roll
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.modifier_choice import (
    CHOICE_IGNORE_ALL,
    CHOICE_IGNORE_NEGATIVE,
    CHOICE_IGNORE_POSITIVE,
    CHOICE_KEEP_ALL,
)
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "9",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability in list(abilities or []):
            if isinstance(ability, Ability):
                self.datasheets_abilities.append(
                    {
                        "name": ability.name,
                        "description": ability.description,
                        "type": ability.type,
                        "parameter": ability.parameter,
                    }
                )
            else:
                self.datasheets_abilities.append(ability)
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
):
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", detachment_type="Other")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", PlayerControl.LOCAL, army=csm_army)
    p2 = Player("P2", PlayerControl.LOCAL, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, csm_army, enemy_army, p1, p2


def _resolve_yes(game: Game, player: Player):
    req = game.decision_queue.peek()
    assert req is not None
    option_id = None
    for opt in list(req.options or []):
        if bool((opt.payload or {}).get("choice", False)):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)


def test_spirit_thief_queues_and_applies_wound_reroll_mark():
    ability = Ability(
        "Spirit Thief",
        "CSM",
        (
            "At the start of your Shooting phase, select one visible enemy VEHICLE unit. "
            "Until the end of the phase, each time a friendly HERETIC ASTARTES model makes an attack that targets that unit, "
            "re-roll a Wound roll of 1."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Lord Discordant", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game._on_phase_start_spirit_thief(player=p1, phase=game.phase)
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert (req.context or {}).get("ability") == "spirit_thief"

    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == str(target_id):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=p1.id)

    assert bool(enemy.special_rules.get("spirit_thief_active"))
    mods = source.get_unit_wound_reroll_modifiers("ranged", target=enemy)
    assert bool(mods.get("reroll_wound_ones"))
    assert 1 in tuple(mods.get("reroll_wound_values") or ())


def test_corrupt_machine_spirits_queues_and_deals_mortal_wounds():
    ability = Ability(
        "Corrupt Machine Spirits",
        "CSM",
        (
            "At the start of your Shooting phase, select one visible enemy VEHICLE unit within 12\" of this model and roll one D6: "
            "on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; "
            "on a 6, that enemy unit suffers D3+3 mortal wounds."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Lord Discordant", abilities=[ability])
    enemy = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    source._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_corrupt_machine_spirits(player=p1, phase=game.phase)
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert (req.context or {}).get("ability") == "corrupt_machine_spirits"

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        resolve_decision_command(game, req, req.options[0].option_id, player_id=p1.id)

    source._apply_mortal_wounds_to_unit.assert_called()
    call_args = source._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is enemy
    assert int(call_args.args[1]) == 3


def test_daemonic_ordnance_confirmation_sets_phase_effect():
    ability = Ability(
        "Daemonic Ordnance",
        "CSM",
        (
            "Each time this model is selected to shoot, it can use this ability. If it does, until the end of the phase, "
            "its ranged weapons have the [DEVASTATING WOUNDS] and [HAZARDOUS] abilities."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Forgefiend", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_daemonic_ordnance(attacking_unit=source, target_units=[enemy])
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CONFIRM_YES_NO
    assert (req.context or {}).get("ability") == "daemonic_ordnance"

    _resolve_yes(game, p1)
    sr = source.special_rules
    assert bool(sr.get("daemonic_ordnance_active"))
    assert str(sr.get("daemonic_ordnance_expires_phase", "")).upper() == "SHOOTING_PHASE"


def test_warp_rift_firepower_confirmation_marks_once_per_battle():
    ability = Ability(
        "Warp Rift Firepower",
        "CSM",
        (
            "Once per battle, during the shooting phase, this unit can use this ability. If it does, until the end of the phase, "
            "ranged weapons equipped by models in this unit have the [INDIRECT FIRE] ability."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit("Obliterators", abilities=[ability], keywords=["HERETIC ASTARTES"])
    enemy = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_warp_rift_firepower(attacking_unit=source, target_units=[enemy])
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CONFIRM_YES_NO
    assert (req.context or {}).get("ability") == "warp_rift_firepower"

    _resolve_yes(game, p1)
    assert source.has_used_unit_once_per_battle("warp_rift_firepower")
    assert bool(source.special_rules.get("warp_rift_firepower_active"))

    game._on_shooting_targets_selected_warp_rift_firepower(attacking_unit=source, target_units=[enemy])
    assert list(game.decision_queue.list() or []) == []


def test_daemonic_ordnance_and_warp_rift_effects_are_consumed_by_attack_resolution():
    source = _make_unit("Forgefiend", keywords=["HERETIC ASTARTES"])
    target = _make_unit("Target")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.special_rules["daemonic_ordnance_active"] = True
    source.special_rules["daemonic_ordnance_expires_phase"] = "SHOOTING_PHASE"
    source.special_rules["daemonic_ordnance_owner"] = p1.id
    source.special_rules["daemonic_ordnance_turn"] = int(getattr(game, "turn", 0) or 0)
    source.special_rules["warp_rift_firepower_active"] = True
    source.special_rules["warp_rift_firepower_expires_phase"] = "SHOOTING_PHASE"
    source.special_rules["warp_rift_firepower_owner"] = p1.id
    source.special_rules["warp_rift_firepower_turn"] = int(getattr(game, "turn", 0) or 0)

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Ectoplasma Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 2]):
        result = profile.attack(target, source.models[0], game_map=game.map)

    assert result is not None
    assert int(result.hazardous_roll or 0) == 2
    assert any("Daemonic Ordnance" in str(v) for v in list(result.attacks_special_modifiers or []))
    assert any("Warp Rift Firepower" in str(v) for v in list(result.attacks_special_modifiers or []))
    assert any(
        "Devastating Wounds" in str(effect)
        for wound in list(result.wound_results or [])
        for effect in list((wound or {}).get("special_effects", []) or [])
    )


def test_bringers_of_change_applies_wound_rerolls_with_objective_upgrade():
    ability = Ability(
        "Bringers of Change",
        "CSM",
        "Ranged attacks re-roll Wound rolls of 1; full re-rolls vs targets within objective range you do not control.",
        "Datasheet",
        "",
    )
    source = _make_unit("Lord of Change", abilities=[ability], keywords=["HERETIC ASTARTES"])
    target = _make_unit("Enemy Unit")

    game, army, enemy_army, p1, p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    objective = SimpleNamespace(
        x=10.0,
        y=0.0,
        z=0.0,
        control_radius=3.0,
        controlling_player=p2,
    )
    game.map.objectives = [objective]
    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    mods = source.get_unit_wound_reroll_modifiers("ranged", target=target)
    assert 1 in tuple(mods.get("reroll_wound_values") or ())
    assert bool(mods.get("reroll_wound_full"))

    objective.controlling_player = p1
    mods_controlled = source.get_unit_wound_reroll_modifiers("ranged", target=target)
    assert 1 in tuple(mods_controlled.get("reroll_wound_values") or ())
    assert not bool(mods_controlled.get("reroll_wound_full"))


def test_siege_crawler_modifier_choices_apply_to_move_advance_and_charge_modifiers():
    ability = Ability(
        "Siege Crawler",
        "CSM",
        "You can ignore any or all modifiers to this model's Move characteristic and to Advance and Charge rolls made for it.",
        "Datasheet",
        "",
    )
    source = _make_unit("Forgefiend", abilities=[ability], keywords=["VEHICLE"])
    target = _make_unit("Enemy Unit")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    assert source.has_siege_crawler()
    source.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 3, source="test:slow"))
    source.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, 1, source="test:fast"))
    model = source.models[0]

    source.round_state.move_modifier_choice = CHOICE_KEEP_ALL
    move_keep = source.get_effective_model_characteristic(model, "movement")
    assert int(move_keep) == 6

    source.round_state.move_modifier_choice = CHOICE_IGNORE_NEGATIVE
    move_ignore_negative = source.get_effective_model_characteristic(model, "movement")
    assert int(move_ignore_negative) == 9

    source.round_state.move_modifier_choice = CHOICE_IGNORE_POSITIVE
    move_ignore_positive = source.get_effective_model_characteristic(model, "movement")
    assert int(move_ignore_positive) == 5

    source.round_state.move_modifier_choice = CHOICE_IGNORE_ALL
    move_ignore_all = source.get_effective_model_characteristic(model, "movement")
    assert int(move_ignore_all) == 8

    source.special_rules["advance_roll_modifiers"] = [
        {"value": -2, "source": "test:slow"},
        {"value": 1, "source": "test:fast"},
    ]
    source.round_state.advance_modifier_choice = CHOICE_KEEP_ALL
    assert int(source._apply_advance_roll_modifiers(4)) == 3
    source.round_state.advance_modifier_choice = CHOICE_IGNORE_NEGATIVE
    assert int(source._apply_advance_roll_modifiers(4)) == 5
    source.round_state.advance_modifier_choice = CHOICE_IGNORE_ALL
    assert int(source._apply_advance_roll_modifiers(4)) == 4

    source.special_rules["charge_roll_modifiers"] = [
        {"value": -2, "source": "test:slow"},
        {"value": 1, "source": "test:fast"},
    ]
    source.round_state.charge_modifier_choice = CHOICE_KEEP_ALL
    keep_mods = game._collect_charge_modifiers(source, target_unit=target)
    assert sorted(keep_mods) == [(-2, "test:slow"), (1, "test:fast")]

    source.round_state.charge_modifier_choice = CHOICE_IGNORE_NEGATIVE
    ignore_negative_mods = game._collect_charge_modifiers(source, target_unit=target)
    assert ignore_negative_mods == [(1, "test:fast")]

    source.round_state.charge_modifier_choice = CHOICE_IGNORE_ALL
    ignore_all_mods = game._collect_charge_modifiers(source, target_unit=target)
    assert ignore_all_mods == []


def test_siege_crawler_queues_move_advance_and_charge_modifier_ignore_decisions():
    from warhammer40k_ai.engine.decision_handlers.movement import _maybe_request_move_modifier_choice

    ability = Ability(
        "Siege Crawler",
        "CSM",
        "You can ignore any or all modifiers to this model's Move characteristic and to Advance and Charge rolls made for it.",
        "Datasheet",
        "",
    )
    source = _make_unit("Forgefiend", abilities=[ability], keywords=["VEHICLE"])
    target = _make_unit("Enemy Unit")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:slow"))
    source.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, 1, source="test:fast"))
    _maybe_request_move_modifier_choice(game, source, action_type="move")
    move_requests = [
        req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CHOOSE_MOVE_MODIFIER_IGNORES
    ]
    assert len(move_requests) == 1
    move_ctx = dict(move_requests[0].context or {})
    assert str(move_ctx.get("ability_name", "")) == "Siege Crawler"
    game.decision_queue.pop(move_requests[0].decision_id)

    source.special_rules["advance_roll_modifiers"] = [
        {"value": -2, "source": "test:slow"},
        {"value": 1, "source": "test:fast"},
    ]
    advance_state = DiceRollState(
        roll_id=101,
        player_id=p1.id,
        spec={"unit_id": get_entity_id(source)},
        status="rolled",
        dice=[{"die_id": "101:0", "value": 4}],
        total=4,
    )
    result = handle_advance_roll(game, advance_state)
    assert result is None
    adv_requests = [
        req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES
    ]
    assert len(adv_requests) == 1
    adv_ctx = dict(adv_requests[0].context or {})
    assert str(adv_ctx.get("ability_name", "")) == "Siege Crawler"
    game.decision_queue.pop(adv_requests[0].decision_id)

    source.special_rules["charge_roll_modifiers"] = [
        {"value": -2, "source": "test:slow"},
        {"value": 1, "source": "test:fast"},
    ]
    game.phase = BattleRoundPhases.CHARGE_PHASE
    charge_state = DiceRollState(
        roll_id=102,
        player_id=p1.id,
        spec={
            "unit_id": get_entity_id(source),
            "charge_spec": {"dice_count": 2, "keep_highest": 2},
            "target_unit_ids": [get_entity_id(target)],
        },
        status="rolled",
        dice=[{"die_id": "102:0", "value": 4}, {"die_id": "102:1", "value": 2}],
        total=6,
    )
    handle_charge_roll(game, charge_state)
    charge_requests = [
        req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CHOOSE_CHARGE_MODIFIER_IGNORES
    ]
    assert len(charge_requests) == 1
    charge_ctx = dict(charge_requests[0].context or {})
    assert str(charge_ctx.get("ability_name", "")) == "Siege Crawler"


def test_reorder_reality_marks_attacker_and_applies_hazardous_and_hit_penalty():
    reorder = Ability(
        "Reorder Reality",
        "CSM",
        "Enemy units that target this unit in the Shooting phase suffer penalties and [HAZARDOUS].",
        "Datasheet",
        "",
    )
    source = _make_unit("Shooter")
    target = _make_unit("Warp Construct", abilities=[reorder])

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game._on_shooting_targets_selected_reorder_reality(attacking_unit=source, target_units=[target])
    assert bool(source.special_rules.get("reorder_reality_active"))
    assert str(get_entity_id(target)) in tuple(source.special_rules.get("reorder_reality_target_ids") or ())
    assert str(source.special_rules.get("reorder_reality_owner", "")) == str(p1.id)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Warp Blaster", is_ranged=lambda: True, is_melee=lambda: False),
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 1, 2]):
        result = profile.attack(target, source.models[0], game_map=game.map)

    assert result is not None
    assert int(result.hazardous_roll or 0) == 2
    assert any("Reorder Reality: [HAZARDOUS]" in str(v) for v in list(result.attacks_special_modifiers or []))
    first_hit = dict((result.hit_results or [])[0] or {})
    assert any("Reorder Reality" in str(v) for v in list(first_hit.get("modifiers", []) or []))


def test_siege_shield_allows_demolisher_blast_into_own_engagement_only():
    siege_shield = Ability(
        "Siege Shield",
        "CSM",
        "Demolisher Cannon can target in own engagement despite Blast restriction.",
        "Datasheet",
        "",
    )
    source = _make_unit("Vindicator", abilities=[siege_shield], keywords=["VEHICLE"])
    target = _make_unit("Enemy Unit")
    other_friendly = _make_unit("Friendly Squad")

    game, army, enemy_army, _p1, _p2 = _build_game()
    army.add_unit(source)
    army.add_unit(other_friendly)
    enemy_army.add_unit(target)
    game.map.units = [source, other_friendly, target]
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.4, 0.0, 0.0, 0.0)
    other_friendly.models[0].set_location(20.0, 20.0, 0.0, 0.0)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "Blast",
        },
        parent_wargear=SimpleNamespace(name="Demolisher Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    assert source._can_model_shoot_weapon_at_target(source.models[0], profile, target, game.map)

    other_friendly.models[0].set_location(0.5, 0.0, 0.0, 0.0)
    assert not source._can_model_shoot_weapon_at_target(source.models[0], profile, target, game.map)


def test_master_of_mechanisms_queues_optional_selection_and_applies_effect():
    ability = Ability(
        "Master of Mechanisms",
        "CSM",
        "In your Command phase, select one friendly VEHICLE unit within 3\"; it regains D3 wounds and gets +1 to hit.",
        "Datasheet",
        "",
    )
    source = _make_unit("Warpsmith", abilities=[ability], keywords=["INFANTRY"])
    vehicle = _make_unit("Predator", keywords=["VEHICLE"], wounds=10)

    game, army, _enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    army.add_unit(vehicle)
    game.map.units = [source, vehicle]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    before_wounds = int(vehicle.models[0].wounds)
    vehicle.models[0].wounds = before_wounds - 3

    game._on_phase_start_master_of_mechanisms(player=p1, phase=game.phase)
    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert (req.context or {}).get("ability") == "master_of_mechanisms"
    assert str((req.options or [])[0].label) == "None"

    vehicle_id = str(get_entity_id(vehicle))
    option_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == vehicle_id:
            option_id = opt.option_id
            break
    assert option_id is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        resolve_decision_command(game, req, option_id, player_id=p1.id)

    assert bool(vehicle.special_rules.get("master_of_mechanisms_hit_bonus_active"))
    assert int(vehicle.models[0].wounds) == before_wounds - 1


def test_herald_of_the_apocalypse_forces_battleshock_in_opponent_command_phase():
    ability = Ability(
        "Herald of the Apocalypse (Aura)",
        "CSM",
        "In your opponent's Command phase, enemy units below Starting Strength within 6\" must take Battle-shock tests.",
        "Datasheet",
        "",
    )
    source = _make_unit("Daemon Herald", abilities=[ability])
    enemy = _make_unit("Enemy Unit", wounds=6)

    game, csm_army, enemy_army, p1, _p2 = _build_game()
    enemy_army.add_unit(source)
    csm_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    enemy.models[0].wounds = int(enemy.models[0].wounds) - 1
    enemy.take_battle_shock_test = Mock()

    game._on_phase_start_herald_of_the_apocalypse(player=p1, phase=game.phase)
    enemy.take_battle_shock_test.assert_called_once_with(int(getattr(game, "turn", 0) or 0))


def test_plough_through_the_enemy_triggers_on_phase_end_event_bus():
    ability = Ability(
        "Plough Through the Enemy",
        "CSM",
        "At the end of the Fight phase, after this unit destroys an enemy, nearby enemies take Battle-shock tests.",
        "Datasheet",
        "",
    )
    source = _make_unit("Daemon Engine", abilities=[ability], keywords=["VEHICLE"])
    enemy = _make_unit("Enemy Unit")

    game, army, enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    enemy.take_battle_shock_test = Mock()
    game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {str(get_entity_id(source))}

    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    enemy.take_battle_shock_test.assert_called_once()


def test_soul_eater_triggers_on_phase_end_event_bus():
    ability = Ability(
        "Soul Eater",
        "CSM",
        "At the end of the Fight phase, after this unit destroys an enemy, it gains +1 Attacks.",
        "Datasheet",
        "",
    )
    source = _make_unit("Soul Grinder", abilities=[ability], keywords=["VEHICLE"])

    game, army, _enemy_army, p1, _p2 = _build_game()
    army.add_unit(source)
    game.map.units = [source]
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {str(get_entity_id(source))}
    game.event_system.publish("phase_end", player=p1, phase=game.phase)

    assert int(source.special_rules.get("soul_eater_attacks_bonus", 0) or 0) == 1
