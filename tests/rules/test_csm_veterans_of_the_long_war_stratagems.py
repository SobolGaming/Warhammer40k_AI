from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        move: int = 6,
        toughness: int = 4,
        base_size: str = "32mm",
    ):
        self.id = str(name).lower().replace(" ", "_")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
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


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    move: int = 6,
    toughness: int = 4,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
            toughness=toughness,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.possible_abilities = ["Dark Pacts"]
    return unit


def _make_wargear(
    name: str,
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    veterans_army = Army.with_detachment("Chaos Space Marines", "Veterans of the Long War")
    veterans_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    veterans_player = Player("Veterans", control=PlayerControl.LOCAL, army=veterans_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(veterans_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    veterans_player.command_points = 10
    enemy_player.command_points = 10

    veterans_army.configure_rule_managers(force=True)
    veterans_player.stratagems.refresh_available()
    _inject_veterans_stratagems(veterans_player)
    veterans_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, veterans_player, enemy_player, veterans_army, enemy_army


def _inject_veterans_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008961002",
            "Endless Ire",
            2,
            "Either player's turn",
            "Any phase",
            "Veterans of the Long War - Epic Deed Stratagem",
        ),
        (
            "000008961003",
            "Contemptuous Disregard",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Veterans of the Long War - Battle Tactic Stratagem",
        ),
        (
            "000008961004",
            "Bringers of Despair",
            2,
            "Either player's turn",
            "Fight phase",
            "Veterans of the Long War - Epic Deed Stratagem",
        ),
        (
            "000008961005",
            "Black Crusade",
            1,
            "Your turn",
            "Movement phase",
            "Veterans of the Long War - Strategic Ploy Stratagem",
        ),
        (
            "000008961006",
            "Let the Galaxy Burn",
            1,
            "Your turn",
            "Shooting phase",
            "Veterans of the Long War - Battle Tactic Stratagem",
        ),
        (
            "000008961007",
            "Millennia of Experience",
            1,
            "Opponent's turn",
            "Movement phase",
            "Veterans of the Long War - Strategic Ploy Stratagem",
        ),
    )
    for stratagem_id, name, cp_cost, turn, phase, stratagem_type in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=stratagem_id,
                name=name,
                type=stratagem_type,
                description="",
                cp_cost=int(cp_cost),
                turn=turn,
                phase=phase,
                detachment="Veterans of the Long War",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    expected = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == expected:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability is None:
            return request
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return request
    return None


def _find_target_option(request, *, target_unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return option
    return None


def test_veterans_of_the_long_war_stratagem_descriptors_registered():
    expected = {
        "000008961002": ("Endless Ire", "replace_focus_of_hatred_target"),
        "000008961003": ("Contemptuous Disregard", "defensive_ap_worsen"),
        "000008961004": ("Bringers of Despair", "grant_fights_first"),
        "000008961005": ("Black Crusade", "shoot_after_advance_or_fall_back_and_conditional_bolt_devastating_wounds"),
        "000008961006": ("Let the Galaxy Burn", "ranged_ignores_cover_and_torrent_attacks_set_6"),
        "000008961007": ("Millennia of Experience", "reactive_normal_move_up_to_6"),
    }
    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == name
        assert by_name.name == name
        assert by_id.effect == effect


def test_black_crusade_grants_shoot_after_advance_and_conditional_bolt_devastating_wounds():
    game, veterans_player, _enemy_player, veterans_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=10)
    boltgun = _make_wargear("Boltgun", melee=False, damage="2")
    legionaries.models[0].wargear = [boltgun]
    veterans_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    profile = boltgun.profiles["default"]
    mgr = veterans_army.chaos_space_marines_detachments

    _set_phase(game, veterans_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(veterans_player.stratagems, "BLACK CRUSADE") is not None
    assert veterans_player.stratagems.use("BLACK CRUSADE", unit=legionaries, phase_name="Movement phase", dequeue=True)
    assert legionaries.can_shoot_after_advance(profile) is True
    assert legionaries.can_shoot_after_fall_back(profile) is True

    _set_phase(game, veterans_player, "SHOOTING_PHASE", 0)
    attack_instance = {}
    wound_result = profile._wound_target_with_tracking(
        enemy,
        legionaries.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound", False)) is True
    assert bool(attack_instance.get("bonus_devastating_wounds", False)) is True
    damage_result = profile._damage_target_with_tracking(enemy.models[0], legionaries.models[0], attack_instance)
    assert int(damage_result.get("damage_applied", 0) or 0) == 2

    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    damage_key = getattr(mgr, "_VETERANS_BLACK_CRUSADE_DAMAGE_KEY")
    assert int(sr.get(damage_key, 0) or 0) == 2

    mgr.veterans_record_black_crusade_damage(legionaries.models[0], 4, game=game)
    capped_attack = {}
    capped_wound = profile._wound_target_with_tracking(
        enemy,
        legionaries.models[0],
        capped_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(capped_wound.get("wound", False)) is True
    assert bool(capped_attack.get("bonus_devastating_wounds", False)) is False

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_end", player=veterans_player, phase=game.phase)
    assert legionaries.can_shoot_after_advance(profile) is False
    assert legionaries.can_shoot_after_fall_back(profile) is False


def test_let_the_galaxy_burn_sets_torrent_attacks_to_six_and_grants_ignores_cover_until_phase_end():
    game, veterans_player, _enemy_player, veterans_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    flamer = _make_wargear("Flamer", melee=False, attacks="D6", description="Torrent")
    boltgun = _make_wargear("Boltgun", melee=False)
    legionaries.models[0].wargear = [flamer, boltgun]
    veterans_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    flamer_profile = flamer.profiles["default"]
    boltgun_profile = boltgun.profiles["default"]

    _set_phase(game, veterans_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(veterans_player.stratagems, "LET THE GALAXY BURN") is not None
    assert veterans_player.stratagems.use(
        "LET THE GALAXY BURN",
        unit=legionaries,
        phase_name="Shooting phase",
        dequeue=True,
    )

    preview = flamer_profile.preview_attack_count(enemy, legionaries.models[0], publish_roll_event=False)
    assert int(preview.num_attacks) == 6

    attack_instance = {"damage_characteristic": 1}
    boltgun_profile._hit_target_with_tracking(
        enemy,
        legionaries.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("ignores_cover", False)) is True

    game.event_system.publish("phase_end", player=veterans_player, phase=game.phase)
    post_attack = {"damage_characteristic": 1}
    boltgun_profile._hit_target_with_tracking(
        enemy,
        legionaries.models[0],
        post_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(post_attack.get("ignores_cover", False)) is False


def test_bringers_of_despair_grants_fight_first_until_fight_phase_end():
    game, veterans_player, _enemy_player, veterans_army, enemy_army = _build_game()
    chosen = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    focus_target = _make_unit("Enemy Focus", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    veterans_army.add_unit(chosen)
    enemy_army.add_unit(focus_target)
    _deploy_unit(game, chosen, 10.0, 10.0)
    _deploy_unit(game, focus_target, 11.0, 10.0)
    game.rebuild_entity_registry()

    mgr = veterans_army.chaos_space_marines_detachments
    mgr.veterans_focus_of_hatred_target_unit_id = str(get_entity_id(focus_target) or "")

    _set_phase(game, veterans_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(veterans_player.stratagems, "BRINGERS OF DESPAIR") is not None
    assert veterans_player.stratagems.use(
        "BRINGERS OF DESPAIR",
        unit=chosen,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert chosen.has_fight_first() is True

    game.event_system.publish("phase_end", player=veterans_player, phase=game.phase)
    assert chosen.has_fight_first() is False


def test_contemptuous_disregard_applies_armour_of_contempt_mapping_and_clears_for_the_attacker():
    game, veterans_player, enemy_player, veterans_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    veterans_army.add_unit(legionaries)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[legionaries])
    assert _pending_by_name(veterans_player.stratagems, "CONTEMPTUOUS DISREGARD") is not None
    assert veterans_player.stratagems.use(
        "CONTEMPTUOUS DISREGARD",
        unit=legionaries,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )

    attacker_key = veterans_player.stratagems._attacker_unit_key(attacker)
    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    ap_map = dict(sr.get("armour_of_contempt_ap_worsen", {}) or {})
    assert int(ap_map.get(str(attacker_key), 0) or 0) == 1

    veterans_player.stratagems._clear_armour_of_contempt_for_attacker(attacker)
    sr_after = dict(getattr(legionaries, "special_rules", {}) or {})
    assert not dict(sr_after.get("armour_of_contempt_ap_worsen", {}) or {})


def test_millennia_of_experience_queues_reactive_move_request():
    game, veterans_player, enemy_player, veterans_army, enemy_army = _build_game()
    raptors = _make_unit(
        "Raptors",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    enemy = _make_unit("Enemy Movers", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    veterans_army.add_unit(raptors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, raptors, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(veterans_player.stratagems, "MILLENNIA OF EXPERIENCE") is not None

    assert veterans_player.stratagems.use(
        "MILLENNIA OF EXPERIENCE",
        unit=raptors,
        moving_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "veterans_millennia_of_experience"
    assert str(context.get("veterans_millennia_of_experience_trigger_unit_id", "") or "") == str(
        get_entity_id(enemy) or ""
    )


def test_endless_ire_prompts_for_new_focus_of_hatred_and_updates_after_selection():
    game, veterans_player, enemy_player, veterans_army, enemy_army = _build_game()
    chaos_lord = _make_unit(
        "Chaos Lord",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    focus_target = _make_unit("Enemy Focus", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    replacement_target = _make_unit(
        "Enemy Replacement",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_destroyer = _make_unit("Enemy Destroyer", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    veterans_army.add_unit(chaos_lord)
    enemy_army.add_unit(focus_target)
    enemy_army.add_unit(replacement_target)
    enemy_army.add_unit(enemy_destroyer)
    _deploy_unit(game, chaos_lord, 10.0, 10.0)
    _deploy_unit(game, focus_target, 16.0, 10.0)
    _deploy_unit(game, replacement_target, 18.0, 10.0)
    _deploy_unit(game, enemy_destroyer, 22.0, 10.0)
    game.rebuild_entity_registry()

    chaos_lord._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True
    mgr = veterans_army.chaos_space_marines_detachments
    mgr.veterans_focus_of_hatred_target_unit_id = str(get_entity_id(focus_target) or "")

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "unit_destroyed",
        unit=focus_target,
        destroyed_by_unit=enemy_destroyer,
    )
    assert _pending_by_name(veterans_player.stratagems, "ENDLESS IRE") is not None

    assert veterans_player.stratagems.use(
        "ENDLESS IRE",
        unit=chaos_lord,
        destroyed_unit=focus_target,
        phase_name="Fight phase",
        dequeue=True,
    )
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="veterans_endless_ire_focus_target")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("source_unit_id", "") or "") == str(get_entity_id(chaos_lord) or "")

    option = _find_target_option(request, target_unit_id=str(get_entity_id(replacement_target) or ""))
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=veterans_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert str(mgr.veterans_focus_of_hatred_target_unit_id or "") == str(get_entity_id(replacement_target) or "")
