from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


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
        move: int = 6,
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
                "M": str(int(move)),
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
        self.transport = ""
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
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Unforgiven Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

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


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems, *, clear: bool = False) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=clear) or [])
    }


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _melee_wargear(name: str = "Power Sword") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _make_profile(*, is_melee: bool, skill: str = "3+", strength: str = "4", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_unforgiven_task_force_stratagem_descriptors_registered():
    expected = {
        "000008389005": ("Fire Discipline", "grant_ranged_assault_heavy_ignores_cover"),
        "000008389006": ("Grim Retribution", "reactive_shooting_against_attacker_after_losing_models"),
        "000008389004": ("Intractable", "eligible_to_shoot_and_charge_after_fall_back"),
        "000008389007": ("Unbreakable Lines", "defensive_wound_penalty"),
        "000008389003": ("Unforgiven Fury", "phase_lethal_hits_and_conditional_crit_hit_threshold"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_unforgiven_phase_start_reactions_queue_shooting_and_fight_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    shooters = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    fighters = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    shooters.models[0].wargear = [_ranged_wargear()]
    fighters.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(shooters)
    sm_army.add_unit(fighters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooters, 10.0, 10.0)
    _deploy_unit(game, fighters, 12.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sm_player.stratagems, clear=True) == {"FIRE DISCIPLINE", "UNFORGIVEN FURY"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sm_player.stratagems, clear=True) == {"UNFORGIVEN FURY"}


def test_fire_discipline_grants_ranged_keywords_until_end_of_phase():
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
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "FIRE DISCIPLINE")
    assert pending is not None

    ok = sm_player.stratagems.use("FIRE DISCIPLINE", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    keywords = {
        str(item.get("keyword", "") or "").strip().upper()
        for item in list(bonuses or [])
        if str(item.get("attack_type", "") or "").strip().lower() == "ranged"
    }
    assert keywords == {"ASSAULT", "HEAVY", "IGNORES COVER"}

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") == []


def test_unforgiven_fury_grants_phase_keywords_and_conditional_critical_hits():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    shocked = _make_unit(
        "Shock Victims",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear(), _melee_wargear()]
    sm_army.add_unit(intercessors)
    sm_army.add_unit(shocked)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, shocked, 12.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    shocked.apply_status_effect(BattleShockEffect(1))

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("UNFORGIVEN FURY", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    ranged_keywords = {
        str(item.get("keyword", "") or "").strip().upper()
        for item in list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or [])
        if str(item.get("attack_type", "") or "").strip().lower() == "ranged"
    }
    assert ranged_keywords == {"LETHAL HITS"}

    hit = _make_profile(is_melee=False)._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    game2, sm_player2, enemy_player2, sm_army2, enemy_army2 = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy2 = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bladeguard.models[0].wargear = [_melee_wargear()]
    sm_army2.add_unit(bladeguard)
    enemy_army2.add_unit(enemy2)
    _deploy_unit(game2, bladeguard, 10.0, 10.0)
    _deploy_unit(game2, enemy2, 12.0, 10.0)
    game2.rebuild_entity_registry()

    _set_phase(game2, enemy_player2, "FIGHT_PHASE", 1)
    ok = sm_player2.stratagems.use("UNFORGIVEN FURY", unit=bladeguard, dequeue=True)
    assert ok
    melee_keywords = {
        str(item.get("keyword", "") or "").strip().upper()
        for item in list(bladeguard.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or [])
        if str(item.get("attack_type", "") or "").strip().lower() == "melee"
    }
    assert melee_keywords == {"LETHAL HITS"}
    special_rules = dict(getattr(bladeguard, "special_rules", {}) or {})
    assert "space_marines_unforgiven_fury_crit_hit_threshold" not in special_rules


def test_grim_retribution_queues_after_model_loss_and_creates_reactive_shooting_request():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[intercessors])
    intercessors.models[0].take_damage(4, game_map=game.map)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)

    pending = _pending_by_name(sm_player.stratagems, "GRIM RETRIBUTION")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [intercessors]

    ok = sm_player.stratagems.use(
        "GRIM RETRIBUTION",
        unit=intercessors,
        enemy_unit=enemy,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert bool(context.get("out_of_phase", False)) is True
    assert bool(context.get("grim_retribution_flow", False)) is True
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_intractable_queues_after_fall_back_and_expires_at_end_of_turn():
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
    bolt_rifle = _ranged_wargear()
    intercessors.models[0].wargear = [bolt_rifle]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    intercessors.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=intercessors, action="fall_back")
    assert _pending_by_name(sm_player.stratagems, "INTRACTABLE") is not None

    ok = sm_player.stratagems.use(
        "INTRACTABLE",
        unit=intercessors,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert intercessors.can_shoot_after_fall_back(bolt_rifle.profiles["default"], model=intercessors.models[0]) is True
    assert intercessors.can_charge_after_fall_back() is True

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.can_shoot_after_fall_back(bolt_rifle.profiles["default"], model=intercessors.models[0]) is False
    assert intercessors.can_charge_after_fall_back() is False


def test_unbreakable_lines_queues_after_enemy_charge_and_applies_wound_penalty():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defender = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    far_defender = _make_unit(
        "Hellblasters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(defender)
    sm_army.add_unit(far_defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, far_defender, 24.0, 24.0)
    _deploy_unit(game, attacker, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=attacker, action="charge")
    pending = _pending_by_name(sm_player.stratagems, "UNBREAKABLE LINES")
    assert pending is not None
    candidates = list(pending.get("candidates") or [])
    assert defender in candidates
    assert far_defender not in candidates

    ok = sm_player.stratagems.use(
        "UNBREAKABLE LINES",
        unit=defender,
        attacking_unit=attacker,
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 8

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    wound_result = _make_profile(is_melee=True)._wound_target_with_tracking(
        defender,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound")) is False
    assert any("UNBREAKABLE LINES" in str(item) for item in list(wound_result.get("modifiers", []) or []))
