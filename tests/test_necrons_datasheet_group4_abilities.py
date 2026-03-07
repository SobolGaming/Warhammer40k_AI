import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers, get_aura_strength_bonus


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        datasheet_id=None,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        attached_to=None,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name,
    *,
    datasheet_id=None,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    attached_to=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        attached_to=attached_to,
    )
    return Unit(datasheet)


def _build_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Necrons", "Det")
    army1.faction_id = "NEC"
    army2 = Army("Enemy", "Det")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


def _deploy_pair(game, army1, army2, friendly, enemy, *, friendly_xy=(0.0, 0.0), enemy_xy=(12.0, 0.0)):
    army1.add_unit(friendly)
    army2.add_unit(enemy)
    friendly.deployed = True
    enemy.deployed = True
    friendly.models[0].set_location(float(friendly_xy[0]), float(friendly_xy[1]), 0.0, 0.0)
    enemy.models[0].set_location(float(enemy_xy[0]), float(enemy_xy[1]), 0.0, 0.0)
    game.map.units = [friendly, enemy]


class TestNecronsDatasheetGroup4Abilities(unittest.TestCase):
    def test_technomancer_parses_end_movement_phase_model_repair_rule(self):
        ability = {
            "name": "Technomancer",
            "description": (
                "At the end of your Movement phase, you can select one friendly NECRONS model within 6\" of the bearer. "
                "That model regains up to D3 lost wounds. Each model can only be selected for this ability once per turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit(
            "Technomancer",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
        )
        rule = source.get_command_phase_vehicle_repair_hit_bonus_rule()

        self.assertIsNotNone(rule)
        self.assertEqual(str(rule.get("source", "")), "Technomancer")
        self.assertEqual(str(rule.get("phase", "")), "MOVEMENT_PHASE")
        self.assertEqual(str(rule.get("selection_kind", "")), "model")
        self.assertEqual(str(rule.get("limit_scope", "")), "model")
        self.assertTrue(bool(rule.get("limit_once_per_turn", False)))
        self.assertEqual(str(rule.get("target_keyword", "")), "NECRONS")
        self.assertEqual(int(rule.get("range", 0) or 0), 6)
        self.assertEqual(str(rule.get("heal_roll", "")).upper(), "D3")

    def test_technomancer_queues_and_applies_model_heal_once_per_turn(self):
        ability = {
            "name": "Technomancer",
            "description": (
                "At the end of your Movement phase, you can select one friendly NECRONS model within 6\" of the bearer. "
                "That model regains up to D3 lost wounds. Each model can only be selected for this ability once per turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit(
            "Technomancer",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
        )
        target = _make_unit("Necron Warriors", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.turn = 2
        game.rebuild_entity_registry()

        before = int(target.models[0].wounds)
        target.models[0].wounds = before - 1

        player = game.players[0]
        game._on_phase_start_master_of_mechanisms(player=player, phase=game.phase)

        req = next(
            r
            for r in list(game.decision_queue.list() or [])
            if str((r.context or {}).get("ability", "")) == "master_of_mechanisms"
        )
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((req.context or {}).get("phase", "")), "Movement phase")
        self.assertEqual(str((req.context or {}).get("selection_kind", "")), "model")
        self.assertEqual(str((req.context or {}).get("limit_scope", "")), "model")

        target_unit_id = str(get_entity_id(target) or "")
        option = next(
            opt
            for opt in list(req.options or [])
            if str((opt.payload or {}).get("target_unit_id", "")) == target_unit_id
        )
        target_model_id = str((option.payload or {}).get("target_model_id", "") or "")
        self.assertTrue(bool(target_model_id))
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            result = resolve_decision_command(game, req, option.option_id, player_id=player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(target.models[0].wounds), before)

        msr = getattr(target.models[0], "special_rules", {}) or {}
        self.assertEqual(str(msr.get("master_of_mechanisms_selected_turn_owner", "")), str(player.id))
        self.assertEqual(int(msr.get("master_of_mechanisms_selected_turn", 0) or 0), 2)

        game._on_phase_start_master_of_mechanisms(player=player, phase=game.phase)
        next_req = next(
            r
            for r in list(game.decision_queue.list() or [])
            if str((r.context or {}).get("ability", "")) == "master_of_mechanisms"
        )
        payload_ids = [str((opt.payload or {}).get("target_model_id", "")) for opt in list(next_req.options or [])]
        self.assertNotIn(target_model_id, payload_ids)

    def test_ancient_collector_sticky_objective_requires_leading(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        ability = {
            "name": "Ancient Collector",
            "description": (
                "While this model is leading a unit, at the end of your Command phase, if that unit is within range of an "
                "objective marker you control, it remains under your control, even if you have no models within range of it, "
                "until your opponent controls it at start or end of any turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, _army2 = _build_game()
        trazyn = _make_unit(
            "Trazyn The Infinite",
            datasheet_id="trazyn_ds",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
            attached_to=["warriors_ds"],
        )
        bodyguard = _make_unit(
            "Necron Warriors",
            datasheet_id="warriors_ds",
            keywords=["NECRONS", "INFANTRY"],
            model_count=2,
        )
        army1.add_unit(trazyn)
        army1.add_unit(bodyguard)
        trazyn.deployed = True
        bodyguard.deployed = True
        bodyguard.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        trazyn.models[0].set_location(0.5, 0.0, 0.0, 0.0)
        trazyn.attach_to_unit(bodyguard)

        objective_while_leading = Objective(
            name="Obj Lead",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0),
        )
        game.map.objectives = [objective_while_leading]
        game.map.units = [trazyn, bodyguard]
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 1

        player = game.players[0]
        game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        self.assertIs(objective_while_leading.location.sticky_controller, player)

        trazyn.detach_from_unit()
        trazyn.models[0].set_location(30.0, 30.0, 0.0, 0.0)
        objective_not_leading = Objective(
            name="Obj Solo",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(5.0, 0.0, 0.0, control_radius=3.0),
        )
        game.map.objectives = [objective_not_leading]

        game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        self.assertIsNone(objective_not_leading.location.sticky_controller)

    def test_surrogate_hosts_replaces_model_and_transfers_leader(self):
        ability = {
            "name": "Surrogate Hosts",
            "description": (
                "At the start of your Command phase, if this model is on the battlefield, you can select one other friendly "
                "Necrons Infantry Character model on the battlefield (excluding Skorpekh Lord or Epic Hero models). "
                "The selected model is destroyed (ignoring any rules that are triggered when a model is destroyed) and this model "
                "is put in its place, with all of its wounds remaining (if the selected model was leading a unit, this model now "
                "attaches to that unit as its Leader)."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 2

        source_bodyguard = _make_unit(
            "Lychguard",
            datasheet_id="lychguard_ds",
            keywords=["NECRONS", "INFANTRY"],
            model_count=3,
        )
        trazyn = _make_unit(
            "Trazyn The Infinite",
            datasheet_id="trazyn_ds",
            abilities=[ability],
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
            attached_to=["lychguard_ds", "immortals_ds"],
        )
        target_bodyguard = _make_unit(
            "Immortals",
            datasheet_id="immortals_ds",
            keywords=["NECRONS", "INFANTRY"],
            model_count=3,
        )
        target_leader = _make_unit(
            "Overlord",
            datasheet_id="overlord_ds",
            keywords=["NECRONS", "INFANTRY", "CHARACTER"],
            attached_to=["immortals_ds"],
        )
        enemy = _make_unit("Enemy")

        army1.add_unit(source_bodyguard)
        army1.add_unit(trazyn)
        army1.add_unit(target_bodyguard)
        army1.add_unit(target_leader)
        army2.add_unit(enemy)

        for unit in [source_bodyguard, trazyn, target_bodyguard, target_leader, enemy]:
            unit.deployed = True
            unit.reserve_status = "deployed"
            unit.embarked_in = None

        source_bodyguard.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        trazyn.models[0].set_location(0.2, 0.0, 0.0, 0.0)
        target_bodyguard.models[0].set_location(8.0, 0.0, 0.0, 0.0)
        target_leader.models[0].set_location(8.2, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(40.0, 0.0, 0.0, 0.0)

        trazyn.attach_to_unit(source_bodyguard)
        target_leader.attach_to_unit(target_bodyguard)

        game.map.units = [source_bodyguard, trazyn, target_bodyguard, target_leader, enemy]
        game.rebuild_entity_registry()

        target_model = target_leader.models[0]
        target_model_id = str(get_entity_id(target_model) or "")
        target_location = target_model.get_location()

        game.start_command_phase()
        req = next(
            r
            for r in list(game.decision_queue.list() or [])
            if str((r.context or {}).get("ability", "")) == "surrogate_hosts"
        )
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((req.context or {}).get("ability_name", "")), "Surrogate Hosts")

        none_option = next(
            opt for opt in list(req.options or []) if str((opt.payload or {}).get("action", "") or "") == "skip"
        )
        self.assertIsNotNone(none_option)

        selected_option = next(
            opt
            for opt in list(req.options or [])
            if str((opt.payload or {}).get("target_model_id", "") or "") == target_model_id
        )
        result = resolve_decision_command(game, req, selected_option.option_id, player_id=game.players[0].id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        self.assertEqual(len(list(target_leader.models or [])), 0)
        self.assertNotIn(target_leader, list(getattr(target_bodyguard, "attached_leaders", []) or []))
        self.assertIn(trazyn, list(getattr(target_bodyguard, "attached_leaders", []) or []))
        self.assertIs(trazyn.attached_to, target_bodyguard)
        self.assertNotIn(trazyn, list(getattr(source_bodyguard, "attached_leaders", []) or []))

        moved_location = trazyn.models[0].get_location()
        self.assertAlmostEqual(float(moved_location[0]), float(target_location[0]), places=4)
        self.assertAlmostEqual(float(moved_location[1]), float(target_location[1]), places=4)

    def test_fabricator_claw_array_aura_grants_vehicle_fnp(self):
        ability = {
            "name": "Fabricator Claw Array (Aura)",
            "description": (
                "While a friendly Necrons Vehicle unit is within 6\" of the bearer, "
                "that unit has the Feel No Pain 6+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Canoptek Spyders", abilities=[ability], keywords=["NECRONS"])
        vehicle = _make_unit("Vehicle", keywords=["NECRONS", "VEHICLE"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(vehicle)
        army2.add_unit(enemy)
        source.deployed = True
        vehicle.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(30.0, 0.0, 0.0, 0.0)
        game.map.units = [source, vehicle, enemy]

        fnp = list(vehicle.has_feel_no_pain())
        self.assertTrue(any(int(v) == 6 for v, _c in fnp))

    def test_gloom_prism_aura_grants_conditional_fnp(self):
        ability = {
            "name": "Gloom Prism (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the "
                "Feel No Pain 5+ ability against mortal wounds and Psychic Attacks."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Canoptek Spyders", abilities=[ability], keywords=["NECRONS"])
        target = _make_unit("Necron Unit", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 5 and "mortal" in str(c or "").lower() for v, c in fnp))

    def test_nullstone_field_generator_aura_grants_conditional_fnp(self):
        ability = {
            "name": "Nullstone Field Generator (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the "
                "Feel No Pain 5+ ability against mortal wounds and Psychic Attacks."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Nekrosor", abilities=[ability], keywords=["NECRONS"])
        target = _make_unit("Necron Unit", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 5 and "psychic" in str(c or "").lower() for v, c in fnp))

    def test_reanimation_nodes_aura_grants_infantry_fnp(self):
        ability = {
            "name": "Reanimation Nodes (Aura)",
            "description": (
                "While a friendly Necrons Infantry unit is within 6\" of this Fortification, "
                "models in that unit have Feel No Pain 6+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("Convergence Of Dominion", abilities=[ability], keywords=["NECRONS", "FORTIFICATION"])
        target = _make_unit("Infantry", keywords=["NECRONS", "INFANTRY"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(22.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        fnp = list(target.has_feel_no_pain())
        self.assertTrue(any(int(v) == 6 for v, _c in fnp))

    def test_ancient_cover_registers_fortification_cover_rule(self):
        ability = {
            "name": "Ancient Cover",
            "description": (
                "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model "
                "in the attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit("Convergence Of Dominion", abilities=[ability], keywords=["NECRONS", "FORTIFICATION"])
        rule = source.get_fortification_cover_rule()

        self.assertIsNotNone(rule)
        self.assertEqual("Ancient Cover", rule.get("source"))

    def test_relentless_march_adds_move_within_szarekh_aura(self):
        ability = {
            "name": "Relentless March (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, "
                "add 2\" to the Move characteristic of models in that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        target = _make_unit("Necron Unit", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        effective_move = target.get_effective_model_characteristic(target.models[0], "movement", game_map=game.map)
        self.assertEqual(int(effective_move), 8)

    def test_the_silent_king_improves_leadership_within_szarekh_aura(self):
        ability = {
            "name": "The Silent King",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, "
                "improve that unit's Leadership characteristic by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        target = _make_unit("Necron Unit", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        army1.add_unit(source)
        army1.add_unit(target)
        army2.add_unit(enemy)
        source.deployed = True
        target.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [source, target, enemy]

        effective_ld = target.get_effective_model_characteristic(target.models[0], "leadership", game_map=game.map)
        self.assertEqual(int(effective_ld), 6)

    def test_phaeron_of_the_stars_grants_hit_and_wound_reroll_ones(self):
        ability = {
            "name": "Phaeron of the Stars (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, each time a model in that "
                "unit makes an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        attacker = _make_unit("Attacker", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")
        _deploy_pair(game, army1, army2, attacker, enemy, friendly_xy=(4.0, 0.0), enemy_xy=(12.0, 0.0))
        army1.add_unit(source)
        source.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [source, attacker, enemy]

        ranged_parent = SimpleNamespace(is_melee=lambda: False, is_ranged=lambda: True)
        profile = SimpleNamespace(parent_wargear=ranged_parent)
        mods = get_aura_attack_modifiers(attacker, enemy, profile, game_map=game.map)
        self.assertTrue(bool(mods.reroll_hit_ones))
        self.assertTrue(bool(mods.reroll_wound_ones))

    def test_phaeron_of_the_blades_grants_melee_strength_and_charge_reroll(self):
        ability = {
            "name": "Phaeron of the Blades (Aura)",
            "description": (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, you can re-roll Charge rolls "
                "made for that unit and each time a model in that unit makes a melee attack, add 1 to the Strength "
                "characteristic of that attack."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        source = _make_unit("The Silent King", abilities=[ability], keywords=["NECRONS"])
        source.models[0].name = "Szarekh"
        attacker = _make_unit("Attacker", keywords=["NECRONS"])
        enemy = _make_unit("Enemy")

        _deploy_pair(game, army1, army2, attacker, enemy, friendly_xy=(5.0, 0.0), enemy_xy=(12.0, 0.0))
        army1.add_unit(source)
        source.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [source, attacker, enemy]

        melee_parent = SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False)
        profile = SimpleNamespace(parent_wargear=melee_parent)
        strength_bonus, _reasons = get_aura_strength_bonus(attacker, profile, game_map=game.map)
        self.assertEqual(int(strength_bonus), 1)
        self.assertTrue(bool(attacker.can_reroll_charge_roll(game_map=game.map)))


if __name__ == "__main__":
    unittest.main()
