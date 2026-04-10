from unittest.mock import patch
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Data-Psalm Conclave")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    admech_player.command_points = 10
    enemy_player.command_points = 10
    admech_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    admech_player.stratagems.refresh_available()
    return game, admech_army, enemy_army, admech_player, enemy_player


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (idx * 0.05), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        existing = list(getattr(game.map, "units", []) or [])
        if unit not in existing:
            existing.append(unit)
            game.map.units = existing


def _phase_start(game: Game, acting_player: Player, phase_name: str) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = list(game.players).index(acting_player)
    game.event_system.publish("phase_start", player=acting_player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _find_data_psalm_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "data_psalm_benediction"
    ]


def _choose_benediction(game: Game, request, *, player_id: str, choice_key: str) -> None:
    wanted = str(choice_key or "").strip().upper()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _attack_result_stub() -> AttackResult:
    return AttackResult(
        weapon_name="Test Weapon",
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="",
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


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Gamma Blaster", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged",
        {
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Power Blades", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_data_psalm_round_one_queues_benediction_selection():
    game, admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    admech_army.on_battle_round_start(1)
    requests = _find_data_psalm_requests(game)
    assert len(requests) == 1
    request = requests[0]
    assert request.player_id == admech_player.id
    choices = {
        str((opt.payload or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(request.options or [])
    }
    assert choices == {"PANEGYRIC_PROCESSION", "CITATION_IN_SAVAGERY"}


def test_panegyric_procession_improves_ap_at_half_range_for_cult_mechanicus_units():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    cult_unit = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(cult_unit)
    enemy_army.add_unit(enemy)
    cult_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    game.map.units = [cult_unit, enemy]

    admech_army.on_battle_round_start(1)
    request = _find_data_psalm_requests(game)[0]
    _choose_benediction(game, request, player_id=admech_player.id, choice_key="PANEGYRIC_PROCESSION")

    profile = _ranged_profile()
    attacker_model = cult_unit.models[0]
    assert profile.get_effective_ap(attacker_model, enemy) == -1

    enemy.models[0].set_location(30.0, 10.0, 0.0, 0.0)
    assert profile.get_effective_ap(attacker_model, enemy) == 0


def test_citation_in_savagery_grants_melee_strength_and_attacks_when_charged():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    cult_unit = _make_unit(
        "Fulgurite Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["SPACE MARINES"])
    admech_army.add_unit(cult_unit)
    enemy_army.add_unit(enemy)
    cult_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    game.map.units = [cult_unit, enemy]

    admech_army.on_battle_round_start(1)
    request = _find_data_psalm_requests(game)[0]
    _choose_benediction(game, request, player_id=admech_player.id, choice_key="CITATION_IN_SAVAGERY")

    profile = _melee_profile()
    attacker_model = cult_unit.models[0]
    cult_unit.round_state.charged_this_round = True

    attack_result = _attack_result_stub()
    attack_info = profile._resolve_attack_count(
        enemy,
        attacker_model,
        attack_result,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(attack_info.num_attacks or 0) == 3
    assert any("Citation in Savagery" in str(v) for v in list(attack_result.attacks_special_modifiers or []))

    wound_result = profile._wound_target_with_tracking(
        enemy,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Citation in Savagery" in str(v) for v in list(wound_result.get("modifiers", []) or []))

    cult_unit.round_state.charged_this_round = False
    attack_result_no_charge = _attack_result_stub()
    attack_info_no_charge = profile._resolve_attack_count(
        enemy,
        attacker_model,
        attack_result_no_charge,
        closest_dist=1.0,
        publish_roll_event=False,
        roll_value=2,
        roll_values=[2],
    )
    assert int(attack_info_no_charge.num_attacks or 0) == 2


def test_data_psalm_stratagem_descriptors_registered():
    expected = {
        "000008565002": ("Incantation of the Iron Soul", "mortal_wound_feel_no_pain"),
        "000008565003": ("Chant of the Remorseless Fist", "melee_wound_bonus"),
        "000008565004": ("Verse of Vengeance", "fight_on_death_after_attacks"),
        "000008565005": ("Tribute of Emphatic Veneration", "battle_shock_then_attacker_hit_penalty_on_fail"),
        "000008565006": ("Litany of the Electromancer", "enemy_units_within_range_mortal_wounds"),
        "000008565007": ("Luminescent Blessing", "invulnerable_save"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.stratagem_id == stratagem_id


def test_chant_of_the_remorseless_fist_adds_melee_wound_bonus():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cult = _make_unit(
        "Fulgurite Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Intercessors", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(enemy)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "FIGHT_PHASE")
    start_cp = int(p1.command_points or 0)
    assert p1.stratagems.use(
        "CHANT OF THE REMORSELESS FIST",
        unit=cult,
        phase_name="Fight phase",
    )
    assert int(p1.command_points or 0) == start_cp - 1

    wound_result = _melee_profile()._wound_target_with_tracking(
        enemy,
        cult.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound")) is True
    assert any("CHANT OF THE REMORSELESS FIST" in str(mod).upper() for mod in list(wound_result.get("modifiers", []) or []))


def test_incantation_of_the_iron_soul_queues_and_grants_mortal_fnp():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    cult = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(enemy)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p2, "SHOOTING_PHASE")
    game.event_system.publish(
        "mortal_wound_allocated",
        target_unit=cult,
        attacker_unit=enemy,
        target_model=cult.models[0],
        phase_name="Shooting phase",
    )
    pending = _pending_by_name(p1.stratagems, "INCANTATION OF THE IRON SOUL")
    assert pending is not None
    assert pending.get("target_unit") is cult

    start_cp = int(p1.command_points or 0)
    assert p1.stratagems.use(
        "INCANTATION OF THE IRON SOUL",
        unit=cult,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert int(p1.command_points or 0) == start_cp - 1
    assert (4, "against mortal wounds") in list(cult.has_feel_no_pain(target_model=cult.models[0]) or [])

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(cult.has_feel_no_pain(target_model=cult.models[0]) or []) == []


def test_litany_of_the_electromancer_deals_mortal_wounds_to_nearby_enemy_units():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cult = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS", "ELECTRO-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, enemy_near, 14.0, 10.0)
    _place_unit(game, enemy_far, 25.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "SHOOTING_PHASE")
    start_cp = int(p1.command_points or 0)
    with patch("warhammer40k_ai.rules.stratagems_adeptus_mechanicus.dice_module.get_roll", side_effect=[4, 2]):
        assert p1.stratagems.use(
            "LITANY OF THE ELECTROMANCER",
            unit=cult,
            phase_name="Shooting phase",
        )
    assert int(p1.command_points or 0) == start_cp - 1
    assert int(enemy_near.models[0].wounds or 0) == 1
    assert int(enemy_far.models[0].wounds or 0) == 3


def test_luminescent_blessing_queues_and_grants_invulnerable_save():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    cult = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(attacker)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p2, "SHOOTING_PHASE")
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[cult])
    pending = _pending_by_name(p1.stratagems, "LUMINESCENT BLESSING")
    assert pending is not None
    assert cult in list(pending.get("candidates") or [])

    start_cp = int(p1.command_points or 0)
    assert p1.stratagems.use(
        "LUMINESCENT BLESSING",
        unit=cult,
        attacking_unit=attacker,
        target_units=[cult],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert int(p1.command_points or 0) == start_cp - 1
    entries = list(cult.special_rules.get("defensive_invuln_overrides", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 4
        and str(entry.get("expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
        for entry in entries
        if isinstance(entry, dict)
    )

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    entries_after = list(cult.special_rules.get("defensive_invuln_overrides", []) or [])
    assert all(
        str(entry.get("source", "") or "").strip().upper() != "LUMINESCENT BLESSING"
        for entry in entries_after
        if isinstance(entry, dict)
    )


def test_tribute_of_emphatic_veneration_applies_hit_penalty_on_failed_battleshock():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    cult = _make_unit(
        "Fulgurite Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(enemy)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    def _fail_test(_turn):
        game.event_system.publish("battle_shock_test_resolved", unit=enemy, passed=False)

    enemy.take_battle_shock_test = _fail_test

    _phase_start(game, p1, "MOVEMENT_PHASE")
    start_cp = int(p1.command_points or 0)
    assert p1.stratagems.use(
        "TRIBUTE OF EMPHATIC VENERATION",
        unit=cult,
        enemy_unit=enemy,
        phase_name="Movement phase",
    )
    assert int(p1.command_points or 0) == start_cp - 1

    hit_result = _ranged_profile()._hit_target_with_tracking(
        cult,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit")) is False
    assert any("TRIBUTE OF EMPHATIC VENERATION" in str(mod).upper() for mod in list(hit_result.get("modifiers", []) or []))

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    expired_result = _ranged_profile()._hit_target_with_tracking(
        cult,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(expired_result.get("hit")) is True


def test_verse_of_vengeance_queues_and_grants_fight_on_death():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    cult = _make_unit(
        "Corpuscarii Electro-priests",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(cult)
    enemy_army.add_unit(enemy)
    _place_unit(game, cult, 10.0, 10.0)
    _place_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p2, "FIGHT_PHASE")
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[cult])
    pending = _pending_by_name(p1.stratagems, "VERSE OF VENGEANCE")
    assert pending is not None
    assert cult in list(pending.get("candidates") or [])

    start_cp = int(p1.command_points or 0)
    assert p1.stratagems.use(
        "VERSE OF VENGEANCE",
        unit=cult,
        attacking_unit=enemy,
        target_units=[cult],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert int(p1.command_points or 0) == start_cp - 1

    rule = cult.get_melee_fight_on_death_after_attacks_rule(model=cult.models[0])
    assert rule == {"threshold": 4, "source": "VERSE OF VENGEANCE"}

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    _phase_start(game, p1, "COMMAND_PHASE")
    assert cult.get_melee_fight_on_death_after_attacks_rule(model=cult.models[0]) is None
