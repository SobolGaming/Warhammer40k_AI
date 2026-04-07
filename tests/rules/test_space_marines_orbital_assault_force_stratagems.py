from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


AUTO_SENSE_NAME = "Auto\u2011Sense Coordination"


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        transport: str = "",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            transport=transport,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Orbital Assault Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _normalize_name(name: str) -> str:
    text = str(name or "").strip().upper()
    for hyphen in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(hyphen, "-")
    return text


def _pending_by_name(stratagems, name: str):
    target = _normalize_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {
        _normalize_name(str(item.get("stratagem", "") or ""))
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _make_profile(
    *,
    name: str = "Bolt Rifle",
    is_melee: bool = False,
    skill: str = "3+",
    strength: str = "4",
):
    wargear = Wargear(
        {
            "name": str(name),
            "type": "Melee" if is_melee else "Ranged",
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return wargear.profiles["default"]


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_orbital_assault_force_stratagem_descriptors_registered():
    expected = {
        "000010681002": ("Suppression Strafing", "visible_enemy_within_18_forced_battleshock_and_suppressed"),
        "000010681003": ("Tactical Decapitation", "grant_precision_and_character_target_hit_bonus"),
        "000010681004": ("Shock Onslaught", "increase_pile_in_and_consolidate_distance"),
        "000010681005": (AUTO_SENSE_NAME, "choose_lethal_hits_or_sustained_hits_1_if_drop_pod_or_within_12"),
        "000010681006": ("Blind Screen", "paired_units_gain_stealth_and_cover"),
        "000010681007": ("Onward For The Emperor", "end_of_opponent_fight_embark"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        assert by_id is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect

    by_name = get_stratagem_tool_descriptor(name="AUTO-SENSE COORDINATION")
    assert by_name is not None
    assert by_name.name == AUTO_SENSE_NAME
    assert by_name.effect == "choose_lethal_hits_or_sustained_hits_1_if_drop_pod_or_within_12"


def test_orbital_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    smoke_vehicle = _make_unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT", "SMOKE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        transport="Transport Capacity 6",
    )
    infantry = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    smoke_vehicle.transport_capacity = 6
    smoke_vehicle.transport_required_keywords = set()
    smoke_vehicle.transport_excluded_keywords = set()

    sm_army.add_unit(intercessors)
    sm_army.add_unit(smoke_vehicle)
    sm_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, smoke_vehicle, 14.0, 10.0)
    _deploy_unit(game, infantry, 12.0, 14.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert _pending_names(sm_player.stratagems) == {"SUPPRESSION STRAFING"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"TACTICAL DECAPITATION", "AUTO-SENSE COORDINATION"}

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"TACTICAL DECAPITATION", "AUTO-SENSE COORDINATION", "SHOCK ONSLAUGHT"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[intercessors])
    assert _pending_by_name(sm_player.stratagems, "BLIND SCREEN") is not None

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "ONWARD FOR THE EMPEROR") is not None


def test_suppression_strafing_forces_battleshock_and_applies_suppressed():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    def _force_failed_battle_shock(current_turn=1, *, modifier=0, source=""):
        assert int(current_turn or 0) == 1
        assert int(modifier or 0) == -1
        assert str(source or "").strip().upper() == "SUPPRESSION STRAFING"
        enemy._last_leadership_test_roll = 9
        enemy._last_leadership_test_modified_roll = 8
        enemy._last_leadership_test_passed = False
        game.event_system.publish("battle_shock_test_resolved", unit=enemy, passed=False)

    enemy.force_battle_shock_test = _force_failed_battle_shock

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "SUPPRESSION STRAFING") is not None

    ok = sm_player.stratagems.use(
        "SUPPRESSION STRAFING",
        unit=intercessors,
        enemy_unit=enemy,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    enemy_sr = dict(getattr(enemy, "special_rules", {}) or {})
    assert bool(enemy_sr.get("post_shoot_suppressed_active")) is True

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    profile = _make_profile(is_melee=False, skill="4+")
    hit_result = profile._hit_target_with_tracking(
        intercessors,
        enemy.models[0],
        {"distance_to_target": 8.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("SUPPRESSED" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))


def test_tactical_decapitation_applies_precision_hit_bonus_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Character Unit",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    intercessors.models[0].wargear = [_ranged_wargear()]
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "TACTICAL DECAPITATION") is not None

    ok = sm_player.stratagems.use(
        "TACTICAL DECAPITATION",
        unit=intercessors,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    keyword_bonuses = list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or [])
    assert any(str(item.get("keyword", "") or "").strip().upper() == "PRECISION" for item in keyword_bonuses)

    profile = _make_profile(is_melee=False, skill="4+")
    attack_instance = {"distance_to_target": 6.0}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("TACTICAL DECAPITATION" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))
    assert bool(attack_instance.get("bonus_precision", False)) is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []

    after_attack_instance = {"distance_to_target": 6.0}
    after = profile._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        after_attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("TACTICAL DECAPITATION" in str(modifier).upper() for modifier in list(after.get("modifiers", []) or []))
    assert bool(after_attack_instance.get("bonus_precision", False)) is False


def test_shock_onslaught_sets_six_inch_pile_in_and_consolidate_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "SHOCK ONSLAUGHT") is not None

    ok = sm_player.stratagems.use(
        "SHOCK ONSLAUGHT",
        unit=intercessors,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    sr = dict(getattr(intercessors, "special_rules", {}) or {})
    assert float(sr.get("bearer_unit_pile_in_distance_override", 0.0) or 0.0) == 6.0
    assert float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0) == 6.0

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    cleared = dict(getattr(intercessors, "special_rules", {}) or {})
    assert "bearer_unit_pile_in_distance_override" not in cleared
    assert "stratagem_consolidate_distance_override" not in cleared


def test_auto_sense_coordination_grants_lethal_hits_after_drop_pod_disembark():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    drop_pod = _make_unit(
        "Drop Pod",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    sm_army.add_unit(drop_pod)
    enemy_army.add_unit(enemy)
    intercessors.models[0].wargear = [_ranged_wargear()]
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, drop_pod, 22.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    intercessors.round_state.disembarked_this_round = True
    intercessors.round_state.disembarked_from_transport_id = str(get_entity_id(drop_pod) or "")

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "AUTO-SENSE COORDINATION",
        unit=intercessors,
        choice="LETHAL_HITS",
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    bonuses = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert bool(bonuses.get("lethal_hits", False)) is True
    assert int(bonuses.get("sustained_hits_value", 0) or 0) == 0


def test_auto_sense_coordination_grants_sustained_hits_one_within_twelve():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "AUTO-SENSE COORDINATION",
        unit=intercessors,
        choice="SUSTAINED_HITS_1",
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    bonuses = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert int(bonuses.get("sustained_hits_value", 0) or 0) == 1
    assert bool(bonuses.get("lethal_hits", False)) is False


def test_blind_screen_queues_applies_stealth_and_cover_then_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    smoke_vehicle = _make_unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT", "SMOKE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        transport="Transport Capacity 6",
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    smoke_vehicle.transport_capacity = 6
    smoke_vehicle.transport_required_keywords = set()
    smoke_vehicle.transport_excluded_keywords = set()

    sm_army.add_unit(defenders)
    sm_army.add_unit(smoke_vehicle)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, smoke_vehicle, 14.0, 10.0)
    _deploy_unit(game, enemy, 26.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[defenders])
    assert _pending_by_name(sm_player.stratagems, "BLIND SCREEN") is not None

    ok = sm_player.stratagems.use(
        "BLIND SCREEN",
        unit=defenders,
        support_unit=smoke_vehicle,
        attacking_unit=enemy,
        target_units=[defenders],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert defenders.has_stealth() is True
    assert smoke_vehicle.has_stealth() is True

    profile = _make_profile(is_melee=False)
    attack_instance = {
        "mortal_wound": False,
        "distance_to_target": 16.0,
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
    }
    profile._save_with_tracking(
        defenders.models[0],
        attack_instance,
        ap=-1,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("benefit_of_cover", False)) is True
    assert "BLIND SCREEN" in str(attack_instance.get("benefit_of_cover_source", "")).upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert defenders.has_stealth() is False
    assert smoke_vehicle.has_stealth() is False


def test_onward_for_the_emperor_queues_and_embarks_nearby_infantry():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    infantry = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    transport = _make_unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        transport="Transport Capacity 6",
    )
    transport.transport_capacity = 6
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    sm_army.add_unit(infantry)
    sm_army.add_unit(transport)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, transport, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "ONWARD FOR THE EMPEROR") is not None

    ok = sm_player.stratagems.use(
        "ONWARD FOR THE EMPEROR",
        unit=infantry,
        transport_unit=transport,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert infantry.embarked_in is transport
    assert infantry in list(getattr(transport, "transport_passengers", []) or [])
