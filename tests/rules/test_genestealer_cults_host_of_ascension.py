from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, faction: str, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "2",
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
        self.attached_to = []


def _make_unit(name: str, *, faction: str, faction_keywords: list[str], keywords: list[str]) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction=faction,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    model = unit.models[0]
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:autopistol",
            name="Autopistol",
            is_ranged=lambda: True,
            is_melee=lambda: False,
            profiles={},
        )
    )
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:cult_knife",
            name="Cult Knife",
            is_ranged=lambda: False,
            is_melee=lambda: True,
            profiles={},
        )
    )
    unit.deployed = True
    return unit


def _make_game(
    detachment_type: str,
    *,
    gsc_control: PlayerControl = PlayerControl.LOCAL,
    enemy_control: PlayerControl = PlayerControl.LOCAL,
) -> tuple[Game, Player, Player, Unit]:
    gsc_army = Army("Genestealer Cults", detachment_type)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    gsc_player = Player("GSC", gsc_control, army=gsc_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[gsc_player, enemy_player])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1

    gsc_unit = _make_unit(
        "Neophyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    gsc_army.add_unit(gsc_unit)
    game.map.units = [gsc_unit]
    game.rebuild_entity_registry()
    return game, gsc_player, enemy_player, gsc_unit


def _weapon_bonuses(unit: Unit, weapon_name: str, *, attack_type: str) -> dict:
    return unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name=weapon_name,
        attack_type=attack_type,
    )


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="GC",
        detachment="Host of Ascension",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _resolve_yes(game: Game, request, *, player_id: str) -> None:
    option_id = None
    for opt in list(getattr(request, "options", []) or []):
        if bool((getattr(opt, "payload", {}) or {}).get("choice", False)):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, request, option_id, player_id=player_id)


def _pending_reaction_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _ranged_profile():
    weapon = Wargear(
        {
            "name": "Test Carbine",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_a_perfect_ambush_applies_on_reinforcements_setup() -> None:
    game, _gsc_player, _enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 0

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    ranged_bonuses = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert ranged_bonuses.get("sustained_hits_value", 0) == 1
    assert ranged_bonuses.get("ignores_cover", False) is True

    melee_bonuses = _weapon_bonuses(gsc_unit, "Cult Knife", attack_type="melee")
    assert melee_bonuses.get("sustained_hits_value", 0) == 1
    assert melee_bonuses.get("ignores_cover", False) is True


def test_a_perfect_ambush_expires_at_end_of_owners_next_fight_phase() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 1

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    before_cleanup = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert before_cleanup.get("sustained_hits_value", 0) == 1
    assert before_cleanup.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_enemy_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_enemy_fight.get("sustained_hits_value", 0) == 1
    assert after_enemy_fight.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_owner_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_owner_fight.get("sustained_hits_value", 0) == 0
    assert after_owner_fight.get("ignores_cover", False) is False


def test_host_of_ascension_enhancement_descriptors_registered() -> None:
    prowling = get_enhancement_tool_descriptor(enhancement_id="000009067002")
    assert prowling is not None
    assert prowling.name == "Prowling Agitant"
    assert prowling.effect == "reactive_normal_move_up_to_d6"

    chink = get_enhancement_tool_descriptor(enhancement_id="000009067003")
    assert chink is not None
    assert chink.name == "A Chink in Their Armour"
    assert chink.effect == "grant_weapon_keywords"
    assert tuple(chink.effect_params.get("keywords", ())) == ("LETHAL HITS",)

    our_time = get_enhancement_tool_descriptor(enhancement_id="000009067004")
    assert our_time is not None
    assert our_time.name == "Our Time Is Nigh"
    assert our_time.once_per_battle is True
    assert int(our_time.effect_params.get("charge_roll_bonus", 0) or 0) == 2

    edict = get_enhancement_tool_descriptor(enhancement_id="000009067005")
    assert edict is not None
    assert edict.name == "Assassination Edict"
    assert edict.effect == "add_hit_roll_modifier"
    assert int(edict.effect_params.get("hit_roll_bonus", 0) or 0) == 1


def test_a_chink_in_their_armour_grants_ranged_lethal_hits_on_reinforcements() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 1
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067003",
        name="A Chink in Their Armour",
        description=(
            "GENESTEALER CULTS model only. Each time the bearer is set up on the battlefield as Reinforcements, "
            "until the end of your next Fight phase, ranged weapons equipped by models in the bearer's unit have "
            "the [LETHAL HITS] ability."
        ),
    )

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    ranged_bonuses = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert ranged_bonuses.get("lethal_hits", False) is True
    melee_bonuses = _weapon_bonuses(gsc_unit, "Cult Knife", attack_type="melee")
    assert melee_bonuses.get("lethal_hits", False) is False

    game._on_phase_end_cleanup(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    still_active = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert still_active.get("lethal_hits", False) is True

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.FIGHT_PHASE)
    expired = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert expired.get("lethal_hits", False) is False


def test_prowling_agitant_triggers_loping_speed_prompt_from_bearers_unit_wording() -> None:
    game, _gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    enemy_unit = _make_unit(
        "Enemy Movers",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_unit)
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067002",
        name="Prowling Agitant",
        description=(
            "GENESTEALER CULTS model only. Once per turn, when an enemy unit ends a Normal, Advance or Fall Back "
            "move within 9\" of the bearer's unit, if the bearer's unit is not within Engagement Range of any enemy "
            "units, it can make a Normal move of up to D6\"."
        ),
    )

    gsc_unit.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    game.map.units = [gsc_unit, enemy_unit]
    game.rebuild_entity_registry()

    prompts = []
    game.event_system.subscribe("loping_speed_prompt", lambda **kwargs: prompts.append(kwargs))
    game.event_system.publish("unit_move_ended", unit=enemy_unit, action="move")

    assert len(prompts) == 1
    assert prompts[0].get("unit") is gsc_unit
    assert prompts[0].get("moving_unit") is enemy_unit


def test_our_time_is_nigh_is_optional_and_applies_after_confirmation() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game(
        "Host of Ascension",
        gsc_control=PlayerControl.REMOTE,
        enemy_control=PlayerControl.REMOTE,
    )
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067004",
        name="Our Time Is Nigh",
        description=(
            "GENESTEALER CULTS model only. Once per battle, when the bearer's unit declares a charge, the bearer can "
            "use this Enhancement. If it does, until the end of the phase, add 2 to Charge rolls made for the bearer's unit."
        ),
    )

    target = _make_unit(
        "Target Unit",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(target)
    game.map.units = [gsc_unit, target]
    game.rebuild_entity_registry()

    gsc_unit._can_declare_charge_base = lambda _game, out_of_turn=False: True
    gsc_unit.can_declare_charge_against = lambda _target, _game, out_of_turn=False: True

    mods_before = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert not any("our time is nigh" in str(source or "").strip().lower() for _val, source in mods_before)

    declared = game.declare_charge(gsc_unit, [target])
    assert declared is not None

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "our_time_is_nigh"
    ]
    assert len(pending) == 1
    _resolve_yes(game, pending[0], player_id=gsc_player.id)

    assert gsc_unit.has_used_unit_once_per_battle("our_time_is_nigh")
    mods_after = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert any(int(val or 0) == 2 and "our time is nigh" in str(source or "").strip().lower() for val, source in mods_after)

    game.phase = BattleRoundPhases.FIGHT_PHASE
    mods_after_phase = list(game.get_charge_roll_modifiers(gsc_unit, target_unit=target))
    assert not any("our time is nigh" in str(source or "").strip().lower() for _val, source in mods_after_phase)


def test_assassination_edict_adds_hit_against_character_targets() -> None:
    game, _gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    _apply_enhancement(
        gsc_unit,
        enhancement_id="000009067005",
        name="Assassination Edict",
        description=(
            "GENESTEALER CULTS model only. Each time a model in the bearer's unit makes an attack that targets a "
            "CHARACTER unit, add 1 to the Hit roll."
        ),
    )

    character_target = _make_unit(
        "Enemy Character",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["CHARACTER", "INFANTRY"],
    )
    non_character_target = _make_unit(
        "Enemy Infantry",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(character_target)
    enemy_player.army.add_unit(non_character_target)
    game.map.units = [gsc_unit, character_target, non_character_target]

    mods_vs_character = gsc_unit.get_unit_hit_reroll_modifiers("ranged", target=character_target)
    assert int(mods_vs_character.get("hit", 0) or 0) >= 1
    assert any("assassination edict" in str(reason or "").strip().lower() for reason in mods_vs_character.get("hit_reasons", ()))

    mods_vs_non_character = gsc_unit.get_unit_hit_reroll_modifiers("ranged", target=non_character_target)
    assert not any(
        "assassination edict" in str(reason or "").strip().lower()
        for reason in mods_vs_non_character.get("hit_reasons", ())
    )


def test_host_of_ascension_stratagem_descriptors_registered() -> None:
    coordinated = get_stratagem_tool_descriptor(stratagem_id="000009068002")
    assert coordinated is not None
    assert coordinated.name == "Coordinated Trap"
    assert coordinated.effect == "target_lock_and_wound_bonus"
    assert int(coordinated.effect_params.get("wound_roll_bonus", 0) or 0) == 1

    primed = get_stratagem_tool_descriptor(stratagem_id="000009068003")
    assert primed is not None
    assert primed.name == "Primed and Readied"
    assert primed.effect == "critical_hits_on_5plus"
    assert int(primed.effect_params.get("critical_hit_threshold", 0) or 0) == 5

    tunnel = get_stratagem_tool_descriptor(stratagem_id="000009068004")
    assert tunnel is not None
    assert tunnel.name == "Tunnel Crawlers"
    assert tunnel.effect == "deep_strike_min_distance_override_with_no_charge"
    assert int(tunnel.effect_params.get("min_distance", 0) or 0) == 6
    assert bool(tunnel.effect_params.get("cannot_charge_this_turn")) is True

    lying = get_stratagem_tool_descriptor(stratagem_id="000009068005")
    assert lying is not None
    assert lying.name == "Lying in Wait"
    assert lying.effect == "cult_ambush_marker_setup_override"
    assert int(lying.effect_params.get("setup_max_distance", 0) or 0) == 6
    assert str(lying.effect_params.get("enemy_distance_mode", "") or "") == "engagement_range"

    shadows = get_stratagem_tool_descriptor(stratagem_id="000009068006")
    assert shadows is not None
    assert shadows.name == "Return to the Shadows"
    assert shadows.effect == "place_unit_into_strategic_reserves"
    assert str(shadows.effect_params.get("reserve_status", "") or "") == "strategic_reserves"

    snare = get_stratagem_tool_descriptor(stratagem_id="000009068007")
    assert snare is not None
    assert snare.name == "A Deadly Snare"
    assert snare.effect == "roll_d6_tiered_mortal_wounds_on_charging_enemy"
    assert str((snare.effect_params.get("mortal_wounds_table", {}) or {}).get("2-4", "") or "") == "D3"
    assert int((snare.effect_params.get("mortal_wounds_table", {}) or {}).get("5+", 0) or 0) == 3


def test_tunnel_crawlers_queues_and_applies_deep_strike_override_with_no_charge() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)
    enemy_unit = _make_unit(
        "Enemy Infantry",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_unit)
    enemy_unit.models[0].set_location(14.0, 10.0, 0.0, 0.0)
    enemy_unit.deployed = True
    enemy_unit.reserve_status = "deployed"
    game.map.units = [enemy_unit]
    game.rebuild_entity_registry()

    gsc_unit.deployed = False
    gsc_unit.reserve_status = "reserves"
    gsc_unit.has_deep_strike = lambda: True
    gsc_unit.can_arrive_from_reserves = lambda _turn: True

    phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.phase = phase
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=gsc_player, phase=phase)

    pending = _pending_reaction_by_name(gsc_player.stratagems, "TUNNEL CRAWLERS")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=gsc_unit,
        dequeue=True,
    )
    assert ok
    assert float(gsc_unit.get_deep_strike_min_distance_override() or 0.0) == 6.0

    gsc_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    gsc_unit.deployed = True
    gsc_unit.reserve_status = "deployed"
    gsc_unit.arrived_from_reserves_this_turn = True
    if gsc_unit not in game.map.units:
        game.map.units.append(gsc_unit)
    gsc_unit._finalize_reserves_arrival(turn=game.turn, game_map=game.map)

    assert not gsc_unit.can_declare_charge_against(enemy_unit, game)


def test_lying_in_wait_allows_cult_ambush_setup_within_six_and_not_engagement() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)
    gsc_unit.keywords.append("BATTLELINE")
    gsc_unit.deployed = False
    gsc_unit.reserve_status = "reserves"
    game.map.units = []
    game.rebuild_entity_registry()

    cult_ambush = gsc_player.army.cult_ambush
    assert cult_ambush is not None
    cult_ambush._prepare_unit_in_cult_ambush(gsc_unit, game=game)
    gsc_unit.can_arrive_from_reserves = lambda _turn: True
    marker = cult_ambush.place_marker_at(game, 10.0, 10.0)
    assert marker is not None

    enemy_unit = _make_unit(
        "Enemy Blocker",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_unit)
    enemy_unit.models[0].set_location(13.8, 10.0, 0.0, 0.0)
    enemy_unit.deployed = True
    enemy_unit.reserve_status = "deployed"
    game.map.units = [enemy_unit]
    game.rebuild_entity_registry()

    placements_before = cult_ambush._find_cult_ambush_placements(gsc_unit, marker, game=game)
    assert placements_before is None

    phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.phase = phase
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=phase)

    pending = _pending_reaction_by_name(gsc_player.stratagems, "LYING IN WAIT")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=gsc_unit,
        dequeue=True,
    )
    assert ok
    placements_after = cult_ambush._find_cult_ambush_placements(gsc_unit, marker, game=game)
    assert placements_after is not None


def test_primed_and_readied_queues_and_applies_critical_hits_on_five_plus() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)

    enemy_target = _make_unit(
        "Enemy Target",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_target)
    enemy_target.models[0].set_location(16.0, 10.0, 0.0, 0.0)
    game.map.units = [gsc_unit, enemy_target]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.phase = phase
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=gsc_player, phase=phase)

    pending = _pending_reaction_by_name(gsc_player.stratagems, "PRIMED AND READIED")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=gsc_unit,
        dequeue=True,
    )
    assert ok

    profile = _ranged_profile()
    hit = profile._hit_target_with_tracking(
        enemy_target,
        gsc_unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5
    assert any("primed and readied" in str(effect or "").strip().lower() for effect in list(hit.get("special_effects", []) or []))


def test_coordinated_trap_applies_target_lock_and_wound_bonus() -> None:
    game, gsc_player, enemy_player, first_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)

    second_unit = _make_unit(
        "Acolyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    marked_enemy = _make_unit(
        "Marked Enemy",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    gsc_player.army.add_unit(second_unit)
    enemy_player.army.add_unit(marked_enemy)
    enemy_player.army.add_unit(other_enemy)
    first_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    second_unit.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    marked_enemy.models[0].set_location(16.0, 10.0, 0.0, 0.0)
    other_enemy.models[0].set_location(18.0, 12.0, 0.0, 0.0)
    game.map.units = [first_unit, second_unit, marked_enemy, other_enemy]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.phase = phase
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=gsc_player, phase=phase)

    pending = _pending_reaction_by_name(gsc_player.stratagems, "COORDINATED TRAP")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        units=[first_unit, second_unit],
        enemy_unit=marked_enemy,
        dequeue=True,
    )
    assert ok

    expected_target_id = str(get_entity_id(marked_enemy) or "")
    for unit in (first_unit, second_unit):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("gsc_coordinated_trap_active")) is True
        assert str(sr.get("gsc_coordinated_trap_target_id", "") or "") == expected_target_id
        assert int(sr.get("gsc_coordinated_trap_wound_bonus", 0) or 0) == 1

    profile = _ranged_profile()
    can_target_marked = first_unit._can_model_shoot_weapon_at_target(first_unit.models[0], profile, marked_enemy, game.map)
    can_target_other = first_unit._can_model_shoot_weapon_at_target(first_unit.models[0], profile, other_enemy, game.map)
    assert can_target_marked
    assert not can_target_other

    mods_marked = first_unit.get_unit_wound_reroll_modifiers("ranged", target=marked_enemy)
    assert int(mods_marked.get("wound", 0) or 0) >= 1
    assert any("coordinated trap" in str(reason or "").strip().lower() for reason in mods_marked.get("wound_reasons", ()))

    mods_other = first_unit.get_unit_wound_reroll_modifiers("ranged", target=other_enemy)
    assert not any("coordinated trap" in str(reason or "").strip().lower() for reason in mods_other.get("wound_reasons", ()))


def test_coordinated_trap_fight_phase_requires_enemy_engaged_with_both_units() -> None:
    game, gsc_player, enemy_player, first_unit = _make_game("Host of Ascension")
    gsc_player.command_points = 5
    second_unit = _make_unit(
        "Acolyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    enemy_unit = _make_unit(
        "Enemy Fighters",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    gsc_player.army.add_unit(second_unit)
    enemy_player.army.add_unit(enemy_unit)
    first_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    second_unit.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    game.map.units = [first_unit, second_unit, enemy_unit]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="FIGHT_PHASE")
    game.phase = phase
    game.current_player_index = 0
    blocked = gsc_player.stratagems.use(
        "COORDINATED TRAP",
        units=[first_unit, second_unit],
        enemy_unit=enemy_unit,
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(gsc_player.command_points or 0) == 5


def test_return_to_the_shadows_queues_and_places_unit_into_strategic_reserves() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)
    game.map.units = [gsc_unit]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="FIGHT_PHASE")
    game.phase = phase
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=phase)
    game.event_system.publish("phase_end", player=enemy_player, phase=phase)

    pending = _pending_reaction_by_name(gsc_player.stratagems, "RETURN TO THE SHADOWS")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=gsc_unit,
        dequeue=True,
    )
    assert ok
    assert str(getattr(gsc_unit, "reserve_status", "") or "") == "strategic_reserves"
    assert gsc_unit not in list(getattr(game.map, "units", []) or [])


def test_return_to_the_shadows_rejects_unit_within_engagement_range() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    gsc_player.command_points = 5
    enemy_unit = _make_unit(
        "Enemy Fighters",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_unit)
    gsc_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    game.map.units = [gsc_unit, enemy_unit]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="FIGHT_PHASE")
    game.phase = phase
    game.current_player_index = 1
    blocked = gsc_player.stratagems.use(
        "RETURN TO THE SHADOWS",
        unit=gsc_unit,
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(gsc_player.command_points or 0) == 5


def test_a_deadly_snare_queues_and_deals_mortal_wounds(monkeypatch) -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)
    enemy_charger = _make_unit(
        "Enemy Charger",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    enemy_player.army.add_unit(enemy_charger)
    game.map.units = [gsc_unit, enemy_charger]
    game.rebuild_entity_registry()

    monkeypatch.setattr(
        "warhammer40k_ai.utility.dice.get_roll",
        lambda die: 5 if str(die or "").strip().upper() == "D6" else 2,
    )

    phase = SimpleNamespace(name="CHARGE_PHASE")
    game.phase = phase
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=phase)
    game.event_system.publish("charge_declared", unit=enemy_charger, target_units=[gsc_unit])

    pending = _pending_reaction_by_name(gsc_player.stratagems, "A DEADLY SNARE")
    assert pending is not None
    ok = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=gsc_unit,
        enemy_unit=enemy_charger,
        dequeue=True,
    )
    assert ok
    assert enemy_charger.is_alive() is False
    assert int(gsc_player.command_points or 0) == 4


def test_a_deadly_snare_rejects_unit_not_selected_as_charge_target() -> None:
    game, gsc_player, enemy_player, first_unit = _make_game("Host of Ascension")
    game.turn = 2
    gsc_player.command_points = 5
    gsc_player.stratagems.refresh_available()
    gsc_player.stratagems.enable_event_subscriptions(event_system=game.event_system)

    second_unit = _make_unit(
        "Acolyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    enemy_charger = _make_unit(
        "Enemy Charger",
        faction="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    gsc_player.army.add_unit(second_unit)
    enemy_player.army.add_unit(enemy_charger)
    game.map.units = [first_unit, second_unit, enemy_charger]
    game.rebuild_entity_registry()

    phase = SimpleNamespace(name="CHARGE_PHASE")
    game.phase = phase
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=phase)
    game.event_system.publish("charge_declared", unit=enemy_charger, target_units=[first_unit])

    pending = _pending_reaction_by_name(gsc_player.stratagems, "A DEADLY SNARE")
    assert pending is not None
    blocked = gsc_player.stratagems.use(
        str(pending.get("stratagem", "")),
        unit=second_unit,
        enemy_unit=enemy_charger,
        dequeue=True,
    )
    assert not blocked
    assert int(gsc_player.command_points or 0) == 5
