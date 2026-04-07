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
        model_count=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Blood Angels", detachment_type="Rage-cursed Onslaught")
    army1.faction_id = "SM"
    army2 = Army.with_detachment("Enemy", detachment_type="Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 5
    p2.command_points = 5
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


class TestRageCursedOnslaughtStratagems(unittest.TestCase):
    def test_a_grim_warning_queues_reaction(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Assault Intercessors", faction_keywords=["BLOOD ANGELS"])
        army1.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models[0].set_location(1.0, 0.0, 0.0, 0.0)

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives.append(objective)
        game._objective_control_snapshot = {objective.location: p1}

        last_model = unit.models[0]
        game.event_system.publish("unit_destroyed", unit=unit, last_model=last_model)
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "A GRIM WARNING" for r in pending))

    def test_a_grim_warning_sets_sticky_control(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Assault Intercessors", faction_keywords=["BLOOD ANGELS"])
        army1.add_unit(unit)

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives.append(objective)

        ok = p1.stratagems.use("A GRIM WARNING", unit=unit, objective=objective)
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, p1)
        self.assertEqual(objective.location.sticky_source, "a_grim_warning")

    def test_deathless_duty_defers_fight_on_death(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Death Company", keywords=["DEATH COMPANY"], faction_keywords=["BLOOD ANGELS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        ok = p1.stratagems.use(
            "DEATHLESS DUTY",
            unit=unit,
            attacking_unit=enemy,
            candidates=[unit],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("deathless_duty_active"))

        model = unit.models[0]
        model._wounds = 0
        unit._handle_model_destroyed(model, game.map)
        pending = getattr(unit, "_deathless_duty_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_deathless_duty_pending_models", []))

    def test_insensate_rampage_grants_fnp(self):
        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit("Death Company", keywords=["DEATH COMPANY"], faction_keywords=["BLOOD ANGELS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)

        ok = p1.stratagems.use("INSENSATE RAMPAGE", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        sr = unit.special_rules
        overrides = sr.get("defensive_fnp_overrides") or []
        self.assertTrue(overrides)
        self.assertEqual(int(overrides[0].get("value", 0) or 0), 5)

    def test_limb_from_limb_red_thirst_bonus(self):
        from warhammer40k_ai.units.wargear import Wargear

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Assault Intercessors", faction_keywords=["BLOOD ANGELS"])
        army1.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)
        unit.round_state.charged_this_round = True
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        ok = p1.stratagems.use("LIMB FROM LIMB", unit=unit, choice="red_thirst", phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(unit.special_rules.get("limb_from_limb_melee_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(unit.special_rules.get("limb_from_limb_melee_ap_bonus", 0) or 0), 1)
        self.assertTrue(unit.is_battle_shocked())

        weapon = Wargear(
            {
                "name": "Test Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = unit.models[0]
        target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_model = target.models[0]
        target_model.parent_unit = target

        ap_val = profile.get_effective_ap(attacker_model, target)
        self.assertEqual(ap_val, -1)

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )
        wound_res = profile._wound_target_with_tracking(target, attacker_model, {"_aura_attack_mods": aura_stub})
        self.assertTrue(any("Limb from Limb" in x for x in wound_res.get("modifiers", [])))

    def test_red_wrath_red_thirst_allows_shoot_and_charge(self):
        from warhammer40k_ai.units.wargear import Wargear

        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit("Assault Intercessors", faction_keywords=["BLOOD ANGELS"])
        army1.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)
        unit.round_state.advanced_this_round = True
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

        ok = p1.stratagems.use("RED WRATH", unit=unit, mode="red_thirst", phase_name="Movement phase", action="advance")
        self.assertTrue(ok)
        self.assertEqual(unit.special_rules.get("red_wrath_mode"), "both")
        self.assertTrue(unit.is_battle_shocked())

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = unit.models[0]

        self.assertTrue(unit.can_shoot_after_advance(profile))
        self.assertTrue(unit.can_charge_after_advance())


if __name__ == "__main__":
    unittest.main()
