from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


CATECHISM_OF_FIRE_TEXT = (
    "Each time this model's unit is selected to shoot, you can select one enemy unit within 12\" of and visible "
    "to this model. Until the end of the phase, ranged weapons equipped by models in this model's unit have the "
    "[DEVASTATING WOUNDS] ability when targeting that enemy unit."
)
EXHORTATION_OF_RAGE_TEXT = (
    "Each time this model's unit is selected to fight, you can select one enemy unit within Engagement Range of "
    "this model's unit and roll one D6: on a 4-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy "
    "unit suffers 3 mortal wounds."
)
TRANSFIXING_GAZE_TEXT = (
    "While an enemy unit is within 6\" of this model, each time that unit is selected to Fall Back, it must take "
    "a Leadership test. If that test is failed, that unit must Remain Stationary this phase instead."
)
MASTER_OF_PRESCIENCE_TEXT = (
    "While this model is leading a unit, each time an attack targets that unit, subtract 1 from the Hit roll. In "
    "addition, once per battle round, you can target that unit with one of the following Stratagems for 0CP: "
    "Counter-offensive; Fire Overwatch; Go to Ground; Heroic Intervention"
)
DEATH_MASK_OF_SANGUINIUS_TEXT = (
    "At the start of the Fight phase, each enemy unit within 6\" of this model must take a Battle-shock test, "
    "subtracting 1 from that test when they do."
)
WARDEN_OF_THE_IMPERIUM_NIHILUS_TEXT = (
    "While this model is leading a unit, add 1 to Advance and Charge rolls made for that unit and each time a "
    "model in that unit makes an attack, add 1 to the Hit roll."
)


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


def _build_game(*, sm_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Test")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=sm_control, army=sm_army)
    enemy_player = Player("Enemy", control=enemy_control, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


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


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key):
            return request
    return None


def _option_for_target(request, target: Unit):
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


def test_chaplain_on_bike_catechism_of_fire_queues_and_applies_to_only_the_selected_target():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    chaplain = _make_unit(
        "Chaplain On Bike",
        abilities=[_ability("Catechism of Fire", CATECHISM_OF_FIRE_TEXT)],
        keywords=["CHARACTER", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    enemy_army.add_unit(enemy_far)
    _set_model_location(chaplain, 0.0, 0.0)
    _set_model_location(enemy_a, 6.0, 0.0)
    _set_model_location(enemy_b, 8.0, 0.0)
    _set_model_location(enemy_far, 20.0, 0.0)
    _register_units(game, chaplain, enemy_a, enemy_b, enemy_far)

    game._on_shooting_targets_selected_selected_to_shoot_target_attack_keywords(
        attacking_unit=chaplain,
        target_units=[enemy_a, enemy_b, enemy_far],
    )
    request = _find_request(game, "selected_to_shoot_target_attack_keywords")
    assert request is not None
    assert str(getattr(request, "player_id", "") or "") == str(sm_player.id)
    assert len(list(getattr(request, "options", []) or [])) == 3
    assert _option_for_target(request, enemy_a) is not None
    assert _option_for_target(request, enemy_b) is not None
    assert _option_for_target(request, enemy_far) is None

    chosen = _option_for_target(request, enemy_a)
    assert chosen is not None
    result = resolve_decision_command(game, request, chosen.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    chosen_bonus = chaplain.get_attack_keyword_bonuses(
        target=enemy_a,
        attack_type="ranged",
        model=chaplain.models[0],
    )
    other_bonus = chaplain.get_attack_keyword_bonuses(
        target=enemy_b,
        attack_type="ranged",
        model=chaplain.models[0],
    )

    assert bool(chosen_bonus.get("devastating_wounds", False)) is True
    assert bool(other_bonus.get("devastating_wounds", False)) is False


def test_chaplain_on_bike_catechism_of_fire_skip_keeps_targets_unmodified():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    chaplain = _make_unit(
        "Chaplain On Bike",
        abilities=[_ability("Catechism of Fire", CATECHISM_OF_FIRE_TEXT)],
        keywords=["CHARACTER", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy)
    _set_model_location(chaplain, 0.0, 0.0)
    _set_model_location(enemy, 6.0, 0.0)
    _register_units(game, chaplain, enemy)

    game._on_shooting_targets_selected_selected_to_shoot_target_attack_keywords(
        attacking_unit=chaplain,
        target_units=[enemy],
    )
    request = _find_request(game, "selected_to_shoot_target_attack_keywords")
    assert request is not None

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    bonus = chaplain.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=chaplain.models[0],
    )
    assert bool(bonus.get("devastating_wounds", False)) is False


@pytest.mark.parametrize(
    ("rolls", "expected_models", "expected_wounds"),
    [
        ([4, 2], 1, 1),
        ([6], 0, 0),
    ],
)
def test_chaplain_with_jump_pack_exhortation_of_rage_queues_and_resolves_mortal_wounds(
    rolls,
    expected_models,
    expected_wounds,
):
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    chaplain = _make_unit(
        "Chaplain With Jump Pack",
        abilities=[_ability("Exhortation of Rage", EXHORTATION_OF_RAGE_TEXT)],
        keywords=["CHARACTER", "JUMP PACK", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=5,
    )
    target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=3,
    )

    sm_army.add_unit(chaplain)
    enemy_army.add_unit(target)
    _set_model_location(chaplain, 0.0, 0.0)
    _set_model_location(target, 0.5, 0.0)
    _register_units(game, chaplain, target)

    game._on_fight_unit_selected_hammer_aflame(unit=chaplain)
    request = _find_request(game, "exhortation_of_rage")
    assert request is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=list(rolls)):
        chosen = _option_for_target(request, target)
        result = resolve_decision_command(game, request, chosen.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert len(list(target.models or [])) == int(expected_models)
    if expected_models:
        assert int(target.models[0].wounds or 0) == int(expected_wounds)


def test_chief_librarian_mephiston_transfixing_gaze_blocks_fall_back_on_failed_leadership(monkeypatch):
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1

    mephiston = _make_unit(
        "Chief Librarian Mephiston",
        abilities=[_ability("Transfixing Gaze (Aura, Psychic)", TRANSFIXING_GAZE_TEXT)],
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
        toughness=5,
    )
    target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=3,
    )

    sm_army.add_unit(mephiston)
    enemy_army.add_unit(target)
    _set_model_location(mephiston, 0.0, 0.0)
    _set_model_location(target, 3.0, 0.0)
    _register_units(game, mephiston, target)

    monkeypatch.setattr(Unit, "pass_leadership_check", lambda self: False)

    ok = target.fall_back((10.0, 0.0, 0.0), [], game.map)
    assert ok is False
    assert bool(target.round_state.remained_stationary_this_round) is True


def test_chief_librarian_tigurius_master_of_prescience_grants_once_per_battle_round_zero_cp_core_stratagems():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    tigurius = _make_unit(
        "Chief Librarian Tigurius",
        abilities=[_ability("Master of Prescience (Psychic)", MASTER_OF_PRESCIENCE_TEXT)],
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=5,
    )
    bodyguard = _make_unit(
        "Sternguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
        wounds=2,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(tigurius)
    sm_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, tigurius)
    bodyguard._refresh_bearer_unit_common_modifiers()
    _register_units(game, bodyguard, tigurius, enemy)

    rule = bodyguard.get_master_of_prescience_stratagem_discount_rule()
    assert rule is not None
    assert str(rule.get("source", "") or "") == "Master of Prescience (Psychic)"
    assert set(rule.get("stratagems", ()) or ()) >= {
        "FIRE OVERWATCH",
        "GO TO GROUND",
        "COUNTER-OFFENSIVE",
        "HEROIC INTERVENTION",
    }
    assert bodyguard.can_use_master_of_prescience_stratagem_discount(game, stratagem_name="GO TO GROUND") is True

    sm_player.command_points = 0
    fire_overwatch = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
    go_to_ground = SimpleNamespace(name="Go to Ground", cp_cost=1)
    heroic_intervention = SimpleNamespace(name="Heroic Intervention", cp_cost=2)

    sm_player.set_next_optional_decision("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", True)
    first = sm_player.apply_stratagem_cp_cost(fire_overwatch, target_unit=bodyguard)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("master_of_prescience_use", False)) is True
    assert bodyguard.master_of_prescience_used_this_battle_round(game) is True

    sm_player.set_next_optional_decision("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", True)
    second = sm_player.apply_stratagem_cp_cost(go_to_ground, target_unit=bodyguard)
    assert int(second.get("cost", -1)) == 1
    assert bool(second.get("master_of_prescience_use", False)) is False

    game.turn = 2
    sm_player.set_next_optional_decision("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", True)
    third = sm_player.apply_stratagem_cp_cost(heroic_intervention, target_unit=bodyguard)
    assert int(third.get("cost", -1)) == 0
    assert bool(third.get("master_of_prescience_use", False)) is True
    assert str(bodyguard.special_rules.get("master_of_prescience_used_battle_round", "") or "") == "2"


def test_commander_dante_death_mask_and_warden_rules_apply_while_leading():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()

    dante = _make_unit(
        "Commander Dante",
        abilities=[
            _ability("Death Mask of Sanguinius", DEATH_MASK_OF_SANGUINIUS_TEXT),
            _ability("Warden of the Imperium Nihilus", WARDEN_OF_THE_IMPERIUM_NIHILUS_TEXT),
        ],
        keywords=["CHARACTER", "JUMP PACK", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
    )
    bodyguard = _make_unit(
        "Sanguinary Guard",
        keywords=["JUMP PACK", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=3,
        wounds=2,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(dante)
    sm_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, dante)
    bodyguard._refresh_bearer_unit_common_modifiers()
    _register_units(game, bodyguard, dante, enemy)

    specs = dante.model_start_fight_phase_aura_battleshock_specs(dante.models[0])
    assert len(specs) == 1
    assert int(specs[0].get("range", 0) or 0) == 6
    assert int(specs[0].get("penalty", 0) or 0) == 1

    assert int(bodyguard._apply_advance_roll_modifiers(4) or 0) == 5
    assert int(game._apply_charge_modifiers(bodyguard, 7) or 0) == 8

    melee_mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=enemy)
    assert int(melee_mods.get("hit", 0) or 0) == 1
