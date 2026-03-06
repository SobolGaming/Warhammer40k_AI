from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        wounds: int = 4,
        movement: int = 7,
        toughness: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Imperial Agents",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    cost: int = 100,
    wounds: int = 4,
    movement: int = 7,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
            wounds=wounds,
            movement=movement,
            toughness=toughness,
        )
    )
    unit.possible_abilities = list(abilities or [])
    unit._ability_cache = {}
    return unit


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    ia_army = Army("Imperial Agents", "Veiled Blade Elimination Force")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_player, enemy_player


def _pending_yes_no_for_ability(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key or ""):
            return request
    return None


def _pending_quarry_for_ability(game: Game, *, ability: str, ability_key: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability or ""):
            continue
        if ability_key and str(ctx.get("ability_key", "") or "") != str(ability_key or ""):
            continue
        return request
    return None


def _resolve_yes(game: Game, request, player: Player):
    yes_option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            yes_option_id = option.option_id
            break
    assert yes_option_id is not None
    return resolve_decision_command(game, request, yes_option_id, player_id=player.id)


def _officio_keywords():
    return ["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"]


def _ia_faction_keywords():
    return ["AGENTS OF THE IMPERIUM", "IMPERIUM"]


def test_extremis_sanction_points_surcharge_applies_to_officio_assassinorum_units():
    army = Army("Imperial Agents", "Veiled Blade Elimination Force")
    army.faction_id = "AOI"

    expected_costs = {
        "Callidus Assassin": 140,
        "Culexus Assassin": 140,
        "Eversor Assassin": 135,
        "Vindicare Assassin": 145,
    }
    for name, expected in expected_costs.items():
        unit = _make_unit(
            name,
            keywords=_officio_keywords(),
            faction_keywords=_ia_faction_keywords(),
            cost=100,
        )
        army.add_unit(unit)
        assert int(unit.get_unit_cost()) == int(expected)

    inquisitor = _make_unit(
        "Inquisitor",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=_ia_faction_keywords(),
        cost=100,
    )
    army.add_unit(inquisitor)
    assert int(inquisitor.get_unit_cost()) == 100


def test_extremis_sanction_grants_extra_use_from_unit_level_assassin_ability_and_honors_round_lock():
    game, ia_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.turn = 1

    overkill = Ability(
        "Overkill",
        "AOI",
        (
            "Once per battle, in your Movement phase, this model can use this ability before it makes a Normal move. "
            "If it does, until the end of the turn, add 6\" to this model's Move characteristic and add 3 to the "
            "Attacks characteristic of this model's melee weapons."
        ),
        "Datasheet",
        "",
    )
    eversor = _make_unit(
        "Eversor Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[overkill],
    )

    ia_player.army.add_unit(eversor)
    game.rebuild_entity_registry()
    model = eversor.models[0]

    assert int(model.remaining_once_per_battle_uses("movement_phase_normal_move_bonus:overkill")) == 2
    assert model.mark_used_once_per_battle(
        "movement_phase_normal_move_bonus:overkill",
        phase_name="MOVEMENT_PHASE",
        ability_name="Overkill",
        source="datasheet",
    )
    # Extra use exists, but not in the same battle round.
    assert int(model.remaining_once_per_battle_uses("movement_phase_normal_move_bonus:overkill")) == 0

    game.turn = 2
    assert int(model.remaining_once_per_battle_uses("movement_phase_normal_move_bonus:overkill")) == 1


def test_hammerhand_grants_lethal_hits_to_unit_melee_weapons_after_charge_move():
    army = Army("Imperial Agents", "Other")
    army.faction_id = "AOI"
    hammerhand = Ability(
        "Hammerhand (Psychic)",
        "AOI",
        (
            "Each time a model in this unit makes a Charge move, until the end of the turn, "
            "melee weapons equipped by models in this unit have the [LETHAL HITS] ability."
        ),
        "Datasheet",
        "",
    )
    terminators = _make_unit(
        "Grey Knights Terminator Squad",
        keywords=["INFANTRY"],
        faction_keywords=_ia_faction_keywords(),
        abilities=[hammerhand],
    )

    model = terminators.models[0]
    model.wargear = [
        SimpleNamespace(name="Nemesis force weapon", is_melee=lambda: True, is_ranged=lambda: False),
        SimpleNamespace(name="Storm bolter", is_melee=lambda: False, is_ranged=lambda: True),
    ]

    applied = terminators._apply_charge_move_weapon_keyword_bonuses()
    assert applied

    melee_bonuses = model.get_temporary_weapon_keyword_bonuses("Nemesis force weapon")
    melee_keywords = {str(entry.get("keyword", "")).upper() for entry in melee_bonuses}
    assert "LETHAL HITS" in melee_keywords

    ranged_bonuses = model.get_temporary_weapon_keyword_bonuses("Storm bolter")
    ranged_keywords = {str(entry.get("keyword", "")).upper() for entry in ranged_bonuses}
    assert "LETHAL HITS" not in ranged_keywords


def test_cat_unit_prompt_applies_ignores_cover_to_ranged_weapons():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 1

    cat_unit = Ability(
        "CAT Unit",
        "AOI",
        (
            "Once per battle, when this unit is selected to shoot, until the end of the phase, "
            "ranged weapons equipped by models in this unit gain the [IGNORES COVER] ability."
        ),
        "Datasheet",
        "",
    )
    breachers = _make_unit(
        "Imperial Navy Breachers",
        keywords=["INFANTRY", "GRENADES"],
        faction_keywords=_ia_faction_keywords(),
        abilities=[cat_unit],
    )
    attacker = breachers.models[0]
    attacker.wargear = [
        SimpleNamespace(_id="navis_shotgun_1", name="Navis shotgun", is_melee=lambda: False, is_ranged=lambda: True),
    ]
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(breachers)
    enemy_player.army.add_unit(target)
    _deploy_unit(game, breachers, 0.0, 0.0)
    _deploy_unit(game, target, 6.0, 0.0)
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_cat_unit(attacking_unit=breachers, target_units=[target])
    request = _pending_yes_no_for_ability(game, "cat_unit")
    assert request is not None
    result = _resolve_yes(game, request, ia_player)
    assert bool(getattr(result, "ok", False))

    bonuses = attacker.get_temporary_weapon_keyword_bonuses("Navis shotgun")
    keywords = {str(entry.get("keyword", "")).upper() for entry in bonuses}
    assert "IGNORES COVER" in keywords
    assert breachers.has_used_unit_once_per_battle("cat_unit")

    game._on_shooting_targets_selected_cat_unit(attacking_unit=breachers, target_units=[target])
    assert _pending_yes_no_for_ability(game, "cat_unit") is None


def test_gheistskull_extends_grenade_target_range_once_per_battle():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 1

    gheistskull = Ability(
        "Gheistskull",
        "AOI",
        (
            "Once per battle, when you select this unit as the target of the Grenade Stratagem, "
            "you can target one enemy unit visible to and within 18\" of this unit that is not within "
            "Engagement Range of any units from your army, instead of one within 8\"."
        ),
        "Datasheet",
        "",
    )
    breachers = _make_unit(
        "Imperial Navy Breachers",
        keywords=["INFANTRY", "GRENADES"],
        faction_keywords=_ia_faction_keywords(),
        abilities=[gheistskull],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )
    enemy_near = _make_unit(
        "Enemy Near",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(breachers)
    enemy_player.army.add_unit(enemy_far)
    enemy_player.army.add_unit(enemy_near)
    _deploy_unit(game, breachers, 0.0, 0.0)
    _deploy_unit(game, enemy_far, 15.0, 0.0)
    _deploy_unit(game, enemy_near, 6.0, 0.0)
    game.rebuild_entity_registry()

    rule = breachers.get_gheistskull_grenade_rule()
    assert isinstance(rule, dict)
    assert int(rule.get("range", 0) or 0) == 18
    assert int(rule.get("base_range", 0) or 0) == 8

    ia_player.command_points = 3
    assert ia_player.stratagems.use(
        "Grenade",
        target_unit=breachers,
        unit=breachers,
        enemy_unit=enemy_far,
        phase_name="Shooting phase",
    )
    assert breachers.has_used_unit_once_per_battle("gheistskull_grenade_range_override")

    ia_player.stratagems._used_stratagems_this_phase.clear()
    ia_player.stratagems._grenade_units_this_phase.clear()
    ia_player.command_points = 3

    assert not ia_player.stratagems.use(
        "Grenade",
        target_unit=breachers,
        unit=breachers,
        enemy_unit=enemy_far,
        phase_name="Shooting phase",
    )

    assert ia_player.stratagems.use(
        "Grenade",
        target_unit=breachers,
        unit=breachers,
        enemy_unit=enemy_near,
        phase_name="Shooting phase",
    )


def test_glovodan_psyber_eagle_selects_target_and_blocks_cover_until_next_command_phase():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 1

    glovodan = Ability(
        "Glovodan Psyber-eagle",
        "AOI",
        (
            "In your Command phase, you can select one enemy unit within 18\" of the bearer. "
            "Until the start of your next Command phase, that unit cannot have the Benefit of Cover."
        ),
        "Datasheet",
        "",
    )
    coteaz = _make_unit(
        "Inquisitor Coteaz",
        keywords=["INFANTRY", "CHARACTER", "INQUISITOR"],
        faction_keywords=_ia_faction_keywords(),
        abilities=[glovodan],
    )
    enemy_target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(coteaz)
    enemy_player.army.add_unit(enemy_target)
    _deploy_unit(game, coteaz, 0.0, 0.0)
    _deploy_unit(game, enemy_target, 12.0, 0.0)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=ia_player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = _pending_quarry_for_ability(
        game,
        ability="post_shoot_no_cover",
        ability_key="command_phase_no_cover:glovodan_psyber_eagle",
    )
    assert request is not None

    target_option_id = None
    target_unit_id = str(get_entity_id(enemy_target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_unit_id:
            target_option_id = option.option_id
            break
    assert target_option_id is not None

    result = resolve_decision_command(game, request, target_option_id, player_id=ia_player.id)
    assert bool(getattr(result, "ok", False))

    target_sr = dict(getattr(enemy_target, "special_rules", {}) or {})
    assert bool(target_sr.get("post_shoot_no_cover_active"))
    assert str(target_sr.get("post_shoot_no_cover_expires_timing", "") or "") == "OWNER_NEXT_COMMAND_START"

    attacker = coteaz.models[0]
    attack_profile = WargearProfile(
        "Test Rifle",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Test Rifle", is_melee=lambda: False, is_ranged=lambda: True),
    )
    attack_instance = {}
    attack_profile._hit_target_with_tracking(
        enemy_target,
        attacker,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("ignores_cover"))

    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert bool(getattr(enemy_target, "special_rules", {}).get("post_shoot_no_cover_active"))

    game.turn = 2
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=ia_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert not bool(getattr(enemy_target, "special_rules", {}).get("post_shoot_no_cover_active"))


def test_malefic_wardings_grants_four_plus_invulnerable_vs_psychic_and_daemon_attacks():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    malefic_wardings = Ability(
        "Malefic Wardings (Psychic)",
        "AOI",
        (
            "While this model is leading a unit, models in that unit have a 6+ invulnerable save, "
            "and a 4+ invulnerable save against Psychic Attacks and attacks made by DAEMON models."
        ),
        "Datasheet",
        "",
    )
    leader = Ability("Leader", "AOI", "Leader.", "Datasheet", "")
    bodyguard = _make_unit(
        "Inquisitorial Agents",
        keywords=["INFANTRY"],
        faction_keywords=_ia_faction_keywords(),
    )
    coteaz = _make_unit(
        "Inquisitor Coteaz",
        keywords=["INFANTRY", "CHARACTER", "INQUISITOR"],
        faction_keywords=_ia_faction_keywords(),
        abilities=[leader, malefic_wardings],
    )
    daemon_attacker_unit = _make_unit(
        "Daemon Attacker",
        faction_name="Enemy",
        keywords=["INFANTRY", "DAEMON"],
        faction_keywords=["CHAOS"],
    )
    normal_attacker_unit = _make_unit(
        "Normal Attacker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(bodyguard)
    ia_player.army.add_unit(coteaz)
    enemy_player.army.add_unit(daemon_attacker_unit)
    enemy_player.army.add_unit(normal_attacker_unit)
    _deploy_unit(game, bodyguard, 0.0, 0.0)
    _deploy_unit(game, coteaz, 0.2, 0.0)
    _deploy_unit(game, daemon_attacker_unit, 10.0, 0.0)
    _deploy_unit(game, normal_attacker_unit, 10.0, 2.0)
    game.rebuild_entity_registry()

    coteaz.can_be_attached_to = [bodyguard.get_datasheet_id()]
    coteaz.can_be_attached_to_names = [bodyguard.name]
    coteaz.attach_to_unit(bodyguard)

    target_model = bodyguard.models[0]
    daemon_attacker = daemon_attacker_unit.models[0]
    normal_attacker = normal_attacker_unit.models[0]

    base_profile = WargearProfile(
        "Bolt Rifle",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-6",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True),
    )
    psychic_profile = WargearProfile(
        "Psychic Bolt",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-6",
            "D": "1",
            "description": "[PSYCHIC]",
        },
        parent_wargear=SimpleNamespace(name="Psychic Bolt", is_melee=lambda: False, is_ranged=lambda: True),
    )

    daemon_save = base_profile._save_with_tracking(
        target_model,
        {"attacker_model": daemon_attacker, "target_unit": bodyguard},
        ap=-6,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert str(daemon_save.get("save_type", "") or "") == "invulnerable"
    assert int(daemon_save.get("final_save", 0) or 0) == 4

    psychic_save = psychic_profile._save_with_tracking(
        target_model,
        {"attacker_model": normal_attacker, "target_unit": bodyguard},
        ap=-6,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert str(psychic_save.get("save_type", "") or "") == "invulnerable"
    assert int(psychic_save.get("final_save", 0) or 0) == 4

    normal_save = base_profile._save_with_tracking(
        target_model,
        {"attacker_model": normal_attacker, "target_unit": bodyguard},
        ap=-6,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert str(normal_save.get("save_type", "") or "") == "invulnerable"
    assert int(normal_save.get("final_save", 0) or 0) == 6


def test_shieldbreaker_prompt_applies_and_modifies_wound_resolution():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 1

    shieldbreaker = Ability(
        "Shieldbreaker",
        "AOI",
        (
            "Once per battle, when selecting targets for this model's exitus rifle, it can fire a shieldbreaker round. "
            "If it does, until the end of the phase, each time this model makes an attack with that weapon, add 1 to "
            "the Wound roll and any successful Wound roll scores a Critical Wound."
        ),
        "Datasheet",
        "",
    )
    vindicare = _make_unit(
        "Vindicare Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[shieldbreaker],
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
        toughness=4,
    )
    ia_player.army.add_unit(vindicare)
    enemy_player.army.add_unit(target)
    _deploy_unit(game, vindicare, 0.0, 0.0)
    _deploy_unit(game, target, 4.0, 0.0)
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_shieldbreaker(attacking_unit=vindicare, target_units=[target])

    request = _pending_yes_no_for_ability(game, "shieldbreaker")
    assert request is not None
    assert str((request.context or {}).get("model_id", "") or "") == str(get_entity_id(vindicare.models[0]) or "")
    result = _resolve_yes(game, request, ia_player)
    assert bool(getattr(result, "ok", False))

    attacker = vindicare.models[0]
    assert attacker.has_used_once_per_battle("shieldbreaker")
    assert int(attacker.get_temporary_weapon_wound_bonus("exitus rifle")[0]) == 1
    assert int(attacker.get_temporary_weapon_crit_wound_threshold("exitus rifle")[0]) == 2

    profile = WargearProfile(
        "Standard",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "2+",
            "S": "8",
            "AP": "-3",
            "D": "3",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Exitus rifle", is_melee=lambda: False),
    )
    attack_instance = {}
    wound = profile._wound_target_with_tracking(
        target,
        attacker,
        attack_instance,
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(wound.get("crit_threshold", 0) or 0) == 2
    assert bool(attack_instance.get("crit_wound", False))
    assert any("to wound" in str(reason or "").lower() for reason in list(wound.get("modifiers", []) or []))


def test_soulless_horror_can_be_used_twice_per_battle_but_not_twice_in_the_same_round():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 1

    soulless_horror = Ability(
        "Soulless Horror",
        "AOI",
        (
            "Once per battle, at the start of any Command phase, this model can use this ability. If it does, each enemy "
            "unit within 9\" of this model must take a Battle-shock test, subtracting 1 from that test (or subtracting 2 "
            "if that unit is a PSYKER)."
        ),
        "Datasheet",
        "",
    )
    culexus = _make_unit(
        "Culexus Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[soulless_horror],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["IMPERIUM"],
    )
    enemy_non_psyker = _make_unit(
        "Enemy Non-Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(culexus)
    enemy_player.army.add_unit(enemy_psyker)
    enemy_player.army.add_unit(enemy_non_psyker)
    _deploy_unit(game, culexus, 0.0, 0.0)
    _deploy_unit(game, enemy_psyker, 6.0, 0.0)
    _deploy_unit(game, enemy_non_psyker, 6.0, 2.0)
    game.rebuild_entity_registry()

    captures: list[tuple[str, int]] = []

    def _capture_factory(unit):
        def _capture(_turn):
            sr = dict(getattr(unit, "special_rules", {}) or {})
            captures.append((str(getattr(unit, "name", "") or ""), int(sr.get("battle_shock_test_modifier", 0) or 0)))
            sr.pop("battle_shock_test_modifier", None)
            sr.pop("battle_shock_test_modifier_reasons", None)
            unit.special_rules = sr
        return _capture

    enemy_psyker.take_battle_shock_test = _capture_factory(enemy_psyker)
    enemy_non_psyker.take_battle_shock_test = _capture_factory(enemy_non_psyker)

    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)
    request = _pending_yes_no_for_ability(game, "soulless_horror")
    assert request is not None
    result = _resolve_yes(game, request, ia_player)
    assert bool(getattr(result, "ok", False))

    assert ("Enemy Psyker", -2) in captures
    assert ("Enemy Non-Psyker", -1) in captures

    # Same battle round: no additional prompt.
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    assert _pending_yes_no_for_ability(game, "soulless_horror") is None

    # Next battle round: prompt appears again from Extremis Sanction extra use.
    game.turn = 2
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)
    request_round_two = _pending_yes_no_for_ability(game, "soulless_horror")
    assert request_round_two is not None

    invalid = resolve_decision_command(
        game,
        request_round_two,
        "invalid-option-id",
        player_id=ia_player.id,
    )
    assert not bool(getattr(invalid, "ok", False))

    # Decision remains pending and can still be resolved legally.
    request_round_two = _pending_yes_no_for_ability(game, "soulless_horror")
    assert request_round_two is not None
    valid = _resolve_yes(game, request_round_two, ia_player)
    assert bool(getattr(valid, "ok", False))

    # Both uses consumed.
    game.turn = 3
    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)
    assert _pending_yes_no_for_ability(game, "soulless_horror") is None


def test_acrobatic_escape_parses_redeploy_for_next_reinforcements_step():
    acrobatic_escape = Ability(
        "Acrobatic Escape",
        "AOI",
        (
            "At the end of the Fight phase, if this model is within Engagement Range of one or more enemy units, "
            "it can make a Fall Back move of up to D6\". In addition, at the end of your opponent's turn, if this "
            "model is not within 3\" of one or more enemy units, you can remove it from the battlefield and then, "
            "in the Reinforcements step of your next Movement phase, set it up anywhere on the battlefield that is "
            "more than 9\" horizontally away from all enemy models. If the battle ends and this model is not on the "
            "battlefield, it is destroyed."
        ),
        "Datasheet",
        "",
    )
    callidus = _make_unit(
        "Callidus Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[acrobatic_escape],
    )

    spec = callidus._scan_end_of_opponent_turn_strategic_reserves_ability()
    assert spec is not None
    assert spec.get("ability_key") == "opponent_turn_strategic_reserves"
    assert bool(spec.get("once_per_battle", True)) is False
    assert int(spec.get("min_enemy_distance_horiz", 0) or 0) == 3
    assert bool(spec.get("return_as_deep_strike")) is True
    assert float(spec.get("return_setup_min_enemy_distance_horiz", 0.0) or 0.0) == 9.0
    assert bool(spec.get("must_arrive_next_movement_phase")) is True


def test_acrobatic_escape_queues_fall_back_move_at_fight_phase_end(monkeypatch):
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    acrobatic_escape = Ability(
        "Acrobatic Escape",
        "AOI",
        (
            "At the end of the Fight phase, if this model is within Engagement Range of one or more enemy units, "
            "it can make a Fall Back move of up to D6\". In addition, at the end of your opponent's turn, if this "
            "model is not within 3\" of one or more enemy units, you can remove it from the battlefield and then, "
            "in the Reinforcements step of your next Movement phase, set it up anywhere on the battlefield that is "
            "more than 9\" horizontally away from all enemy models."
        ),
        "Datasheet",
        "",
    )
    callidus = _make_unit(
        "Callidus Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[acrobatic_escape],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(callidus)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, callidus, 0.0, 0.0)
    _deploy_unit(game, enemy, 0.5, 0.0)
    callidus.round_state.eligible_to_fight_this_phase = False
    callidus.round_state.fought_this_phase = False
    game.rebuild_entity_registry()

    monkeypatch.setattr("warhammer40k_ai.engine.game.get_roll", lambda spec: 4 if str(spec).upper() == "D6" else 0)

    game._on_phase_end_raid_and_run(phase=BattleRoundPhases.FIGHT_PHASE)

    move_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_MOVE_UNIT]
    assert len(move_requests) == 1
    ctx = dict(getattr(move_requests[0], "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "raid_and_run"
    assert str(ctx.get("movement_type", "") or "") == "fall_back"
    assert int(ctx.get("max_distance", 0) or 0) == 4


def test_acrobatic_escape_does_not_queue_fall_back_when_not_engaged():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0

    acrobatic_escape = Ability(
        "Acrobatic Escape",
        "AOI",
        (
            "At the end of the Fight phase, if this model is within Engagement Range of one or more enemy units, "
            "it can make a Fall Back move of up to D6\". In addition, at the end of your opponent's turn, if this "
            "model is not within 3\" of one or more enemy units, you can remove it from the battlefield and then, "
            "in the Reinforcements step of your next Movement phase, set it up anywhere on the battlefield that is "
            "more than 9\" horizontally away from all enemy models."
        ),
        "Datasheet",
        "",
    )
    callidus = _make_unit(
        "Callidus Assassin",
        keywords=_officio_keywords(),
        faction_keywords=_ia_faction_keywords(),
        abilities=[acrobatic_escape],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )

    ia_player.army.add_unit(callidus)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, callidus, 0.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)
    game.rebuild_entity_registry()

    game._on_phase_end_raid_and_run(phase=BattleRoundPhases.FIGHT_PHASE)

    move_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_MOVE_UNIT]
    assert not move_requests
