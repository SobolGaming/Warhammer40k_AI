import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        wounds="4",
        model_count=1,
    ):
        count = int(model_count or 1)
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": wounds,
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


def _make_unit(name, *, keywords=None, faction_keywords=None, wounds="4", model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        wounds=wounds,
        model_count=model_count,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(phase_name: str = "FIGHT_PHASE"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    as_army = Army("Adepta Sororitas", "Hallowed Martyrs")
    as_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("AS", control=PlayerControl.LOCAL, army=as_army)
    p2 = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    game.phase = SimpleNamespace(name=phase_name)
    game.turn = 1
    p1.command_points = 8
    p2.command_points = 8
    return game, p1, p2, as_army, enemy_army


def _place_unit(game, unit, x: float, y: float):
    unit.deployed = True
    unit.reserve_status = "deployed"
    for i, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (i * 0.05), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _phase_start(game, acting_player, phase_name: str):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    try:
        game.current_player_index = list(game.players).index(acting_player)
    except Exception:
        pass
    game.event_system.publish("phase_start", player=acting_player, phase=phase)
    return phase


class TestAdeptaSororitasHallowedMartyrsStratagems(unittest.TestCase):
    def test_righteous_vengeance_grants_melee_rerolls(self):
        game, p1, _p2, as_army, enemy_army = _build_game("FIGHT_PHASE")
        sisters = _make_unit(
            "Battle Sisters",
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        as_army.add_unit(sisters)
        enemy_army.add_unit(enemy)
        _place_unit(game, sisters, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        _phase_start(game, p1, "FIGHT_PHASE")

        enemy.is_below_half_strength = lambda: True
        ok = p1.stratagems.use("RIGHTEOUS VENGEANCE", unit=sisters, phase_name="Fight phase")
        self.assertTrue(ok)

        hit_mods = sisters.get_unit_hit_reroll_modifiers("melee", target=enemy)
        wound_mods = sisters.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full")))
        self.assertTrue(bool(wound_mods.get("reroll_wound_full")))

        enemy.is_below_half_strength = lambda: False
        wound_mods_not_half = sisters.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertFalse(bool(wound_mods_not_half.get("reroll_wound_full")))

    def test_suffering_and_sacrifice_restricts_fight_targets(self):
        from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager

        game, p1, p2, as_army, enemy_army = _build_game("FIGHT_PHASE")
        marked = _make_unit(
            "Sacrifice Unit",
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        other = _make_unit(
            "Other Unit",
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        enemy = _make_unit("Enemy Fighter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        as_army.add_unit(marked)
        as_army.add_unit(other)
        enemy_army.add_unit(enemy)
        _place_unit(game, marked, 10.0, 10.0)
        _place_unit(game, other, 13.5, 10.0)
        _place_unit(game, enemy, 11.75, 10.0)
        _phase_start(game, p2, "FIGHT_PHASE")

        ok = p1.stratagems.use("SUFFERING AND SACRIFICE", unit=marked, phase_name="Fight phase")
        self.assertTrue(ok)

        fight_manager = FightPhaseManager(game)
        eligible = fight_manager._get_eligible_targets(enemy)
        self.assertIn(marked, eligible)
        self.assertNotIn(other, eligible)
        self.assertEqual(len(eligible), 1)

    def test_spirit_of_the_martyr_defers_fight_on_death(self):
        game, p1, p2, as_army, enemy_army = _build_game("FIGHT_PHASE")
        sisters = _make_unit(
            "Celestians",
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        enemy = _make_unit("Enemy Fighter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        as_army.add_unit(sisters)
        enemy_army.add_unit(enemy)
        _place_unit(game, sisters, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        _phase_start(game, p2, "FIGHT_PHASE")

        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[sisters])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "SPIRIT OF THE MARTYR" for r in pending))

        ok = p1.stratagems.use(
            "SPIRIT OF THE MARTYR",
            unit=sisters,
            attacking_unit=enemy,
            candidates=[sisters],
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        model = sisters.models[0]
        sisters.round_state.fought_this_phase = False
        sisters._handle_model_destroyed(model, game.map)
        self.assertIn(model, list(getattr(sisters, "_spirit_of_martyr_pending_models", []) or []))

        with patch.object(sisters, "_try_fight_on_death", return_value=True) as mocked:
            sisters.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(bool(getattr(sisters, "_spirit_of_martyr_pending_models", [])))

    def test_praise_the_fallen_reactive_shooting(self):
        game, p1, p2, as_army, enemy_army = _build_game("SHOOTING_PHASE")
        sisters = _make_unit(
            "Battle Sisters",
            keywords=["INFANTRY", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
            model_count=2,
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        as_army.add_unit(sisters)
        enemy_army.add_unit(enemy)
        _place_unit(game, sisters, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)
        _phase_start(game, p2, "SHOOTING_PHASE")

        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[sisters])
        sisters.models[0].wounds = 0
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={sisters: 1})

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "PRAISE THE FALLEN" for r in pending))

        with patch.object(game, "_queue_setup_reactive_shooting_decision", return_value={"queued": True}) as queue_mock:
            ok = p1.stratagems.use(
                "PRAISE THE FALLEN",
                unit=sisters,
                enemy_unit=enemy,
                candidates=[sisters],
                phase_name="Shooting phase",
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(queue_mock.call_count, 1)

    def test_sanctified_immolation_auto_triggers_deadly_demise(self):
        from warhammer40k_ai.utility.dice import DiceCollection

        game, p1, _p2, as_army, _enemy_army = _build_game("SHOOTING_PHASE")
        vehicle = _make_unit(
            "Immolator",
            keywords=["VEHICLE", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        as_army.add_unit(vehicle)
        _place_unit(game, vehicle, 10.0, 10.0)
        _phase_start(game, p1, "SHOOTING_PHASE")

        vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
        model = vehicle.models[0]
        ok = p1.stratagems.use(
            "SANCTIFIED IMMOLATION",
            destroyed_unit=vehicle,
            destroyed_model=model,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        self.assertTrue(bool(getattr(model, "_sanctified_immolation_auto_trigger_once", False)))

        with patch.object(vehicle, "_apply_deadly_demise_explosion") as explosion_mock:
            vehicle._trigger_deadly_demise(model, game.map)
        self.assertEqual(explosion_mock.call_count, 1)

    def test_divine_intervention_discard_and_return(self):
        game, p1, p2, as_army, _enemy_army = _build_game("FIGHT_PHASE")
        character = _make_unit(
            "Canoness",
            keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        as_army.add_unit(character)
        _place_unit(game, character, 10.0, 10.0)
        _phase_start(game, p2, "FIGHT_PHASE")

        acts_mgr = as_army.acts_of_faith
        acts_mgr.miracle_dice = [1, 2, 5]

        model = character.models[0]
        destroyed_position = model.get_location()
        ok = p1.stratagems.use(
            "DIVINE INTERVENTION",
            unit=character,
            destroyed_model=model,
            destroyed_position=destroyed_position,
            miracle_dice_to_discard=[1, 2],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(list(acts_mgr.miracle_dice), [5])

        model.wounds = 0
        with patch("warhammer40k_ai.rules.stratagems_adepta_sororitas.dice_module.get_roll", return_value=2):
            p1.stratagems._resolve_hallowed_martyrs_phase_end(
                player=p2,
                phase=SimpleNamespace(name="FIGHT_PHASE"),
            )
        self.assertGreaterEqual(int(getattr(model, "wounds", 0) or 0), 1)

    def test_divine_intervention_requires_discard_values(self):
        game, p1, p2, as_army, _enemy_army = _build_game("FIGHT_PHASE")
        character = _make_unit(
            "Canoness",
            keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
            faction_keywords=["ADEPTA SORORITAS"],
        )
        as_army.add_unit(character)
        _place_unit(game, character, 10.0, 10.0)
        _phase_start(game, p2, "FIGHT_PHASE")

        as_army.acts_of_faith.miracle_dice = [3, 4]
        model = character.models[0]
        ok = p1.stratagems.use(
            "DIVINE INTERVENTION",
            unit=character,
            destroyed_model=model,
            phase_name="Fight phase",
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
