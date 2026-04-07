import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        movement="6",
        wounds="2",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": "4",
                "Sv": "4",
                "W": str(wounds),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, movement="6", wounds="2"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        movement=movement,
        wounds=wounds,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    drukhari_army = Army.with_detachment("Drukhari", "Spectacle of Spite")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=drukhari_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    return game, p1, p2, drukhari_army, enemy_army


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game, player, phase_name: str, current_player_index: int):
    game.current_player_index = int(current_player_index)
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.event_system.publish("phase_start", player=player, phase=phase)


def _melee_profile():
    from warhammer40k_ai.units.wargear import Wargear

    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestDrukhariSpectacleOfSpiteStratagems(unittest.TestCase):
    def test_acrobatic_display_queues_and_applies_invulnerable_override(self):
        game, p1, p2, army1, army2 = _build_game()
        wych = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "WYCHES", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(wych)
        army2.add_unit(enemy)
        _place_unit(game, wych, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[wych])

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "ACROBATIC DISPLAY" for r in pending))

        ok = p1.stratagems.use(
            "ACROBATIC DISPLAY",
            unit=wych,
            attacking_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        entries = list(wych.special_rules.get("defensive_invuln_overrides", []) or [])
        self.assertTrue(any(int(e.get("value", 0) or 0) == 5 for e in entries))

    def test_feigned_weakness_allows_shoot_and_charge_after_fall_back(self):
        game, p1, _p2, army1, _army2 = _build_game()
        unit = _make_unit(
            "Kabalites",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        army1.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        unit.round_state.fell_back_this_round = True

        ok = p1.stratagems.use("FEIGNED WEAKNESS", unit=unit, phase_name="Movement phase", action="fall_back")
        self.assertTrue(ok)
        self.assertTrue(unit.has_fell_back_and_shoot())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_deadly_debut_grants_melee_lethal_hits_and_wych_ap_bonus(self):
        game, p1, _p2, army1, army2 = _build_game()
        wych = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "WYCHES", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(wych)
        army2.add_unit(enemy)
        _place_unit(game, wych, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        wych.round_state.charged_this_round = True
        wych.round_state.fought_this_phase = False

        ok = p1.stratagems.use("DEADLY DEBUT", unit=wych, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        attacker = wych.models[0]
        attack_instance = {
            "target_model": enemy.models[0],
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit = profile._hit_target_with_tracking(enemy, attacker, attack_instance)
        self.assertTrue(hit.get("hit"))
        self.assertTrue(bool(attack_instance.get("lethal_hit", False)))
        self.assertEqual(profile.get_effective_ap(attacker, enemy), -1)

    def test_berserk_fugue_defers_and_resolves_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        wych = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(wych)
        army2.add_unit(enemy)
        _place_unit(game, wych, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[wych])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "BERSERK FUGUE" for r in pending))

        ok = p1.stratagems.use(
            "BERSERK FUGUE",
            unit=wych,
            attacking_unit=enemy,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertTrue(bool(wych.special_rules.get("berserk_fugue_active")))

        wych.round_state.fought_this_phase = False
        model = wych.models[0]
        model._wounds = 0
        wych._handle_model_destroyed(model, game.map)
        self.assertIn(model, list(getattr(wych, "_berserk_fugue_pending_models", []) or []))

        with patch.object(wych, "_try_fight_on_death") as mocked:
            wych.begin_attack_resolution()
            wych.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(list(getattr(wych, "_berserk_fugue_pending_models", []) or []))

    def test_preternatural_agility_ignores_modifiers_and_grants_model_pass_through(self):
        from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_ALL

        game, p1, _p2, army1, army2 = _build_game()
        wych = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            movement="6",
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(wych)
        army2.add_unit(enemy)
        _place_unit(game, wych, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        ok = p1.stratagems.use("PRETERNATURAL AGILITY", unit=wych, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertTrue(bool(wych.special_rules.get("preternatural_agility_move_through_models_active")))

        wych.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, -2, source="test_move_penalty"))
        wych.round_state.move_modifier_choice = CHOICE_IGNORE_ALL
        move_value = wych.get_effective_model_characteristic(wych.models[0], "movement")
        self.assertEqual(int(move_value), 6)

        wych.special_rules["advance_roll_modifier"] = -2
        wych.round_state.advance_modifier_choice = CHOICE_IGNORE_ALL
        self.assertEqual(int(wych._apply_advance_roll_modifiers(6)), 6)

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=wych)
        charge_rules = get_validation_rules(MovementType.CHARGE, target_unit=enemy, moving_unit=wych)
        self.assertTrue(bool(move_rules.get("can_move_through_models")))
        self.assertTrue(bool(charge_rules.get("can_move_through_models")))

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        ok = p1.stratagems.use("PRETERNATURAL AGILITY", unit=wych, phase_name="Charge phase")
        self.assertTrue(ok)
        wych.special_rules["charge_roll_modifier"] = -2
        wych.round_state.charge_modifier_choice = CHOICE_IGNORE_ALL
        self.assertEqual(int(game._apply_charge_modifiers(wych, 7, target_unit=enemy)), 7)

    def test_a_challenge_met_queues_and_resolves_out_of_turn_charge_without_bonus(self):
        game, p1, p2, army1, army2 = _build_game()
        wych = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCH CULT", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(wych)
        army2.add_unit(enemy)
        _place_unit(game, wych, 10.0, 10.0)
        _place_unit(game, enemy, 15.0, 10.0)
        wych.can_declare_charge_against = lambda *_args, **_kwargs: True

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="MOVEMENT_PHASE"))

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "A CHALLENGE MET" for r in pending))

        with patch.object(game, "attempt_charge", return_value=True) as charge_mock:
            ok = p1.stratagems.use(
                "A CHALLENGE MET",
                unit=wych,
                enemy_unit=enemy,
                phase_name="Movement phase",
                dequeue=True,
            )
        self.assertTrue(ok)
        charge_mock.assert_called_once()
        self.assertTrue(bool(charge_mock.call_args.kwargs.get("out_of_turn")))
        self.assertFalse(bool(charge_mock.call_args.kwargs.get("count_as_charged", True)))


if __name__ == "__main__":
    unittest.main()
