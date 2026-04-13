from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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


_WARPSTRIKE_SPECS = (
    {
        "id": "000010740002",
        "name": "Empyric Dislocation",
        "cp_cost": 1,
        "turn": "Either player's turn",
        "phase": "Shooting or Fight phase",
        "type": "Warpstrike Champions - Battle Tactic Stratagem",
        "description": (
            "<b>WHEN:</b> Your opponent's Shooting phase or the Fight phase, just after an enemy unit has "
            "selected its targets.<br><br><b>TARGET:</b> One <span class=\"kwb\">HERETIC</span> "
            "<span class=\"kwb\">ASTARTES</span> unit from your army (excluding Damned units) that was "
            "selected as the target of one or more of the attacking unit's attacks.<br><br><b>EFFECT:</b> "
            "Until the attacking unit has finished making its attacks, each time an attack targets your "
            "unit, worsen the Armour Penetration characteristic of that attack by 1.<br><br>"
            "<b>RESTRICTIONS:</b> You cannot target the same unit with the Empyric Dislocation and Armour "
            "of Corruption Stratagems in the same phase."
        ),
    },
    {
        "id": "000010740003",
        "name": "Armour of Corruption",
        "cp_cost": 2,
        "turn": "Opponent's turn",
        "phase": "Fight phase",
        "type": "Warpstrike Champions - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Fight phase, just after an enemy unit has selected its targets.<br><br>"
            "<b>TARGET:</b> One Heretic Astartes Terminator, Obliterators or Mutilators unit from your "
            "army that was selected as the target of one or more of the attacking unit's attacks.<br><br>"
            "<b>EFFECT:</b> Until the end of the turn, each time an attack is allocated to a model in your "
            "unit, subtract 1 from the Damage characteristic of that attack.<br><br><b>RESTRICTIONS:</b> "
            "You cannot target the same unit with the Armour of Corruption and Empyric Dislocation "
            "Stratagems in the same phase."
        ),
    },
    {
        "id": "000010740004",
        "name": "Warp Flicker",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Movement phase",
        "type": "Warpstrike Champions - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Movement phase.<br><br><b>TARGET:</b> One Heretic Astartes Terminator, "
            "Obliterators or Mutilators unit from your army.<br><br><b>EFFECT:</b> Until the end of the "
            "turn, your unit is eligible to shoot and declare a charge in a turn in which it Advanced."
        ),
    },
    {
        "id": "000010740005",
        "name": "Warp-Tainted",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Movement phase",
        "type": "Warpstrike Champions - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Movement phase.<br><br><b>TARGET:</b> One Heretic Astartes Terminator, "
            "Obliterators or Mutilators unit from your army, within range of an objective marker you "
            "control.<br><br><b>EFFECT:</b> That objective marker remains under your control until your "
            "opponent's Level of Control over that objective marker is greater than yours at the end of a "
            "phase."
        ),
    },
    {
        "id": "000010740006",
        "name": "Siegebreaker Strike",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Shooting phase",
        "type": "Warpstrike Champions - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Shooting phase.<br><br><b>TARGET:</b> Up to two <span class=\"kwb\">HERETIC"
            "</span> <span class=\"kwb\">ASTARTES</span> units from your army that were set up using the "
            "Deep Strike ability this turn and have not been selected to shoot this phase.<br><br>"
            "<b>EFFECT:</b> Until the end of the phase, ranged weapons equipped by models in your units "
            "have the [IGNORES COVER] ability."
        ),
    },
    {
        "id": "000010740007",
        "name": "Portal of Spite",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Charge phase",
        "type": "Warpstrike Champions - Battle Tactic Stratagem",
        "description": (
            "<b>WHEN:</b> Your Charge phase.<br><br><b>TARGET:</b> One <span class=\"kwb\">HERETIC</span> "
            "<span class=\"kwb\">ASTARTES</span> unit from your army that was set up using the Deep Strike "
            "ability this turn and has not declared a charge this phase.<br><br><b>EFFECT:</b> Until the "
            "end of the phase, each time your unit declares a charge, if the closest eligible enemy unit is "
            "selected as one of the targets of that charge, add 2 to the Charge roll."
        ),
    },
)


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
):
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
            "description": "",
        }
    )


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    weapon = _make_wargear(
        "Test Weapon",
        melee=melee,
        attacks=attacks,
        skill=skill,
        range_value=range_value,
        strength=strength,
        ap=ap,
        damage=damage,
    )
    return weapon.profiles["default"]


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", "Warpstrike Champions")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("Warpstrike", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    csm_player.command_points = 10
    enemy_player.command_points = 10

    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_warpstrike_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_warpstrike_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    for spec in _WARPSTRIKE_SPECS:
        key = _norm_name(spec["name"])
        stratagem = existing.get(key)
        if stratagem is None:
            player.stratagems.available.append(
                Stratagem(
                    id=spec["id"],
                    name=spec["name"],
                    type=spec["type"],
                    description=spec["description"],
                    cp_cost=int(spec["cp_cost"]),
                    turn=spec["turn"],
                    phase=spec["phase"],
                    detachment="Warpstrike Champions",
                    faction_id="CSM",
                )
            )
            continue
        stratagem.id = spec["id"]
        stratagem.name = spec["name"]
        stratagem.type = spec["type"]
        stratagem.description = spec["description"]
        stratagem.cp_cost = int(spec["cp_cost"])
        stratagem.turn = spec["turn"]
        stratagem.phase = spec["phase"]
        stratagem.detachment = "Warpstrike Champions"
        stratagem.faction_id = "CSM"
    for cache_name in ("_defensive_reaction_cache", "_charge_melee_ap_cache", "_consolidate_move_cache"):
        cache = getattr(player.stratagems, cache_name, None)
        if isinstance(cache, dict):
            cache.clear()


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
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _mark_deep_strike_setup(game: Game, army: Army, unit: Unit) -> None:
    unit.arrived_from_reserves_this_turn = True
    army.chaos_space_marines_detachments.on_unit_set_up(
        unit=unit,
        game=game,
        set_up_as_reinforcements=True,
        used_deep_strike=True,
    )


def test_warpstrike_champions_stratagem_descriptors_registered():
    expected = {
        "000010740002": ("Empyric Dislocation", "defensive_ap_worsen"),
        "000010740003": ("Armour of Corruption", "defensive_damage_reduction"),
        "000010740004": ("Warp Flicker", "shoot_and_charge_after_advance"),
        "000010740005": ("Warp-Tainted", "sticky_objective"),
        "000010740006": ("Siegebreaker Strike", "ranged_weapons_gain_ignores_cover"),
        "000010740007": ("Portal of Spite", "conditional_charge_roll_bonus_if_closest_eligible_target_selected"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_empyric_dislocation_queues_applies_ap_worsen_and_blocks_armour_same_phase():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy.models[0].wargear = [_make_wargear("Accursed Weapon", melee=True, ap="-2", damage="2")]
    csm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    profile = enemy.models[0].wargear[0].profiles["default"]
    assert int(profile.get_effective_ap(enemy.models[0], terminators)) == -2

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[terminators])
    assert _pending_by_name(csm_player.stratagems, "EMPYRIC DISLOCATION") is not None
    assert _pending_by_name(csm_player.stratagems, "ARMOUR OF CORRUPTION") is not None

    assert csm_player.stratagems.use("EMPYRIC DISLOCATION", unit=terminators, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 9
    assert int(profile.get_effective_ap(enemy.models[0], terminators)) == -1

    ap_worsen = dict(getattr(terminators, "special_rules", {}).get("armour_of_contempt_ap_worsen", {}) or {})
    assert int(ap_worsen.get(str(get_entity_id(enemy) or ""), 0) or 0) == 1

    assert not csm_player.stratagems.use("ARMOUR OF CORRUPTION", unit=terminators, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 9


def test_armour_of_corruption_queues_applies_damage_reduction_and_blocks_empyric_same_phase():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy.models[0].wargear = [_make_wargear("Power Fist", melee=True, ap="-2", damage="3")]
    csm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[terminators])
    assert _pending_by_name(csm_player.stratagems, "ARMOUR OF CORRUPTION") is not None
    assert _pending_by_name(csm_player.stratagems, "EMPYRIC DISLOCATION") is not None

    assert csm_player.stratagems.use("ARMOUR OF CORRUPTION", unit=terminators, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 8

    entries = list(getattr(terminators, "special_rules", {}).get("defensive_damage_reductions", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1
        and str(entry.get("expires_phase", "") or "").strip().upper() == "FIGHT_PHASE"
        and "ARMOUR OF CORRUPTION" in str(entry.get("source", "") or "").upper()
        for entry in entries
    )

    assert not csm_player.stratagems.use("EMPYRIC DISLOCATION", unit=terminators, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 8


def test_warp_flicker_grants_shoot_and_charge_after_advance():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    terminators.models[0].wargear = [_make_wargear("Combi-bolter", melee=False)]
    csm_army.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "WARP FLICKER") is not None

    assert csm_player.stratagems.use("WARP FLICKER", unit=terminators, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    profile = terminators.models[0].wargear[0].profiles["default"]
    assert terminators.can_shoot_after_advance(profile) is True
    assert terminators.can_charge_after_advance() is True


def test_warp_tainted_applies_sticky_objective_control():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    objective = _make_objective("Midfield Objective", 10.0, 10.0)
    objective.location.controlling_player = csm_player
    csm_army.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "WARP-TAINTED")
    assert pending is not None

    assert csm_player.stratagems.use("WARP-TAINTED", unit=terminators, objective=objective, dequeue=True)
    assert int(csm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is csm_player
    assert objective.location.controlling_player is csm_player
    assert str(getattr(objective.location, "sticky_source", "") or "") == "warpstrike_champions_warp_tainted"


def test_siegebreaker_strike_grants_ignores_cover_to_selected_deep_strike_units():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    obliterators = _make_unit(
        "Obliterators",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(terminators)
    csm_army.add_unit(obliterators)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, obliterators, 14.0, 10.0)
    _mark_deep_strike_setup(game, csm_army, terminators)
    _mark_deep_strike_setup(game, csm_army, obliterators)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "SIEGEBREAKER STRIKE")
    assert pending is not None
    assert int(pending.get("max_target_count", 0) or 0) == 2

    assert csm_player.stratagems.use(
        "SIEGEBREAKER STRIKE",
        units=[terminators, obliterators],
        dequeue=True,
    )
    assert int(csm_player.command_points or 0) == 9

    for unit in (terminators, obliterators):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("warp_vision_ignores_cover_active", False))
        assert str(sr.get("warp_vision_expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
        assert str(sr.get("warp_vision_source", "") or "").strip().upper() == "SIEGEBREAKER STRIKE"


def test_portal_of_spite_grants_charge_bonus_only_when_closest_enemy_is_declared_target():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_close = _make_unit("Enemy Close", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(terminators)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy_close, 18.0, 10.0)
    _deploy_unit(game, enemy_far, 21.0, 10.0)
    _mark_deep_strike_setup(game, csm_army, terminators)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "PORTAL OF SPITE") is not None

    assert csm_player.stratagems.use("PORTAL OF SPITE", unit=terminators, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    matching = [
        (bonus, source)
        for bonus, source in list(terminators.get_charge_roll_target_strength_modifiers([enemy_close]) or [])
        if int(bonus or 0) == 2 and "PORTAL OF SPITE" in str(source or "").upper()
    ]
    non_matching = [
        (bonus, source)
        for bonus, source in list(terminators.get_charge_roll_target_strength_modifiers([enemy_far]) or [])
        if int(bonus or 0) == 2 and "PORTAL OF SPITE" in str(source or "").upper()
    ]

    assert matching
    assert not non_matching


def test_warpstrike_stratagem_support_matrix_classifies_supported():
    import scripts.generate_ability_support_matrix as gsm

    for spec in _WARPSTRIKE_SPECS:
        status, _icon, notes = gsm._stratagem_support(
            spec["name"],
            spec["description"],
            detachment_name="Warpstrike Champions",
            stratagem_id=spec["id"],
        )
        assert status == "Supported"
        assert str(notes or "").strip()
