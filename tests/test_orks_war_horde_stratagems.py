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
        movement="5",
        toughness="5",
        wounds="4",
    ):
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [k.upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness="5"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Orks", "War Horde")
    army1.faction_id = "ORK"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("Orks", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 5
    p2.command_points = 5
    army1.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class _MeleeWargear:
    name = "Choppa"

    @staticmethod
    def is_melee():
        return True

    @staticmethod
    def is_ranged():
        return False


def _melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Choppa",
        {
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


class TestOrksWarHordeStratagems(unittest.TestCase):
    def test_unbridled_carnage_sets_crit_hits_on_5_plus(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        ok = p1.stratagems.use("UNBRIDLED CARNAGE", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        attack_instance = {"_aura_attack_mods": _aura_stub()}
        profile._hit_target_with_tracking(
            enemy,
            unit.models[0],
            attack_instance,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(attack_instance.get("crit_hit"))

    def test_ard_as_nails_applies_wound_penalty(self):
        from warhammer40k_ai.units.wargear import Wargear

        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"], toughness="5")
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "'ARD AS NAILS",
            unit=unit,
            attacker_unit=enemy,
            candidates=[unit],
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        result = profile._wound_target_with_tracking(unit, enemy.models[0], dict(attack_instance))
        self.assertTrue(any("ARD AS NAILS" in str(m).upper() for m in result.get("modifiers", [])))

    def test_ard_as_nails_rejects_grots(self):
        game, p1, p2, army1, army2 = _build_game()
        grots = _make_unit("Gretchin", keywords=["INFANTRY", "GROTS"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(grots)
        army2.add_unit(enemy)
        _place_unit(game, grots, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "'ARD AS NAILS",
            unit=grots,
            attacker_unit=enemy,
            candidates=[grots],
            phase_name="Shooting phase",
        )
        self.assertFalse(ok)

    def test_ere_we_go_adds_advance_and_charge_bonus_until_end_of_turn(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use("ERE WE GO", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)

        advance_mods = unit._collect_advance_roll_modifiers()
        self.assertTrue(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in advance_mods))

        charge_mods = game.get_charge_roll_modifiers(unit, target_unit=enemy)
        self.assertTrue(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in charge_mods))

        game._on_phase_end_cleanup(player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))

        advance_mods_after = unit._collect_advance_roll_modifiers()
        self.assertFalse(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in advance_mods_after))

        charge_mods_after = game.get_charge_roll_modifiers(unit, target_unit=enemy)
        self.assertFalse(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in charge_mods_after))

    def test_orks_is_never_beaten_defers_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "ORKS IS NEVER BEATEN",
            unit=unit,
            attacking_unit=enemy,
            candidates=[unit],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("orks_is_never_beaten_active"))

        model = unit.models[0]
        model._wounds = 0
        unit._handle_model_destroyed(model, game.map)
        pending = getattr(unit, "_orks_is_never_beaten_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_orks_is_never_beaten_pending_models", []))


if __name__ == "__main__":
    unittest.main()
