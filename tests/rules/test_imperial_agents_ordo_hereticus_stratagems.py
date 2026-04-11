import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.battlefield.objective_sites import Objective, ObjectiveCategory
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        model_count=1,
        movement=6,
        toughness=4,
        wounds=3,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{str(name).lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
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
    name,
    *,
    faction_name="Imperial Agents",
    keywords=None,
    faction_keywords=None,
    model_count=1,
    movement=6,
    toughness=4,
    wounds=3,
):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    ia_army = Army.with_detachment("Imperial Agents", "Ordo Hereticus Purgation Force")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    ia_player.command_points = 10
    enemy_player.command_points = 10
    return game, ia_player, enemy_player, ia_army, enemy_army


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    for player in players:
        player.stratagems.refresh_available()


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    expected = str(name or "").strip().upper()
    for pending in list(getattr(stratagems, "_pending_reactions", []) or []):
        if str(pending.get("stratagem", "") or "").strip().upper() == expected:
            return pending
    return None


def _find_request(game: Game, *, decision_type: str):
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "list"):
        return None
    for request in list(queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


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


def _make_ranged_profile(unit: Unit, *, name: str = "Test Rifle", is_blast: bool = False):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Blast" if is_blast else "",
        }
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [weapon]
    return weapon.profiles["default"]


class TestImperialAgentsOrdoHereticusStratagems(unittest.TestCase):
    def test_ordo_hereticus_stratagem_descriptors_registered(self):
        expected = {
            "000009131002": ("Stun Grenades", "battle_shock_and_hit_penalty"),
            "000009131003": ("Dispense Justice", "grant_lethal_hits"),
            "000009131004": ("Inviolate Jurisdiction", "feel_no_pain"),
            "000009131005": ("Execution Order", "targeted_precision"),
            "000009131006": ("Line of Fire", "allow_ranged_targeting_into_friendly_engagement"),
            "000009131007": ("Exact Punishment", "reactive_shooting_forced_target"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(getattr(by_id, "name", "") or ""), expected_name)
            self.assertEqual(str(getattr(by_id, "effect", "") or ""), expected_effect)
            self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), stratagem_id)

    def test_dispense_justice_grants_lethal_hits_until_phase_end(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        shooters = _make_unit(
            "Exaction Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(shooters)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooters, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)
        profile = _make_ranged_profile(shooters)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, _enemy_player])

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("DISPENSE JUSTICE", unit=shooters, phase_name="Shooting phase")
        self.assertTrue(ok)

        bonuses = shooters.get_attack_keyword_bonuses(
            target=enemy,
            attack_type="ranged",
            model=shooters.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits")))
        self.assertTrue(any("DISPENSE JUSTICE" in str(source).upper() for source in list(bonuses.get("sources", []) or [])))

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        bonuses_after = shooters.get_attack_keyword_bonuses(
            target=enemy,
            attack_type="ranged",
            model=shooters.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertFalse(bool(bonuses_after.get("lethal_hits")))

    def test_execution_order_grants_precision_only_against_selected_enemy_character_and_expires(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        squad = _make_unit(
            "Inquisitorial Agents",
            keywords=["INFANTRY", "INQUISITORIAL AGENTS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_character = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ENEMY"],
        )
        enemy_other = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(squad)
        enemy_army.add_unit(enemy_character)
        enemy_army.add_unit(enemy_other)
        _place_unit(game, squad, 10.0, 10.0)
        _place_unit(game, enemy_character, 18.0, 10.0)
        _place_unit(game, enemy_other, 20.0, 12.0)
        profile = _make_ranged_profile(squad)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, _enemy_player])

        _set_phase(game, ia_player, "COMMAND_PHASE", 0)
        ok = ia_player.stratagems.use(
            "EXECUTION ORDER",
            unit=squad,
            enemy_unit=enemy_character,
            phase_name="Command phase",
        )
        self.assertTrue(ok)

        versus_marked = squad.get_attack_keyword_bonuses(
            target=enemy_character,
            attack_type="ranged",
            model=squad.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        versus_other = squad.get_attack_keyword_bonuses(
            target=enemy_other,
            attack_type="ranged",
            model=squad.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertTrue(bool(versus_marked.get("precision")))
        self.assertFalse(bool(versus_other.get("precision")))

        game.turn = 3
        _set_phase(game, ia_player, "COMMAND_PHASE", 0)
        expired = squad.get_attack_keyword_bonuses(
            target=enemy_character,
            attack_type="ranged",
            model=squad.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertFalse(bool(expired.get("precision")))

    def test_inviolate_jurisdiction_queues_applies_fnp_and_cleans_up(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        target = _make_unit(
            "Subductor Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 18.0, 10.0)
        game.map.objectives = [_make_objective("Center", 10.0, 10.0)]
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
        pending = _pending_by_name(ia_player.stratagems, "INVIOLATE JURISDICTION")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            "INVIOLATE JURISDICTION",
            unit=target,
            attacking_unit=attacker,
            target_units=[target],
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        fnp_entries = list(target.models[0].get_temporary_fnp_entries() or [])
        self.assertIn((5, None), fnp_entries)

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertEqual(list(target.models[0].get_temporary_fnp_entries() or []), [])

    def test_line_of_fire_allows_non_blast_ranged_targeting_into_engagement_within_twelve(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Exaction Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        screen_near = _make_unit(
            "Subductor Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        screen_far = _make_unit(
            "Vigilant Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_near = _make_unit(
            "Enemy Near",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(shooter)
        ia_army.add_unit(screen_near)
        ia_army.add_unit(screen_far)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, screen_near, 20.5, 10.0)
        _place_unit(game, enemy_near, 22.0, 10.0)
        _place_unit(game, screen_far, 23.5, 14.0)
        _place_unit(game, enemy_far, 25.0, 14.0)
        normal_profile = _make_ranged_profile(shooter, name="Shotgun")
        blast_profile = _make_ranged_profile(shooter, name="Grenade Launcher", is_blast=True)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, _enemy_player])

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        baseline = shooter._can_model_shoot_weapon_at_target(shooter.models[0], normal_profile, enemy_near, game.map)
        self.assertFalse(baseline)

        ok = ia_player.stratagems.use("LINE OF FIRE", unit=shooter, phase_name="Shooting phase")
        self.assertTrue(ok)

        allowed = shooter._can_model_shoot_weapon_at_target(shooter.models[0], normal_profile, enemy_near, game.map)
        blocked_blast = shooter._can_model_shoot_weapon_at_target(shooter.models[0], blast_profile, enemy_near, game.map)
        blocked_far = shooter._can_model_shoot_weapon_at_target(shooter.models[0], normal_profile, enemy_far, game.map)
        self.assertTrue(allowed)
        self.assertFalse(blocked_blast)
        self.assertFalse(blocked_far)

    def test_stun_grenades_queues_applies_battle_shock_and_hit_penalty_and_cleans_up(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        grenadiers = _make_unit(
            "Inquisitorial Grenadiers",
            keywords=["INFANTRY", "INQUISITORIAL AGENTS", "GRENADES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(grenadiers)
        enemy_army.add_unit(enemy)
        _place_unit(game, grenadiers, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)
        enemy.take_battle_shock_test = Mock()
        game._visible_enemy_candidates_for_model = lambda **kwargs: list(kwargs.get("enemy_roots") or [])
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        pending = _pending_by_name(ia_player.stratagems, "STUN GRENADES")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            "STUN GRENADES",
            unit=grenadiers,
            enemy_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        enemy.take_battle_shock_test.assert_called_once_with(game.turn)

        hit_mods = enemy.get_unit_hit_reroll_modifiers("ranged", target=grenadiers, attacker_model=enemy.models[0])
        self.assertEqual(int(hit_mods.get("hit", 0) or 0), -1)
        self.assertTrue(any("STUN GRENADES" in str(reason).upper() for reason in list(hit_mods.get("hit_reasons", ()) or ())))

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        hit_mods_after = enemy.get_unit_hit_reroll_modifiers("ranged", target=grenadiers, attacker_model=enemy.models[0])
        self.assertEqual(int(hit_mods_after.get("hit", 0) or 0), 0)

    def test_exact_punishment_queues_reactive_shooting_with_forced_target(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        destroyed = _make_unit(
            "Agents Screen",
            keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        retaliator = _make_unit(
            "Exaction Squad",
            keywords=["INFANTRY", "ADEPTUS ARBITES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(destroyed)
        ia_army.add_unit(retaliator)
        enemy_army.add_unit(attacker)
        _place_unit(game, destroyed, 10.0, 10.0)
        _place_unit(game, retaliator, 14.0, 10.0)
        _place_unit(game, attacker, 22.0, 10.0)
        game._setup_reactive_can_shoot_target = lambda unit, target_unit: True
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("unit_destroyed", unit=destroyed, destroyed_by_unit=attacker)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={destroyed: []})
        pending = _pending_by_name(ia_player.stratagems, "EXACT PUNISHMENT")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            "EXACT PUNISHMENT",
            unit=retaliator,
            enemy_unit=attacker,
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
        self.assertTrue(ok)
        request = _find_request(game, decision_type=DECISION_DECLARE_SHOTS)
        self.assertIsNotNone(request)
        request_ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(request_ctx.get("force_target_unit_id", "") or ""), str(get_entity_id(attacker) or ""))
