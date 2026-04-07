from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


PAROXYSM_TEXT = (
    "At the start of the Fight phase, you can select one enemy unit within 12\" of and visible to this model and roll one D6: "
    "on a 1, this PSYKER suffers D3 mortal wounds; on a 2+, until the end of the phase, subtract 1 from the Attacks "
    "characteristic of weapons equipped by models in that unit."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "9",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "3",
                "base_size": "60mm",
                "inv_sv": "4",
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
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=tyr_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, tyr_army, enemy_army, p1, p2


def _make_paroxysm_ability():
    return {
        "name": "Paroxysm (Psychic)",
        "description": PAROXYSM_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def _find_paroxysm_request(game: Game):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")) == "paroxysm"
    )


def _attack_result(profile, attacker, target_unit) -> AttackResult:
    return AttackResult(
        weapon_name=str(getattr(profile, "name", "") or "Weapon"),
        attacker_name=str(getattr(attacker, "name", "") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "")),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_paroxysm_spec_parsing():
    source = _make_unit(
        "Winged Hive Tyrant",
        abilities=[_make_paroxysm_ability()],
        keywords=["MONSTER", "CHARACTER", "PSYKER"],
        faction_keywords=["TYRANIDS"],
    )
    specs = source.model_start_fight_phase_paroxysm_specs(source.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 12
    assert int(spec.get("success_threshold", 0) or 0) == 2
    assert str(spec.get("self_mortal_wounds", "")).upper() == "D3"
    assert int(spec.get("attacks_penalty", 0) or 0) == 1


def test_paroxysm_queues_and_applies_attacks_penalty():
    source = _make_unit(
        "Winged Hive Tyrant",
        abilities=[_make_paroxysm_ability()],
        keywords=["MONSTER", "CHARACTER", "PSYKER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit("Enemy Elite", keywords=["INFANTRY"])

    game, tyr_army, enemy_army, p1, _p2 = _build_game()
    tyr_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    game.map.can_model_see_model = Mock(return_value=True)

    game._on_phase_start_paroxysm(player=p1, phase=game.phase)
    req = _find_paroxysm_request(game)
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str((req.options or [])[0].label) == "None"

    target_id = str(get_entity_id(enemy))
    target_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == target_id
    )

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, req, target_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = enemy.special_rules
    assert bool(sr.get("paroxysm_attacks_penalty_active")) is True
    assert int(sr.get("paroxysm_attacks_penalty", 0) or 0) == 1
    assert str(sr.get("paroxysm_attacks_penalty_expires_phase", "")).upper() == "FIGHT_PHASE"

    melee_profile = WargearProfile(
        "default",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Enemy Blades", is_ranged=lambda: False, is_melee=lambda: True),
    )
    count_info = melee_profile._resolve_attack_count(
        source,
        enemy.models[0],
        _attack_result(melee_profile, enemy.models[0], source),
        publish_roll_event=False,
    )
    assert int(count_info.num_attacks) == 1
    assert any("Paroxysm" in str(effect) for effect in list(count_info.special_modifiers or []))

    game._on_phase_end_cleanup(player=p1, phase=game.phase)
    assert "paroxysm_attacks_penalty_active" not in enemy.special_rules


def test_paroxysm_roll_one_applies_self_mortals():
    source = _make_unit(
        "Winged Hive Tyrant",
        abilities=[_make_paroxysm_ability()],
        keywords=["MONSTER", "CHARACTER", "PSYKER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit("Enemy Elite", keywords=["INFANTRY"])

    game, tyr_army, enemy_army, p1, _p2 = _build_game()
    tyr_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    game.map.can_model_see_model = Mock(return_value=True)
    source._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_paroxysm(player=p1, phase=game.phase)
    req = _find_paroxysm_request(game)
    target_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(enemy))
    )

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[1, 3]):
        result = resolve_decision_command(game, req, target_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    source._apply_mortal_wounds_to_unit.assert_called_once()
    call_args = source._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is source
    assert int(call_args.args[1]) == 3
    assert bool(enemy.special_rules.get("paroxysm_attacks_penalty_active", False)) is False


def test_paroxysm_invalid_out_of_range_choice_is_rejected():
    source = _make_unit(
        "Winged Hive Tyrant",
        abilities=[_make_paroxysm_ability()],
        keywords=["MONSTER", "CHARACTER", "PSYKER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"])

    game, tyr_army, enemy_army, p1, _p2 = _build_game()
    tyr_army.add_unit(source)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)
    game.map.units = [source, enemy_near, enemy_far]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_near.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy_far.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.map.can_model_see_model = Mock(return_value=True)

    game._on_phase_start_paroxysm(player=p1, phase=game.phase)
    req = _find_paroxysm_request(game)
    near_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(enemy_near))
    )
    near_option.payload["target_unit_id"] = str(get_entity_id(enemy_far))

    result = resolve_decision_command(game, req, near_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is False
