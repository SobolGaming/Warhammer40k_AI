from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


class _Ability:
    def __init__(self, name: str, description: str = "", ability_type: str = "") -> None:
        self.name = name
        self.description = description
        self.type = ability_type


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Astra Militarum",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        move: int = 6,
        save: int = 4,
        toughness: int = 4,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ASTRA MILITARUM"] if faction_name == "Astra Militarum" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
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
    faction_name: str = "Astra Militarum",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    move: int = 6,
    save: int = 4,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            move=move,
            save=save,
            toughness=toughness,
        )
    )
    unit.possible_abilities = list(abilities or [])
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_phase = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    am_army = Army.with_detachment("Astra Militarum", "Siege Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=PlayerControl.LOCAL, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.current_player_idx = 0
    am_player.command_points = 10
    enemy_player.command_points = 10
    return game, am_player, enemy_player, am_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _alive_models(unit: Unit) -> list:
    alive = []
    for model in list(getattr(unit, "models", []) or []):
        alive_attr = getattr(model, "is_alive", True)
        is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if is_alive:
            alive.append(model)
    return alive


def _find_model_selection_request(game: Game, *, unit: Unit, destroy_remaining: int | None = None):
    target_unit_id = str(get_entity_id(unit) or "")
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_SELECT_TARGET_MODEL:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("selection_kind", "") or "") != "worthless_chattel_destroy":
            continue
        if str(context.get("target_unit_id", "") or "") != target_unit_id:
            continue
        if destroy_remaining is not None and int(context.get("destroy_remaining", 0) or 0) != int(destroy_remaining):
            continue
        return request
    return None


def _ranged_wargear(
    name: str = "Siege Lasgun",
    *,
    range_value: str = "24",
    attacks: str = "1",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": str(range_value),
            "A": str(attacks),
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _melee_profile(name: str = "Enemy Blade") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": str(name),
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_siege_regiment_stratagem_descriptors_registered():
    expected = {
        "000009858002": ("Trench Fighters", "fight_on_death_after_attacks"),
        "000009858003": ("Over the Top", "move_move_move_order_to_any_number_of_infantry_regiment_units_ignore_range"),
        "000009858004": ("Flare Burst", "ranged_hit_reroll_within_12_visible"),
        "000009858005": (
            "Callous Sacrifice",
            "ignore_engagement_for_ranged_targeting_and_self_destroy_after_damaging_engaged_enemy",
        ),
        "000009858006": ("Furious Fusillade", "ranged_attacks_bonus_within_half_range"),
        "000009858007": ("Minefield", "charge_end_roll_per_enemy_model_mortals_capped"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_callous_sacrifice_ignores_engagement_for_targeting_and_queues_model_destruction_decisions():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    platoon = _make_unit(
        "Siege Platoon",
        keywords=["INFANTRY", "PLATOON", "REGIMENT"],
        model_count=3,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
        model_count=2,
    )
    am_army.add_unit(platoon)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, platoon, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])
    game.map.is_within_engagement_range = lambda *_args, **_kwargs: True

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("CALLOUS SACRIFICE", unit=platoon, phase_name="Shooting phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert bool(platoon.special_rules.get("siege_regiment_callous_sacrifice_active"))
    assert bool(platoon._ignore_engagement_for_ranged_targeting_active()) is True

    with patch("warhammer40k_ai.rules.stratagems_astra_militarum.get_roll", side_effect=[4, 4]):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=platoon,
            damage_by_target_while_engaged={enemy: 2},
        )

    first_request = _find_model_selection_request(game, unit=platoon, destroy_remaining=2)
    assert first_request is not None
    first_apply = resolve_decision_command(
        game,
        first_request,
        first_request.options[0].option_id,
        player_id=am_player.id,
    )
    assert bool(getattr(first_apply, "ok", False)) is True

    second_request = _find_model_selection_request(game, unit=platoon, destroy_remaining=1)
    assert second_request is not None
    second_apply = resolve_decision_command(
        game,
        second_request,
        second_request.options[0].option_id,
        player_id=am_player.id,
    )
    assert bool(getattr(second_apply, "ok", False)) is True
    assert len(_alive_models(platoon)) == 1

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert bool(platoon._ignore_engagement_for_ranged_targeting_active()) is False


def test_flare_burst_rerolls_hits_within_12_and_cleans_up():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    character = _make_unit(
        "Siege Commander",
        keywords=["INFANTRY", "CHARACTER"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    am_army.add_unit(character)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, character, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])
    weapon = _ranged_wargear(name="Signal Pistol")
    profile = weapon.profiles["default"]

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("FLARE BURST", unit=character, phase_name="Shooting phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            character.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 4
    full_reasons = [str(reason or "") for reason in list(hit_result.get("reroll_full_reasons", []) or [])]
    assert any("FLARE BURST" in reason.upper() for reason in full_reasons)

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_after_cleanup = profile._hit_target_with_tracking(
            enemy,
            character.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert hit_after_cleanup.get("reroll") is None
    assert not list(hit_after_cleanup.get("reroll_full_reasons", []) or [])


def test_furious_fusillade_adds_attack_within_half_range_and_cleans_up():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    platoon = _make_unit(
        "Siege Platoon",
        keywords=["INFANTRY", "PLATOON", "REGIMENT"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
    )
    am_army.add_unit(platoon)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, platoon, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])
    weapon = _ranged_wargear(name="Volley Gun", range_value="24", attacks="1")
    profile = weapon.profiles["default"]

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("FURIOUS FUSILLADE", unit=platoon, phase_name="Shooting phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    attack_result = profile.attack(enemy, platoon.models[0], game.map)
    assert attack_result is not None
    assert int(attack_result.attacks_rolled or 0) == 2
    assert any("FURIOUS FUSILLADE" in str(modifier or "").upper() for modifier in list(attack_result.attacks_special_modifiers or []))

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    attack_after_cleanup = profile.attack(enemy, platoon.models[0], game.map)
    assert attack_after_cleanup is not None
    assert int(attack_after_cleanup.attacks_rolled or 0) == 1


def test_minefield_queues_reaction_and_caps_mortal_wounds():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    platoon = _make_unit(
        "Siege Platoon",
        keywords=["INFANTRY", "PLATOON", "REGIMENT"],
    )
    enemy = _make_unit(
        "Charging Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
        model_count=8,
        wounds=1,
    )
    am_army.add_unit(platoon)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, platoon, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    pending = _pending_by_name(am_player.stratagems, "MINEFIELD")
    assert pending is not None

    ok = am_player.stratagems.use("MINEFIELD", unit=platoon, phase_name="Charge phase", dequeue=True)
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert bool(platoon.special_rules.get("siege_regiment_minefield_active"))

    game.map.is_within_engagement_range = lambda *_args, **_kwargs: True
    with patch("warhammer40k_ai.rules.astra_militarum_detachments.get_roll", side_effect=[5] * 8):
        outcomes = am_army.astra_militarum_detachments.siege_regiment_minefield_on_enemy_move_ended(
            enemy,
            action="charge",
            game=game,
            player=am_player,
    )
    assert len(outcomes) == 1
    assert int(outcomes[0].get("mortal_wounds", 0) or 0) == 6

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    with patch("warhammer40k_ai.rules.astra_militarum_detachments.get_roll", side_effect=[5] * 8):
        outcomes_after_cleanup = am_army.astra_militarum_detachments.siege_regiment_minefield_on_enemy_move_ended(
            enemy,
            action="charge",
            game=game,
            player=am_player,
        )
    assert outcomes_after_cleanup == []


def test_over_the_top_extends_move_order_and_allows_continuation_without_extra_capacity():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    officer = _make_unit(
        "Siege Officer",
        keywords=["INFANTRY", "OFFICER", "CHARACTER"],
        abilities=[
            _Ability("Voice of Command"),
            _Ability("Orders", "This model can issue 1 Order to REGIMENT units within 6\"."),
        ],
    )
    regiment_a = _make_unit("Regiment A", keywords=["INFANTRY", "REGIMENT"])
    regiment_b = _make_unit("Regiment B", keywords=["INFANTRY", "REGIMENT"])
    am_army.add_unit(officer)
    am_army.add_unit(regiment_a)
    am_army.add_unit(regiment_b)
    _deploy_unit(game, officer, 10.0, 10.0)
    _deploy_unit(game, regiment_a, 24.0, 10.0)
    _deploy_unit(game, regiment_b, 34.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(am_player.stratagems, "OVER THE TOP")
    assert pending is not None

    ok = am_player.stratagems.use("OVER THE TOP", officer_unit=officer, phase_name="Command phase", dequeue=True)
    assert ok is True
    assert int(am_player.command_points or 0) == 8
    assert bool(officer.special_rules.get("siege_regiment_over_the_top_active"))

    voice = am_army.voice_of_command
    eligible_before = list(voice.get_eligible_targets(officer, game=game, order_key=ORDER_MOVE.key) or [])
    assert regiment_a in eligible_before
    assert regiment_b in eligible_before

    first_issue = voice.issue_order(game, officer, regiment_a, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert first_issue is True
    assert int(voice.orders_remaining(officer, 1) or 0) == 0
    assert bool(voice._officer_has_siege_over_the_top_pending_targets(officer, 1)) is True
    assert [order.key for order in list(voice.get_available_orders(officer) or [])] == [ORDER_MOVE.key]

    second_issue = voice.issue_order(game, officer, regiment_b, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
    assert second_issue is True
    assert int(voice.orders_remaining(officer, 1) or 0) == 0
    assert bool(voice._officer_has_siege_over_the_top_pending_targets(officer, 1)) is False
    assert str(regiment_a.special_rules.get("voice_of_command_order_key", "") or "") == ORDER_MOVE.key
    assert str(regiment_b.special_rules.get("voice_of_command_order_key", "") or "") == ORDER_MOVE.key

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    assert not bool(officer.special_rules.get("siege_regiment_over_the_top_active"))


def test_trench_fighters_reaction_grants_regiment_fight_on_death_and_cleans_up():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    target = _make_unit(
        "Siege Infantry",
        keywords=["INFANTRY", "REGIMENT"],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
        keywords=["INFANTRY"],
        model_count=2,
    )
    am_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(am_player.stratagems, "TRENCH FIGHTERS")
    assert pending is not None

    ok = am_player.stratagems.use(
        "TRENCH FIGHTERS",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    rule = target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 2
    assert "TRENCH FIGHTERS" in str(rule.get("source", "")).upper()

    model = target.models[0]
    target.round_state.fought_this_phase = False
    target._last_destroyed_by_weapon_profile = _melee_profile()
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=2):
        model._wounds = 0
        target._handle_model_destroyed(model, game.map)

    pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0]) is None
