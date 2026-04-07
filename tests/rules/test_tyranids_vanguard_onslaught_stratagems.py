from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Vanguard Onslaught")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.turn = 1
    tyr_player.command_points = 5
    enemy_player.command_points = 5
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _reserve_unit(unit: Unit, *, status: str = "strategic_reserves") -> None:
    unit.deployed = False
    unit.reserve_status = status
    unit.embarked_in = None
    unit._started_in_reserves = True


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, ability: str | None = None, reactive_move_kind: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(context.get("ability", "") or "") != str(ability):
            continue
        if reactive_move_kind is not None and str(context.get("reactive_move_kind", "") or "") != str(reactive_move_kind):
            continue
        return request
    return None


def _make_profile(*, weapon_name: str, is_melee: bool, skill: str = "4+", strength: str = "4") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": weapon_name,
            "is_melee": staticmethod(lambda: bool(is_melee)),
            "is_ranged": staticmethod(lambda: not bool(is_melee)),
        },
    )()
    return WargearProfile(
        weapon_name,
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _option_for_target(request, *, target_unit):
    target_id = str(getattr(target_unit, "id", "") or getattr(target_unit, "_id", "") or "")
    if not target_id:
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


def _option_for_selected_units(request, *, units: list[Unit]):
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    wanted_ids = frozenset(str(get_entity_id(unit) or "") for unit in list(units) if str(get_entity_id(unit) or ""))
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        selected_ids = frozenset(
            str(value or "").strip()
            for value in list(payload.get("selected_unit_ids", []) or [])
            if str(value or "").strip()
        )
        if selected_ids == wanted_ids:
            return option
    return None


def test_vanguard_onslaught_stratagem_descriptors_registered():
    expected = {
        "000008418002": ("Surprise Assault", "grant_hit_bonus_and_battle_shock_conditional_wound_bonus_against_selected_enemy", 1),
        "000008418003": ("Assassin Beasts", "grant_precision_to_melee_weapons", 1),
        "000008418004": ("Seeded Broods", "increase_strategic_reserves_setup_turn", 1),
        "000008418005": ("Hypersensory Scillia", "reactive_normal_move_up_to_6", 2),
        "000008418006": ("Unseen Lurkers", "restrict_ranged_targeting_to_18_or_6_lone_operative", 1),
        "000008418007": ("Invisible Hunter", "enter_strategic_reserves", 1),
    }
    for stratagem_id, (name, effect, cp_cost) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert desc.name == name
        assert desc.effect == effect
        assert int(desc.cp_cost or 0) == cp_cost


def test_surprise_assault_applies_hit_and_wound_bonuses_against_selected_enemy():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Lictor",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    enemy.take_battle_shock_test = lambda _turn: setattr(enemy, "battle_shocked", True)
    enemy.is_battle_shocked = lambda: True

    profile = _make_profile(weapon_name="Deathspitter", is_melee=False, skill="4+", strength="4")
    before_hit = profile._hit_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    before_wound = profile._wound_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(before_hit.get("hit", False)) is False
    assert bool(before_wound.get("wound", False)) is False

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "SURPRISE ASSAULT",
        unit=attacker,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 4

    after_hit = profile._hit_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    after_wound = profile._wound_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_hit.get("hit", False)) is True
    assert bool(after_wound.get("wound", False)) is True


def test_surprise_assault_queues_choose_quarry_and_resolves_selected_enemy():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Genestealers",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_a = _make_unit(
        "Enemy Alpha",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_b = _make_unit(
        "Enemy Beta",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 18.0, 10.0)
    _deploy_unit(game, enemy_b, 18.0, 14.0)
    game.rebuild_entity_registry()

    enemy_a.take_battle_shock_test = lambda _turn: setattr(enemy_a, "battle_shocked", True)
    enemy_a.is_battle_shocked = lambda: True
    enemy_b.take_battle_shock_test = lambda _turn: setattr(enemy_b, "battle_shocked", False)
    enemy_b.is_battle_shocked = lambda: False

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[enemy_a, enemy_b])
    pending = _pending_by_name(tyr_player.stratagems, "SURPRISE ASSAULT")
    assert pending is not None

    ok = tyr_player.stratagems.use(
        "SURPRISE ASSAULT",
        unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 4

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tyranids_vanguard_surprise_assault")
    assert request is not None
    chosen = _option_for_target(request, target_unit=enemy_a)
    assert chosen is not None

    resolved = resolve_decision_command(game, request, chosen.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    mgr = tyr_army.tyranids_detachments
    hit_bonus, _ = mgr.vanguard_surprise_assault_hit_bonus(attacker.models[0], target_unit=enemy_a, game=game)
    wound_bonus, _ = mgr.vanguard_surprise_assault_wound_bonus(attacker.models[0], target_unit=enemy_a, game=game)
    off_target_bonus, _ = mgr.vanguard_surprise_assault_hit_bonus(attacker.models[0], target_unit=enemy_b, game=game)
    assert int(hit_bonus or 0) == 1
    assert int(wound_bonus or 0) == 1
    assert int(off_target_bonus or 0) == 0


def test_assassin_beasts_grants_precision_to_melee_weapons():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Genestealers",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker.is_eligible_to_fight = lambda _game_map: True
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    melee_profile = _make_profile(weapon_name="Scything Talons", is_melee=True)
    before_attack = {}
    melee_profile._hit_target_with_tracking(enemy, attacker.models[0], before_attack, roll_value=4, allow_rerolls=False, log_roll=False)
    assert bool(before_attack.get("bonus_precision", False)) is False

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "ASSASSIN BEASTS",
        unit=attacker,
        phase_name="Fight phase",
    )
    assert ok is True

    during_attack = {}
    melee_profile._hit_target_with_tracking(enemy, attacker.models[0], during_attack, roll_value=4, allow_rerolls=False, log_roll=False)
    assert bool(during_attack.get("bonus_precision", False)) is True


def test_seeded_broods_queues_choose_quarry_and_grants_turn_one_reserves_arrival():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    reserve_a = _make_unit(
        "Lictors Alpha",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    reserve_b = _make_unit(
        "Lictors Beta",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    reserve_c = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(reserve_a)
    tyr_army.add_unit(reserve_b)
    tyr_army.add_unit(reserve_c)
    _reserve_unit(reserve_a)
    _reserve_unit(reserve_b)
    _reserve_unit(reserve_c)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("SEEDED BROODS", phase_name="Movement phase")
    assert ok is True
    assert int(tyr_player.command_points or 0) == 4

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tyranids_vanguard_seeded_broods")
    assert request is not None
    chosen = _option_for_selected_units(request, units=[reserve_a, reserve_b])
    assert chosen is not None

    resolved = resolve_decision_command(game, request, chosen.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    assert reserve_a.can_arrive_from_reserves(1) is True
    assert reserve_b.can_arrive_from_reserves(1) is True
    assert reserve_c.can_arrive_from_reserves(1) is False


def test_hypersensory_scillia_queues_choose_quarry_and_creates_reactive_move_requests():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    vanguard_a = _make_unit(
        "Lictors Alpha",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    vanguard_b = _make_unit(
        "Lictors Beta",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    infantry = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(vanguard_a)
    tyr_army.add_unit(vanguard_b)
    tyr_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vanguard_a, 10.0, 10.0)
    _deploy_unit(game, vanguard_b, 14.0, 10.0)
    _deploy_unit(game, infantry, 12.0, 14.0)
    _deploy_unit(game, enemy, 19.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(tyr_player.stratagems, "HYPERSENSORY SCILLIA")
    assert pending is not None

    ok = tyr_player.stratagems.use(
        "HYPERSENSORY SCILLIA",
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 3

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tyranids_vanguard_hypersensory_scillia")
    assert request is not None
    chosen = _option_for_selected_units(request, units=[vanguard_a, vanguard_b])
    assert chosen is not None

    resolved = resolve_decision_command(game, request, chosen.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    move_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
        and str(dict(getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "tyranids_hypersensory_scillia"
    ]
    assert len(move_requests) == 2
    for request in move_requests:
        ctx = dict(getattr(request, "context", {}) or {})
        assert str(ctx.get("reactive_move_source", "") or "").strip().upper() == "HYPERSENSORY SCILLIA"
        assert int(ctx.get("max_distance", 0) or 0) == 6


def test_unseen_lurkers_applies_ranged_targeting_cap_and_lone_operative_override():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Lictor",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[defender])
    pending = _pending_by_name(tyr_player.stratagems, "UNSEEN LURKERS")
    assert pending is not None

    ok = tyr_player.stratagems.use(
        "UNSEEN LURKERS",
        unit=defender,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    distance, sources = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert float(distance or 0.0) == 18.0
    assert any("UNSEEN LURKERS" in str(source or "").upper() for source in list(sources or []))

    defender.has_lone_operative = lambda: True
    distance_with_lone_operative, _sources = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert float(distance_with_lone_operative or 0.0) == 6.0


def test_invisible_hunter_queues_and_moves_two_vanguard_invader_units_to_strategic_reserves():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    vanguard_a = _make_unit(
        "Genestealers Alpha",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    vanguard_b = _make_unit(
        "Genestealers Beta",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(vanguard_a)
    tyr_army.add_unit(vanguard_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vanguard_a, 10.0, 10.0)
    _deploy_unit(game, vanguard_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(tyr_player.stratagems, "INVISIBLE HUNTER")
    assert pending is not None
    assert int(pending.get("max_units", 0) or 0) == 2

    ok = tyr_player.stratagems.use(
        "INVISIBLE HUNTER",
        units=[vanguard_a, vanguard_b],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 4
    assert str(getattr(vanguard_a, "reserve_status", "") or "") == "strategic_reserves"
    assert str(getattr(vanguard_b, "reserve_status", "") or "") == "strategic_reserves"
    assert vanguard_a not in list(getattr(game.map, "units", []) or [])
    assert vanguard_b not in list(getattr(game.map, "units", []) or [])


def test_invisible_hunter_rejects_mixed_vanguard_and_non_vanguard_infantry_selection():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    vanguard = _make_unit(
        "Lictors",
        keywords=["INFANTRY", "VANGUARD INVADER", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    infantry = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(vanguard)
    tyr_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vanguard, 10.0, 10.0)
    _deploy_unit(game, infantry, 16.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    blocked = tyr_player.stratagems.use(
        "INVISIBLE HUNTER",
        units=[vanguard, infantry],
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 5
    assert str(getattr(vanguard, "reserve_status", "") or "") == "deployed"
    assert str(getattr(infantry, "reserve_status", "") or "") == "deployed"
