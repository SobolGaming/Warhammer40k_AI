import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        model_count: int = 2,
        keywords=None,
        faction_keywords=None,
        transport: str = "",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Drukhari"}
        self.keywords = list(keywords or ["INFANTRY"])
        self.faction_keywords = list(faction_keywords or ["DRUKHARI"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "14" if "VEHICLE" in self.keywords else "8",
                "T": "8" if "VEHICLE" in self.keywords else "3",
                "Sv": "4",
                "W": "10" if "VEHICLE" in self.keywords else "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "60mm" if "VEHICLE" in self.keywords else "28mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    model_count: int = 2,
    keywords=None,
    faction_keywords=None,
    transport: str = "",
):
    from warhammer40k_ai.units.unit import Unit

    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            transport=transport,
        )
    )


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Drukhari", "Det")
    army1.faction_id = "DRU"
    army2 = Army.with_detachment("Enemy", "Det")
    army2.faction_id = "SM"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


def _find_quarry_request(game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        if req.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key):
            return req
    return None


def _make_attack_result(attacker_name: str, target_name: str, weapon_name: str) -> AttackResult:
    return AttackResult(
        weapon_name=weapon_name,
        attacker_name=attacker_name,
        target_unit_name=target_name,
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


class TestDrukhariBatch4Abilities(unittest.TestCase):
    def test_precognisant_sets_drukhari_redeploy_filters(self):
        ability = {
            "name": "Precognisant",
            "description": (
                "If your army includes this model, after both players have deployed their armies, select up to three "
                "Drukhari units from your army and redeploy them. When doing so, you can set those units up in "
                "Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Lady Malys", abilities=[ability], model_count=1, keywords=["INFANTRY", "CHARACTER"])

        has_redeploy, count, can_place_in_reserves = unit.has_redeploy()

        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 3)
        self.assertTrue(can_place_in_reserves)
        self.assertEqual(list(unit._ability_cache.get("redeploy_filters") or []), ["DRUKHARI"])

    def test_archons_will_queues_and_applies_conditional_invuln_and_oc(self):
        ability = {
            "name": "Archon's Will",
            "description": (
                "At the start of the first battle round, select one objective marker on the battlefield. Until the end "
                "of the battle, while this unit is within range of that objective marker, unless this unit is "
                "Battle-shocked, models in this unit have a 5+ invulnerable save and an Objective Control characteristic of 3."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        unit = _make_unit("Hand of the Archon", abilities=[ability], model_count=2, keywords=["INFANTRY"])
        enemy = _make_unit("Enemy", model_count=1)
        for u in (unit, enemy):
            u.deployed = True
            u.reserve_status = "deployed"
        army1.add_unit(unit)
        army2.add_unit(enemy)
        game.map.units = [unit, enemy]

        near_objective = SimpleNamespace(
            id="obj-near",
            name="Near Objective",
            location=SimpleNamespace(id="obj-near-loc", x=0.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
        )
        far_objective = SimpleNamespace(
            id="obj-far",
            name="Far Objective",
            location=SimpleNamespace(id="obj-far-loc", x=24.0, y=24.0, z=0.0, control_radius=3.0, removed=False),
        )
        game.objectives = [near_objective, far_objective]
        game.map.objectives = [near_objective, far_objective]
        for model in list(unit.models or []):
            model.set_location(0.0, 0.0, 0.0, 0.0)
        game.rebuild_entity_registry()

        army1.on_battle_round_start(1)
        request = _find_quarry_request(game, "archons_will_objective")
        self.assertIsNotNone(request)

        selected_option = None
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("objective_id", "") or "") == "obj-near":
                selected_option = str(opt.option_id)
                break
        self.assertIsNotNone(selected_option)

        cmd_result = resolve_decision_command(
            game,
            request,
            selected_option,
            player_id=getattr(army1.player, "id", None),
        )
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))
        self.assertEqual(str(unit.special_rules.get("archons_will_objective_id", "") or ""), "obj-near")

        model = unit.models[0]
        self.assertTrue(unit.archons_will_effects_active(game=game))
        invuln, source = unit.get_model_invulnerable_save_override(model)
        self.assertEqual(invuln, 5)
        self.assertIn("archon", str(source).lower())
        self.assertEqual(model.objective_control, 3)

        for mdl in list(unit.models or []):
            mdl.set_location(20.0, 20.0, 0.0, 0.0)
        self.assertFalse(unit.archons_will_effects_active(game=game))
        invuln_far, _source_far = unit.get_model_invulnerable_save_override(model)
        self.assertNotEqual(invuln_far, 5)
        self.assertEqual(model.objective_control, 1)

    def test_vanguard_of_dark_city_queues_and_persists_mode(self):
        vanguard = {
            "name": "Vanguard of the Dark City",
            "description": (
                "At the start of your Command phase, select one of the abilities in the Vanguard of the Dark City "
                "section for this model. Until the start of your next Command phase, this model has that ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        raider = _make_unit(
            "Raider",
            abilities=[vanguard],
            model_count=1,
            keywords=["VEHICLE", "Transport", "FLY"],
            transport="This model has a transport capacity of 11 DRUKHARI INFANTRY models.",
        )
        enemy = _make_unit("Enemy", model_count=1)
        raider.deployed = True
        enemy.deployed = True
        raider.reserve_status = "deployed"
        enemy.reserve_status = "deployed"
        army1.add_unit(raider)
        army2.add_unit(enemy)
        game.map.units = [raider, enemy]
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=game.get_current_player(), phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_quarry_request(game, "vanguard_of_dark_city")
        self.assertIsNotNone(request)
        option_modes = sorted(
            str((opt.payload or {}).get("vanguard_mode", "") or "")
            for opt in list(request.options or [])
        )
        self.assertEqual(
            option_modes,
            ["masters_of_the_shadowed_sky", "speed_of_the_kill", "visions_of_butchery"],
        )

        selected_option = None
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("vanguard_mode", "") or "") == "speed_of_the_kill":
                selected_option = str(opt.option_id)
                break
        self.assertIsNotNone(selected_option)
        cmd_result = resolve_decision_command(
            game,
            request,
            selected_option,
            player_id=getattr(army1.player, "id", None),
        )
        apply_result = getattr(cmd_result, "value", None)
        self.assertTrue(apply_result.ok, msg=str(apply_result.errors))
        self.assertEqual(raider.get_vanguard_of_dark_city_selected_mode(), "speed_of_the_kill")

    def test_masters_of_shadowed_sky_requires_mode_and_embarked_kabalites(self):
        vanguard = {
            "name": "Vanguard of the Dark City",
            "description": (
                "At the start of your Command phase, select one of the abilities in the Vanguard of the Dark City "
                "section for this model. Until the start of your next Command phase, this model has that ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        masters = {
            "name": "Masters of the Shadowed Sky",
            "description": (
                "At the end of your Command phase, if one or more KABALITE WARRIORS units are embarked within this "
                "model and this model is within range of an objective marker you control, that objective marker remains "
                "under your control until your opponent's Level of Control over that objective marker is greater than yours at the end of a phase."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        raider = _make_unit(
            "Raider",
            abilities=[vanguard, masters],
            model_count=1,
            keywords=["VEHICLE", "Transport", "FLY"],
            transport="This model has a transport capacity of 11 DRUKHARI INFANTRY models.",
        )
        kabalites = _make_unit(
            "Kabalite Warriors",
            model_count=5,
            keywords=["INFANTRY", "KABALITE WARRIORS"],
        )
        raider.transport_passengers = [kabalites]

        self.assertFalse(raider.command_phase_sticky_objective_prerequisites_met())
        raider.special_rules["vanguard_of_dark_city_selected_mode"] = "masters_of_the_shadowed_sky"
        self.assertTrue(raider.command_phase_sticky_objective_prerequisites_met())

        raider.transport_passengers = []
        self.assertFalse(raider.command_phase_sticky_objective_prerequisites_met())

    def test_speed_of_the_kill_sets_wych_disembark_distance_to_six(self):
        game, _army1, _army2 = _build_game()
        raider = _make_unit(
            "Raider",
            abilities=[{"name": "Vanguard of the Dark City", "description": "Vanguard of the Dark City", "type": "Datasheet", "parameter": ""}],
            model_count=1,
            keywords=["VEHICLE", "Transport", "FLY"],
        )
        raider.special_rules["vanguard_of_dark_city_selected_mode"] = "speed_of_the_kill"
        wyches = _make_unit("Wyches", model_count=5, keywords=["INFANTRY", "WYCHES"])

        overrides = wyches._disembark_override_rules(transport_unit=raider, game=game)
        self.assertEqual(float(overrides.get("max_distance", 0.0) or 0.0), 6.0)

    def test_visions_of_butchery_adds_attacks_per_embarked_wracks_model(self):
        vanguard = {
            "name": "Vanguard of the Dark City",
            "description": (
                "At the start of your Command phase, select one of the abilities in the Vanguard of the Dark City "
                "section for this model. Until the start of your next Command phase, this model has that ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        raider = _make_unit(
            "Raider",
            abilities=[vanguard],
            model_count=1,
            keywords=["VEHICLE", "Transport", "FLY"],
            transport="This model has a transport capacity of 11 DRUKHARI INFANTRY models.",
        )
        raider.special_rules["vanguard_of_dark_city_selected_mode"] = "visions_of_butchery"
        wracks = _make_unit("Wracks", model_count=3, keywords=["INFANTRY", "WRACKS"])
        raider.transport_passengers = [wracks]

        target = _make_unit("Enemy", model_count=1)
        parent_wargear = SimpleNamespace(
            name="Bladevanes",
            is_melee=lambda: True,
            is_ranged=lambda: False,
        )
        profile = WargearProfile(
            "default",
            {
                "range": "Melee",
                "A": "3",
                "BS_WS": "3+",
                "S": "6",
                "AP": "1",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent_wargear,
        )
        attack_result = _make_attack_result("Raider", "Enemy", "Bladevanes")
        count_info = profile._resolve_attack_count(
            target,
            raider.models[0],
            attack_result,
            publish_roll_event=False,
        )
        self.assertEqual(count_info.num_attacks, 6)
        self.assertTrue(
            any("visions of butchery" in str(note).lower() for note in list(count_info.special_modifiers or []))
        )

    def test_void_mine_queues_and_resolves_once_per_battle(self):
        ability = {
            "name": "Void Mine",
            "description": (
                "Once per battle, after this unit ends a Normal move, you can select one enemy model that it moved over "
                "during that move, then roll one D6 for each enemy unit within D6\" of that model: on a 4+, that enemy unit suffers D6 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        bomber = _make_unit("Voidraven Bomber", abilities=[ability], model_count=1, keywords=["VEHICLE", "FLY"])
        enemy_a = _make_unit("Enemy A", model_count=1)
        enemy_b = _make_unit("Enemy B", model_count=1)
        enemy_far = _make_unit("Enemy Far", model_count=1)
        for unit in (bomber, enemy_a, enemy_b, enemy_far):
            unit.deployed = True
            unit.reserve_status = "deployed"
        army1.add_unit(bomber)
        army2.add_unit(enemy_a)
        army2.add_unit(enemy_b)
        army2.add_unit(enemy_far)
        game.map.units = [bomber, enemy_a, enemy_b, enemy_far]
        game.rebuild_entity_registry()

        bomber.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        bomber.models[0].last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
        enemy_a.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy_b.models[0].set_location(7.0, 0.0, 0.0, 0.0)
        enemy_far.models[0].set_location(20.0, 0.0, 0.0, 0.0)

        applied = {"a": [], "b": [], "far": []}
        enemy_a._apply_mortal_wounds_to_unit = lambda _unit, amount, game_map=None: applied["a"].append(int(amount))
        enemy_b._apply_mortal_wounds_to_unit = lambda _unit, amount, game_map=None: applied["b"].append(int(amount))
        enemy_far._apply_mortal_wounds_to_unit = lambda _unit, amount, game_map=None: applied["far"].append(int(amount))

        game._on_unit_move_ended_move_over_mortal_wounds(unit=bomber, action="move")
        request = _find_quarry_request(game, "void_mine")
        self.assertIsNotNone(request)
        candidate_ids = set(str(v or "") for v in list((request.context or {}).get("candidate_model_ids", []) or []))
        self.assertIn(str(get_entity_id(enemy_a.models[0]) or ""), candidate_ids)

        selected_option = None
        enemy_a_model_id = str(get_entity_id(enemy_a.models[0]) or "")
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("target_model_id", "") or "") == enemy_a_model_id:
                selected_option = str(opt.option_id)
                break
        self.assertIsNotNone(selected_option)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            cmd_result = resolve_decision_command(
                game,
                request,
                selected_option,
                player_id=getattr(army1.player, "id", None),
            )
            apply_result = getattr(cmd_result, "value", None)
            self.assertTrue(apply_result.ok, msg=str(apply_result.errors))

        self.assertEqual(applied["a"], [6])
        self.assertEqual(applied["b"], [6])
        self.assertEqual(applied["far"], [])
        self.assertTrue(bomber.has_used_unit_once_per_battle("void_mine"))

        game._on_unit_move_ended_move_over_mortal_wounds(unit=bomber, action="move")
        request_again = _find_quarry_request(game, "void_mine")
        self.assertIsNone(request_again)


if __name__ == "__main__":
    unittest.main()
