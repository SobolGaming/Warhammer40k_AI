from __future__ import annotations

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        save: str = "4",
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": str(save),
                "W": "4",
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
    army: Army,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
    save: str = "4",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            objective_control=objective_control,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    army.add_unit(unit)
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_ranged_profile(*, name: str, range_val: str = "24", keywords: str = ""):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
    )
    return weapon.profiles["default"]


def _build_game(*, army_detachment: str = "Spirit Conclave"):
    army = Army.with_detachment("Aeldari", detachment_type=army_detachment)
    army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    player = Player("Aeldari", control=PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    return game, army, enemy_army, player, enemy_player


def _attach_enhancement(unit: Unit, *, enh_id: str, name: str) -> Enhancement:
    enhancement = Enhancement(
        id=enh_id,
        name=name,
        faction_id="AE",
        detachment="Spirit Conclave",
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def test_spirit_conclave_enhancements_have_tool_descriptors():
    expected = {
        "000009907002": ("Light of Clarity", "target_wraith_construct_model_objective_control_bonus"),
        "000009907003": ("Stave of Kurnous", "target_wraith_construct_precision_on_critical_wound"),
        "000009907004": ("Rune of Mists", "target_wraith_construct_ranged_cover_unless_attacker_within_distance"),
        "000009907005": ("Higher Duty", "reactive_normal_move_when_enemy_move_ends_within_range"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_light_of_clarity_queues_selection_and_expires_on_next_owner_command_phase():
    game, army, _enemy_army, player, _enemy_player = _build_game()

    source = _make_unit(
        "Spiritseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(source, enh_id="000009907002", name="Light of Clarity")

    infantry_target = _make_unit(
        "Wraithguard",
        army,
        keywords=["INFANTRY", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
        objective_control=1,
    )
    monster_target = _make_unit(
        "Wraithlord",
        army,
        keywords=["MONSTER", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
        objective_control=2,
    )

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(infantry_target, x=6.0, y=0.0)
    _set_unit_location(monster_target, x=8.0, y=0.0)

    game.map.units = [source, infantry_target, monster_target]
    game.rebuild_entity_registry()

    game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
    requests = list(game.decision_queue.list() or [])
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "") or "") == "aeldari_light_of_clarity_target"

    infantry_id = str(get_entity_id(infantry_target) or "")
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == infantry_id
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))

    assert int(infantry_target.models[0].objective_control) == 2
    assert int(monster_target.models[0].objective_control) == 2
    target_sr = dict(getattr(infantry_target, "special_rules", {}) or {})
    assert bool(target_sr.get("enhancement_light_of_clarity_active"))

    source.models[0].wounds = 0
    game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)

    assert int(infantry_target.models[0].objective_control) == 1
    target_sr_after = dict(getattr(infantry_target, "special_rules", {}) or {})
    assert not bool(target_sr_after.get("enhancement_light_of_clarity_active"))


def test_light_of_clarity_decision_rejects_skip_choice():
    game, army, _enemy_army, player, _enemy_player = _build_game()

    source = _make_unit(
        "Spiritseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(source, enh_id="000009907002", name="Light of Clarity")
    target = _make_unit(
        "Wraithguard",
        army,
        keywords=["INFANTRY", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(target, x=6.0, y=0.0)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    source_model = source.models[0]
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Light of Clarity: select a target.",
        player_id=player.id,
        options=[DecisionOption.create("None", payload={"action": "skip"})],
        context={
            "ability": "aeldari_light_of_clarity_target",
            "ability_name": "Light of Clarity",
            "source_unit_id": str(get_entity_id(source) or ""),
            "unit_id": str(get_entity_id(source) or ""),
            "model_id": str(get_entity_id(source_model) or ""),
            "range": 12,
            "allow_skip": False,
            "infantry_bonus": 1,
            "monster_bonus": 3,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=str(request.options[0].option_id),
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is False
    assert any("cannot be skipped" in str(err).lower() for err in list(apply_result.errors or []))


def test_stave_of_kurnous_grants_precision_on_critical_wounds():
    game, army, enemy_army, player, _enemy_player = _build_game()

    source = _make_unit(
        "Spiritseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(source, enh_id="000009907003", name="Stave of Kurnous")
    target = _make_unit(
        "Wraithguard",
        army,
        keywords=["INFANTRY", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        enemy_army,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    applied = game._apply_aeldari_stave_of_kurnous_effect(
        source_unit=source,
        target_unit=target,
        player=player,
        ability_name="Stave of Kurnous",
    )
    assert applied is True

    bonuses = target.get_attack_keyword_bonuses_on_critical_wound(
        target=enemy,
        attack_type="ranged",
        model=target.models[0],
        game_map=game.map,
    )
    assert bool(bonuses.get("precision")) is True
    assert any("stave of kurnous" in str(src).lower() for src in list(bonuses.get("sources", []) or []))


def test_rune_of_mists_grants_cover_only_when_attacker_is_beyond_threshold():
    game, army, _enemy_army, player, _enemy_player = _build_game()

    source = _make_unit(
        "Spiritseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(source, enh_id="000009907004", name="Rune of Mists")
    target = _make_unit(
        "Wraithguard",
        army,
        keywords=["INFANTRY", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
        objective_control=1,
        save="4",
    )

    applied = game._apply_aeldari_rune_of_mists_effect(
        source_unit=source,
        target_unit=target,
        player=player,
        ability_name="Rune of Mists",
        min_attacker_distance_for_cover=18,
    )
    assert applied is True

    profile = _make_ranged_profile(name="Boltgun")

    far_attack = {"mortal_wound": False, "distance_to_target": 24.0}
    far_save = profile._save_with_tracking(
        target.models[0],
        far_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(far_attack.get("benefit_of_cover", False)) is True
    assert "rune of mists" in str(far_attack.get("benefit_of_cover_source", "")).lower()
    assert bool(far_save.get("saved", False)) is True

    near_attack = {"mortal_wound": False, "distance_to_target": 12.0}
    near_save = profile._save_with_tracking(
        target.models[0],
        near_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(near_attack.get("benefit_of_cover", False))
    assert bool(near_save.get("saved", False)) is False


def test_higher_duty_reactive_move_queues_fixed_six_inch_move():
    moving_army = Army.with_detachment("Enemy", detachment_type="Other")
    moving_army.faction_id = "SM"
    reacting_army = Army.with_detachment("Aeldari", detachment_type="Spirit Conclave")
    reacting_army.faction_id = "AE"

    moving_player = Player("Enemy", control=PlayerControl.REMOTE, army=moving_army)
    reacting_player = Player("Aeldari", control=PlayerControl.REMOTE, army=reacting_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[moving_player, reacting_player])
    game.current_player_index = 0

    moving_unit = _make_unit(
        "Enemy Movers",
        moving_army,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    reacting_unit = _make_unit(
        "Spiritseer",
        reacting_army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(reacting_unit, enh_id="000009907005", name="Higher Duty")

    _set_unit_location(moving_unit, x=0.0, y=0.0)
    _set_unit_location(reacting_unit, x=8.0, y=0.0)
    game.map.units = [moving_unit, reacting_unit]
    game.rebuild_entity_registry()

    game.event_system.publish("unit_move_ended", unit=moving_unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    confirm_request = pending[0]
    yes_option = next(opt for opt in list(confirm_request.options or []) if bool((opt.payload or {}).get("choice", False)))
    resolve_decision_command(game, confirm_request, yes_option.option_id, player_id=reacting_player.id)

    follow_up = list(game.decision_queue.list() or [])
    assert len(follow_up) == 1
    move_request = follow_up[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    move_ctx = dict(move_request.context or {})
    assert str(move_ctx.get("movement_type", "") or "") == "loping_speed"
    assert int(move_ctx.get("max_distance", 0) or 0) == 6
