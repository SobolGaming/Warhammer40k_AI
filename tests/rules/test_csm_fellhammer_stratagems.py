from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
                "T": "4",
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 6,
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
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_profile(*, melee: bool):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _make_ranged_wargear(name: str, *, description: str = "", range_value: str = "24") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": str(range_value),
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", "Fellhammer Siege-host")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = SimpleNamespace(name="COMMAND_PHASE")

    csm_player.command_points = 10
    enemy_player.command_points = 10

    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_fellhammer_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_fellhammer_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008977002",
            "Persistent Assailants",
            1,
            "Either player's turn",
            "Fight phase",
            "Fellhammer Siege-Host - Battle Tactic Stratagem",
        ),
        (
            "000008977003",
            "Brutal Attrition",
            1,
            "Either player's turn",
            "Fight phase",
            "Fellhammer Siege-Host - Epic Deed Stratagem",
        ),
        (
            "000008977004",
            "Pitiless Cannonade",
            1,
            "Your turn",
            "Shooting phase",
            "Fellhammer Siege-Host - Battle Tactic Stratagem",
        ),
        (
            "000008977005",
            "Point-Blank Destruction",
            1,
            "Your turn",
            "Shooting phase",
            "Fellhammer Siege-Host - Battle Tactic Stratagem",
        ),
        (
            "000008977006",
            "Steadfast Determination",
            1,
            "Opponent's turn",
            "Shooting phase",
            "Fellhammer Siege-Host - Strategic Ploy Stratagem",
        ),
        (
            "000008977007",
            "Siegecraft",
            1,
            "Opponent's turn",
            "Charge phase",
            "Fellhammer Siege-Host - Strategic Ploy Stratagem",
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
                detachment="Fellhammer Siege-host",
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
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_fellhammer_stratagem_descriptors_registered():
    expected = {
        "000008977002": "Persistent Assailants",
        "000008977003": "Brutal Attrition",
        "000008977004": "Pitiless Cannonade",
        "000008977005": "Point-Blank Destruction",
        "000008977006": "Steadfast Determination",
        "000008977007": "Siegecraft",
    }

    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_persistent_assailants_queues_applies_melee_rerolls_and_cleans_up():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    csm_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[legionaries])

    pending = _pending_by_name(csm_player.stratagems, "PERSISTENT ASSAILANTS")
    assert pending is not None
    assert csm_player.stratagems.use("PERSISTENT ASSAILANTS", unit=legionaries, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    profile = _make_profile(melee=True)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            legionaries.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert hit_result["hit"] is True
    assert int(hit_result.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_result.get("special_effects", []), "Persistent Assailants")

    full_strength_wound = profile._wound_target_with_tracking(
        enemy,
        legionaries.models[0],
        {},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert full_strength_wound["wound"] is False
    assert "reroll" not in full_strength_wound

    legionaries.models[0].wounds = 1
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        below_half_wound = profile._wound_target_with_tracking(
            enemy,
            legionaries.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert below_half_wound["wound"] is True
    assert int(below_half_wound.get("reroll", 0) or 0) == 4

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    expired_hit = profile._hit_target_with_tracking(
        enemy,
        legionaries.models[0],
        {},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert expired_hit["hit"] is False
    assert "reroll" not in expired_hit


def test_brutal_attrition_caps_allocations_and_resolves_post_attack_mortals():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=7,
        wounds=2,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    csm_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[legionaries])

    pending = _pending_by_name(csm_player.stratagems, "BRUTAL ATTRITION")
    assert pending is not None
    assert csm_player.stratagems.use("BRUTAL ATTRITION", unit=legionaries, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    profile = _make_profile(melee=True)
    for model in list(legionaries.models or []):
        result = profile._apply_damage_with_tracking(
            model,
            enemy.models[0],
            1,
            False,
            attack_instance={},
            game_map=game.map,
        )
        assert int(result.get("damage_applied", 0) or 0) == 1

    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    allocations_by_key = dict(sr.get("allocated_melee_retaliation_allocations", {}) or {})
    specs_by_key = dict(sr.get("allocated_melee_retaliation_specs", {}) or {})
    assert len(allocations_by_key) == 1
    assert len(specs_by_key) == 1
    ability_key = next(iter(allocations_by_key))
    attacker_id = str(get_entity_id(enemy) or "")
    assert int(allocations_by_key[ability_key].get(attacker_id, 0) or 0) == 6

    with patch(
        "warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll",
        side_effect=[4, 4, 3, 6, 1, 5],
    ):
        game._on_fight_sequence_complete_allocated_melee_mortal_retaliation(unit=enemy)

    assert int(enemy.models[0].wounds) == 6
    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    assert "allocated_melee_retaliation_allocations" not in sr
    assert "allocated_melee_retaliation_specs" not in sr


def test_pitiless_cannonade_queues_applies_crit_threshold_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    havocs = _make_unit(
        "Havocs",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    wounded_enemy = _make_unit(
        "Wounded Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    fresh_enemy = _make_unit(
        "Fresh Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    wounded_enemy.models[0].wounds = 1
    csm_army.add_unit(havocs)
    enemy_army.add_unit(wounded_enemy)
    enemy_army.add_unit(fresh_enemy)
    _deploy_unit(game, havocs, 10.0, 10.0)
    _deploy_unit(game, wounded_enemy, 16.0, 10.0)
    _deploy_unit(game, fresh_enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "PITILESS CANNONADE")
    assert pending is not None
    assert csm_player.stratagems.use("PITILESS CANNONADE", unit=havocs, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    profile = _make_profile(melee=False)
    wounded_hit = profile._hit_target_with_tracking(
        wounded_enemy,
        havocs.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wounded_hit["hit"] is True
    assert int(wounded_hit.get("crit_threshold", 0) or 0) == 5
    assert _contains_text(wounded_hit.get("special_effects", []), "Pitiless Cannonade")

    fresh_hit = profile._hit_target_with_tracking(
        fresh_enemy,
        havocs.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert fresh_hit["hit"] is True
    assert int(fresh_hit.get("crit_threshold", 0) or 0) == 6

    game.event_system.publish("phase_end", player=csm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    expired_hit = profile._hit_target_with_tracking(
        wounded_enemy,
        havocs.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert expired_hit["hit"] is True
    assert int(expired_hit.get("crit_threshold", 0) or 0) == 6


def test_point_blank_destruction_grants_temporary_pistol_only_to_non_blast_weapons():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    rifle = _make_ranged_wargear("Bolt Rifle")
    missile = _make_ranged_wargear("Frag Missile", description="Blast")
    legionaries.models[0].wargear = [rifle, missile]
    csm_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 10.5, 10.0)
    game.rebuild_entity_registry()

    model = legionaries.models[0]
    rifle_profile = rifle.profiles["default"]
    missile_profile = missile.profiles["default"]
    assert legionaries.weapon_profile_counts_as_pistol(rifle_profile, model=model) is False
    assert legionaries._can_model_shoot_weapon_at_target(model, rifle_profile, enemy, game.map) is False
    assert legionaries._can_model_shoot_weapon_at_target(model, missile_profile, enemy, game.map) is False

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "POINT-BLANK DESTRUCTION")
    assert pending is not None
    assert csm_player.stratagems.use("POINT-BLANK DESTRUCTION", unit=legionaries, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    assert legionaries.weapon_profile_counts_as_pistol(rifle_profile, model=model) is True
    assert legionaries.weapon_profile_counts_as_pistol(missile_profile, model=model) is False
    assert legionaries._can_model_shoot_weapon_at_target(model, rifle_profile, enemy, game.map) is True
    assert legionaries._can_model_shoot_weapon_at_target(model, missile_profile, enemy, game.map) is False

    game.event_system.publish("phase_end", player=csm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert legionaries.weapon_profile_counts_as_pistol(rifle_profile, model=model) is False
    assert model.get_temporary_weapon_keyword_bonuses("Bolt Rifle") == []
    assert legionaries._can_model_shoot_weapon_at_target(model, rifle_profile, enemy, game.map) is False


def test_steadfast_determination_queues_applies_fnp_and_cleans_up():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Chaos Terminators",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[terminators])

    pending = _pending_by_name(csm_player.stratagems, "STEADFAST DETERMINATION")
    assert pending is not None
    assert csm_player.stratagems.use("STEADFAST DETERMINATION", unit=terminators, attacking_unit=enemy, dequeue=True)
    assert int(csm_player.command_points or 0) == 9
    assert any(int(value) == 5 and not condition for value, condition in list(terminators.has_feel_no_pain() or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not any(int(value) == 5 and not condition for value, condition in list(terminators.has_feel_no_pain() or []))


def test_siegecraft_queues_applies_charge_penalty_and_is_not_cumulative():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.get_charge_roll_target_keyword_modifiers = lambda _target: [(-1, "Other Penalty")]
    csm_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    pending = _pending_by_name(csm_player.stratagems, "SIEGECRAFT")
    assert pending is not None
    assert csm_player.stratagems.use("SIEGECRAFT", unit=legionaries, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    modifiers = game.get_charge_roll_modifiers(enemy, target_unit=legionaries)
    negative_modifiers = [(int(value), str(source)) for value, source in list(modifiers or []) if int(value) < 0]
    assert len(negative_modifiers) == 1
    assert negative_modifiers[0][0] == -2
    assert "SIEGECRAFT" in negative_modifiers[0][1].upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    modifiers_after = game.get_charge_roll_modifiers(enemy, target_unit=legionaries)
    negative_modifiers_after = [(int(value), str(source)) for value, source in list(modifiers_after or []) if int(value) < 0]
    assert negative_modifiers_after == [(-1, "Other Penalty")]
