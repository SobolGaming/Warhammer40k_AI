from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "9",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "4",
                "base_size": "80mm",
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
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Crusher Stampede")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
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


def _make_profile(
    *,
    weapon_name: str,
    is_melee: bool,
    skill: str = "4+",
    strength: str = "4",
    description: str = "",
) -> WargearProfile:
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=parent,
    )


def test_untrammelled_ferocity_applies_movement_overrides_and_cleans_up():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Screamer-Killer",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(monster)
    _deploy_unit(game, monster, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "UNTRAMMELLED FEROCITY",
        unit=monster,
        phase_name="Movement phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    sr = dict(getattr(monster, "special_rules", {}) or {})
    assert bool(sr.get("tyranids_untrammelled_ferocity_active")) is True
    assert set(sr.get("bearer_unit_phase_move_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_block_titanic_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_engagement_types", []) or []) >= {"move", "advance", "fall_back"}
    assert float(sr.get("titanic_stride_tall_terrain_height", 0.0) or 0.0) == 4.0

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=monster)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("can_move_through_terrain")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=tyr_player, phase=game.phase)
    sr_after = dict(getattr(monster, "special_rules", {}) or {})
    assert bool(sr_after.get("tyranids_untrammelled_ferocity_active", False)) is False
    assert "bearer_unit_phase_move_types" not in sr_after
    assert "bearer_unit_phase_move_block_titanic_types" not in sr_after
    assert "bearer_unit_phase_move_engagement_types" not in sr_after
    assert "titanic_stride_tall_terrain_height" not in sr_after


def test_untrammelled_ferocity_rejects_non_monster_targets():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    infantry = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(infantry)
    _deploy_unit(game, infantry, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "UNTRAMMELLED FEROCITY",
        unit=infantry,
        phase_name="Movement phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10


def test_crusher_stampede_descriptor_registered():
    expected = {
        "000008422002": ("Corrosive Viscera", "auto_trigger_deadly_demise"),
        "000008422003": ("Rampaging Monstrosities", "reroll_hit_rolls"),
        "000008422004": ("Savage Roar", "force_battleshock_and_apply_attacker_filtered_melee_penalties"),
        "000008422005": ("Untrammelled Ferocity", "move_through_models_terrain_with_titanic_block_and_tall_terrain_battleshock_risk"),
        "000008422006": ("Swarm-guided Salvoes", "grant_ranged_ignores_cover_and_ignore_ballistic_skill_and_hit_modifiers"),
        "000008422007": ("Massive Impact", "charge_end_mortal_wounds"),
    }
    for stratagem_id, (name, effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect

    untrammelled = get_stratagem_tool_descriptor(stratagem_id="000008422005")
    assert list(untrammelled.effect_params.get("move_types", []) or []) == ["move", "advance", "fall_back"]
    assert float(untrammelled.effect_params.get("tall_terrain_threshold", 0.0) or 0.0) == 4.0


def test_rampaging_monstrosities_grants_full_melee_hit_rerolls_until_phase_end():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Screamer-Killer",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(monster)
    _deploy_unit(game, monster, 10.0, 10.0)

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "RAMPAGING MONSTROSITIES",
        unit=monster,
        phase_name="Fight phase",
    )
    assert ok is True

    hit_mods = monster.get_unit_hit_reroll_modifiers("melee", attacker_model=monster.models[0])
    assert bool(hit_mods.get("reroll_hit_full")) is True
    assert any(
        "RAMPAGING MONSTROSITIES" in str(reason or "").upper()
        for reason in list(hit_mods.get("reroll_hit_full_reasons") or [])
    )

    game.event_system.publish("phase_end", player=tyr_player, phase=game.phase)
    hit_mods_after = monster.get_unit_hit_reroll_modifiers("melee", attacker_model=monster.models[0])
    assert bool(hit_mods_after.get("reroll_hit_full")) is False


def test_swarm_guided_salvoes_grants_ignores_cover_and_ignore_modifier_rule():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monster = _make_unit(
        "Exocrine",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    monster.models[0].wargear = [
        SimpleNamespace(id="bio-cannon-1", name="Bio-cannon", is_ranged=lambda: True)
    ]
    tyr_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, monster, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "SWARM-GUIDED SALVOES",
        unit=monster,
        phase_name="Shooting phase",
    )
    assert ok is True

    bonuses = list(monster.models[0].get_temporary_weapon_keyword_bonuses("Bio-cannon") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in bonuses
    )

    profile = _make_profile(weapon_name="Bio-cannon", is_melee=False)
    rule = profile._ignore_hit_modifier_rule(monster.models[0], target_unit=enemy)
    assert rule is not None
    assert str(rule.get("name", "") or "").strip().upper() == "SWARM-GUIDED SALVOES"
    assert set(rule.get("skill_kinds", set()) or set()) == {"ballistic", "weapon"}

    game.event_system.publish("phase_end", player=tyr_player, phase=game.phase)
    assert list(monster.models[0].get_temporary_weapon_keyword_bonuses("Bio-cannon") or []) == []
    assert bool(getattr(monster, "special_rules", {}).get("tyranids_swarm_guided_salvoes_active", False)) is False


def test_massive_impact_queues_after_charge_move_and_deals_expected_mortals():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monster = _make_unit(
        "Screamer-Killer",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, monster, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    monster.round_state.charged_this_round = True
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "CHARGE_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=monster, action="charge")
    pending = _pending_by_name(tyr_player.stratagems, "MASSIVE IMPACT")
    assert pending is not None
    assert len(list(pending.get("source_model_candidates") or [])) == 1

    enemy_wounds_before = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_tyranids.dice_module.get_roll", side_effect=[4, 5, 1, 2, 6, 3]):
        ok = tyr_player.stratagems.use("MASSIVE IMPACT", phase_name="Charge phase", dequeue=True)

    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert int(enemy.models[0].wounds or 0) == enemy_wounds_before - 3


def test_savage_roar_applies_hit_and_wound_penalties_when_forced_battleshock_fails():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Screamer-Killer",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Enemy Bruiser",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    game.rebuild_entity_registry()
    game.turn = 1

    melee_profile = _make_profile(weapon_name="Enemy Blade", is_melee=True, skill="4+", strength="9")
    before_hit = melee_profile._hit_target_with_tracking(
        defender,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    before_wound = melee_profile._wound_target_with_tracking(
        defender,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(before_hit.get("hit")) is True
    assert bool(before_wound.get("wound")) is True

    def _force_failed_battle_shock(current_turn=1, *, modifier=0, source=""):
        assert int(current_turn or 0) == 1
        assert str(source or "").strip().upper() == "SAVAGE ROAR"
        attacker._last_leadership_test_passed = False
        game.event_system.publish("battle_shock_test_resolved", unit=attacker, passed=False)

    attacker.force_battle_shock_test = _force_failed_battle_shock

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[defender])
    assert _pending_by_name(tyr_player.stratagems, "SAVAGE ROAR") is not None

    ok = tyr_player.stratagems.use(
        "SAVAGE ROAR",
        unit=defender,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    hit_mods = list(defender.special_rules.get("defensive_hit_mods", []) or [])
    wound_mods = list(defender.special_rules.get("defensive_wound_mods", []) or [])
    assert any("SAVAGE ROAR" in str(entry.get("source", "")).upper() for entry in hit_mods if isinstance(entry, dict))
    assert any("SAVAGE ROAR" in str(entry.get("source", "")).upper() for entry in wound_mods if isinstance(entry, dict))

    during_hit = melee_profile._hit_target_with_tracking(
        defender,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    during_wound = melee_profile._wound_target_with_tracking(
        defender,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(during_hit.get("hit")) is False
    assert bool(during_wound.get("wound")) is False

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert list(defender.special_rules.get("defensive_hit_mods", []) or []) == []
    assert list(defender.special_rules.get("defensive_wound_mods", []) or []) == []


def test_savage_roar_only_applies_wound_penalty_on_failed_battleshock():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Tervigon",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Enemy Bruiser",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    game.rebuild_entity_registry()
    game.turn = 1

    def _force_passed_battle_shock(current_turn=1, *, modifier=0, source=""):
        assert int(current_turn or 0) == 1
        assert str(source or "").strip().upper() == "SAVAGE ROAR"
        attacker._last_leadership_test_passed = True
        game.event_system.publish("battle_shock_test_resolved", unit=attacker, passed=True)

    attacker.force_battle_shock_test = _force_passed_battle_shock

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[defender])
    ok = tyr_player.stratagems.use(
        "SAVAGE ROAR",
        unit=defender,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert list(defender.special_rules.get("defensive_hit_mods", []) or []) != []
    assert list(defender.special_rules.get("defensive_wound_mods", []) or []) == []


def test_corrosive_viscera_queues_before_removal_and_auto_triggers_deadly_demise():
    from warhammer40k_ai.utility.dice import DiceCollection

    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    monster = _make_unit(
        "Haruspex",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(monster)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, monster, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    monster.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    destroyed_model = monster.models[0]
    destroyed_model.wounds = 0
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    tyr_player.stratagems._current_phase_name = "SHOOTING_PHASE"
    tyr_player.stratagems._on_model_destroyed_before_removal(unit=monster, model=destroyed_model)
    assert _pending_by_name(tyr_player.stratagems, "CORROSIVE VISCERA") is not None

    enemy_wounds_before = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.units.unit.get_roll", return_value=1):
        ok = tyr_player.stratagems.use("CORROSIVE VISCERA", phase_name="Shooting phase", dequeue=True)

    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert int(enemy.models[0].wounds or 0) < enemy_wounds_before


def test_crusher_stampede_stratagem_support_matrix_entries_are_supported():
    import scripts.generate_ability_support_matrix as gsm

    expected = {
        "CORROSIVE VISCERA": "auto-triggers deadly demise",
        "MASSIVE IMPACT": "roll 6d6",
        "RAMPAGING MONSTROSITIES": "full melee hit re-rolls",
        "SAVAGE ROAR": "battle-shock test",
        "SWARM-GUIDED SALVOES": "ignores cover",
        "UNTRAMMELLED FEROCITY": "move through models",
    }
    for name, note_fragment in expected.items():
        status, notes, _ = gsm._stratagem_support(name)
        assert status == "Supported"
        assert note_fragment.lower() in str(notes or "").lower()
