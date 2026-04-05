from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
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
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
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
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
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
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    damage: str = "1",
):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    pactbound_army = Army("Chaos Space Marines", "Pactbound Zealots")
    pactbound_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    pactbound_player = Player("Pactbound", control=PlayerControl.REMOTE, army=pactbound_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(pactbound_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    pactbound_player.command_points = 10
    enemy_player.command_points = 10

    pactbound_army.configure_rule_managers(force=True)
    pactbound_player.stratagems.refresh_available()
    _inject_pactbound_stratagems(pactbound_player)
    pactbound_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, pactbound_player, enemy_player, pactbound_army, enemy_army


def _inject_pactbound_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008358002",
            "Eye of the Gods",
            1,
            "Either player's turn",
            "Fight phase",
            "Pactbound Zealots - Epic Deed Stratagem",
        ),
        (
            "000008358003",
            "Eternal Hate",
            1,
            "Either player's turn",
            "Fight phase",
            "Pactbound Zealots - Strategic Ploy Stratagem",
        ),
        (
            "000008358004",
            "Profane Zeal",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Pactbound Zealots - Battle Tactic Stratagem",
        ),
        (
            "000008358005",
            "Skinshift",
            1,
            "Your turn",
            "Command phase",
            "Pactbound Zealots - Epic Deed Stratagem",
        ),
        (
            "000008358006",
            "Torpefying Refrain",
            1,
            "Your turn",
            "Movement phase",
            "Pactbound Zealots - Strategic Ploy Stratagem",
        ),
        (
            "000008358007",
            "Festering Miasma",
            1,
            "Opponent's turn",
            "Shooting phase",
            "Pactbound Zealots - Strategic Ploy Stratagem",
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
                detachment="Pactbound Zealots",
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


def _set_mark(unit: Unit, mark: str) -> None:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["pactbound_zealots_mark"] = str(mark or "").strip().upper()
    sr["pactbound_zealots_mark_source"] = "Marks of Chaos"
    unit.special_rules = sr


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, selection_kind: str = ""):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if selection_kind and str(ctx.get("selection_kind", "") or "") != str(selection_kind):
            continue
        return req
    return None


def _find_option(request, *, model_id: str = ""):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if model_id and str(payload.get("model_id", "") or "") != str(model_id):
            continue
        return opt
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_pactbound_zealots_stratagem_descriptors_registered():
    expected = {
        "000008358002": ("Eye of the Gods", "permanent_characteristic_and_melee_weapon_bonus_after_destroying_enemy_unit"),
        "000008358003": ("Eternal Hate", "fight_on_death_roll"),
        "000008358004": ("Profane Zeal", "wound_reroll_full"),
        "000008358005": ("Skinshift", "heal_and_conditional_return_destroyed_model"),
        "000008358006": (
            "Torpefying Refrain",
            "charge_after_fall_back_and_conditional_shoot_charge_after_advance_or_fall_back",
        ),
        "000008358007": ("Festering Miasma", "grant_stealth_and_conditional_ranged_targeting_cap"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_profane_zeal_queues_applies_wound_rerolls_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _set_mark(unit, "CHAOS UNDIVIDED")
    csm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "Profane Zeal") is not None

    assert csm_player.stratagems.use("PROFANE ZEAL", unit=unit, phase_name="Shooting phase", dequeue=True)
    mods = unit.get_model_wound_reroll_modifiers(unit.models[0], attack_type="ranged", target=enemy)
    assert bool(mods.get("reroll_wound_full", False))
    assert _contains_text(mods.get("reroll_wound_full_reasons", []), "Profane Zeal")

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    after = unit.get_model_wound_reroll_modifiers(unit.models[0], attack_type="ranged", target=enemy)
    assert not bool(after.get("reroll_wound_full", False))


def test_skinshift_heals_three_wounds_and_returns_one_destroyed_model():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
    )
    _set_mark(unit, "TZEENTCH")
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    wounded_model = unit.models[1]
    wounded_model.wounds = 1
    lost_model = unit.models[0]
    unit.remove_model(lost_model)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "Skinshift") is not None

    assert csm_player.stratagems.use(
        "SKINSHIFT",
        unit=unit,
        phase_name="Command phase",
        target_model=wounded_model,
        dequeue=True,
    )
    assert int(getattr(wounded_model, "wounds", 0) or 0) == int(getattr(wounded_model, "_base_wounds", 0) or 0)

    request = _find_request(game, DECISION_ALLOCATE_DAMAGE, selection_kind="bodyguard_return")
    if request is not None:
        option = _find_option(request, model_id=str(get_entity_id(lost_model) or ""))
        assert option is not None
        result = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
        assert bool(getattr(result, "ok", False))
    assert len(unit.models) == 3
    assert len(unit.models_lost) == 0


def test_eye_of_the_gods_queues_after_destroying_enemy_and_permanently_buffs_character():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=4,
        move=6,
        toughness=4,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=enemy, last_model=enemy.models[0], destroyed_by_unit=source)
    pending = _pending_by_name(csm_player.stratagems, "Eye of the Gods")
    assert pending is not None

    assert csm_player.stratagems.use("EYE OF THE GODS", unit=source, phase_name="Fight phase", dequeue=True)
    model = source.models[0]
    assert source.get_effective_model_characteristic(model, "movement") == 7
    assert source.get_effective_model_characteristic(model, "toughness") == 5
    assert int(getattr(model, "wounds", 0) or 0) == 5

    mgr = source.get_parent_army().chaos_space_marines_detachments
    attacks_bonus, attack_source = mgr.pactbound_eye_of_the_gods_melee_attacks_bonus(model, weapon_profile=_make_profile(melee=True))
    strength_bonus, strength_source = mgr.pactbound_eye_of_the_gods_melee_strength_bonus(model, weapon_profile=_make_profile(melee=True))
    damage_bonus, damage_source = mgr.pactbound_eye_of_the_gods_melee_damage_bonus(model, weapon_profile=_make_profile(melee=True))
    assert int(attacks_bonus or 0) == 1
    assert int(strength_bonus or 0) == 1
    assert int(damage_bonus or 0) == 1
    assert str(attack_source or "").strip().upper() == "EYE OF THE GODS"
    assert str(strength_source or "").strip().upper() == "EYE OF THE GODS"
    assert str(damage_source or "").strip().upper() == "EYE OF THE GODS"


def test_festering_miasma_queues_grants_stealth_and_nurgle_targeting_cap_then_cleans_up():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _set_mark(unit, "NURGLE")
    csm_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 40.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[unit])
    assert _pending_by_name(csm_player.stratagems, "Festering Miasma") is not None

    assert csm_player.stratagems.use(
        "FESTERING MIASMA",
        unit=unit,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert bool(unit.has_stealth())
    distance, sources = unit.get_ranged_targeting_restriction(game_map=game.map)
    assert float(distance or 0.0) == 18.0
    assert _contains_text(sources, "Festering Miasma")

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert not bool(unit.has_stealth())
    distance_after, sources_after = unit.get_ranged_targeting_restriction(game_map=game.map)
    assert distance_after is None
    assert not _contains_text(sources_after, "Festering Miasma")


def test_torpefying_refrain_grants_slaanesh_fall_back_and_advance_mobility_until_turn_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    _set_mark(unit, "SLAANESH")
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    ranged_profile = _make_profile(melee=False)
    unit.round_state.fell_back_this_round = True
    unit.round_state.advanced_this_round = False
    assert unit.can_shoot_after_fall_back(ranged_profile) is False
    assert unit.can_charge_after_fall_back() is False

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "Torpefying Refrain") is not None
    assert csm_player.stratagems.use("TORPEFYING REFRAIN", unit=unit, phase_name="Movement phase", dequeue=True)

    unit.round_state.fell_back_this_round = True
    unit.round_state.advanced_this_round = False
    assert unit.can_shoot_after_fall_back(ranged_profile) is True
    assert unit.can_charge_after_fall_back() is True

    unit.round_state.fell_back_this_round = False
    unit.round_state.advanced_this_round = True
    assert unit.can_charge_after_advance() is True

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)

    unit.round_state.fell_back_this_round = True
    unit.round_state.advanced_this_round = False
    assert unit.can_shoot_after_fall_back(ranged_profile) is False
    assert unit.can_charge_after_fall_back() is False


def test_eternal_hate_queues_sets_khorne_threshold_three_and_cleans_up():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _set_mark(unit, "KHORNE")
    csm_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[unit])
    assert _pending_by_name(csm_player.stratagems, "Eternal Hate") is not None

    assert csm_player.stratagems.use(
        "ETERNAL HATE",
        unit=unit,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )
    rule = unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 3
    assert str(rule.get("source", "") or "").strip().upper() == "ETERNAL HATE"

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0]) is None
