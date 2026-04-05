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
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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


def _make_unit(name, *, keywords=None, faction_keywords=None, wounds="4"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        wounds=wounds,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("World Eaters", "Cult of Blood")
    army1.faction_id = "WE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    game.turn = 1
    p1.command_points = 10
    p2.command_points = 10
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _destroy_unit(unit, game_map):
    model = unit.models[0]
    model.wounds = 0
    model.die(game_map=game_map)
    return model


class _MeleeWargear:
    name = "Test Blade"

    @staticmethod
    def is_melee():
        return True

    @staticmethod
    def is_ranged():
        return False


class _RangedWargear:
    name = "Test Rifle"

    @staticmethod
    def is_melee():
        return False

    @staticmethod
    def is_ranged():
        return True


def _melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


def _ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Test Rifle",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_RangedWargear(),
    )


class TestWorldEatersCultOfBloodStratagems(unittest.TestCase):
    def test_bloodthirsty_horde_sets_and_clears_phase_flags(self):
        game, p1, _p2, army1, army2 = _build_game()
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(jakhals)
        army2.add_unit(enemy)
        _place_unit(game, jakhals, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("BLOODTHIRSTY HORDE", unit=jakhals, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertTrue(bool(jakhals.special_rules.get("cult_bloodthirsty_horde_active")))
        self.assertTrue(bool(jakhals.special_rules.get("fight_within_3_active")))

        game.event_system.publish("phase_end", player=p1, phase=phase)
        self.assertFalse(bool(jakhals.special_rules.get("cult_bloodthirsty_horde_active")))
        self.assertFalse(bool(jakhals.special_rules.get("fight_within_3_active")))

    def test_bloody_vengeance_queues_and_grants_hit_rerolls_vs_destroyer(self):
        game, p1, p2, army1, army2 = _build_game()
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"])
        titan = _make_unit("World Eaters Titan", keywords=["MONSTER", "TITANIC"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy Destroyer", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(jakhals)
        army1.add_unit(titan)
        army2.add_unit(enemy)
        _place_unit(game, jakhals, 10.0, 10.0)
        _place_unit(game, titan, 14.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        dead_model = _destroy_unit(titan, game.map)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish(
            "unit_destroyed",
            unit=titan,
            last_model=dead_model,
            destroyed_by_unit=enemy,
        )
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "BLOODY VENGEANCE" for r in pending))

        ok = p1.stratagems.use(
            "BLOODY VENGEANCE",
            unit=titan,
            enemy_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        profile = _ranged_profile()
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit = profile._hit_target_with_tracking(enemy, jakhals.models[0], {}, roll_value=1)
        self.assertEqual(int(hit.get("reroll", 0) or 0), 5)
        self.assertIn("Bloody Vengeance", list(hit.get("reroll_full_reasons", []) or []))

    def test_brazen_idol_applies_source_specific_idol_override(self):
        from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

        game, p1, _p2, army1, army2 = _build_game()
        source = _make_unit(
            "Daemon Prince",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["WORLD EATERS"],
        )
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(source)
        army1.add_unit(jakhals)
        army2.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, jakhals, 12.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        mgr = army1.world_eaters_detachments
        self.assertTrue(mgr.activate_idol_of_khorne("BLESSED_BLOOD"))

        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use(
            "BRAZEN IDOL",
            unit=source,
            ability_key="INFINITE_RAGE",
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertTrue(mgr.idols_of_khorne_infinite_rage_applies(jakhals, game_map=game.map))
        self.assertFalse(mgr.idols_of_khorne_blessed_blood_applies(jakhals, game_map=game.map))

        weapon_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False))
        mods = get_aura_attack_modifiers(jakhals, enemy, weapon_profile, game_map=game.map)
        self.assertEqual(int(mods.hit), 1)
        self.assertEqual(int(mods.wound), 1)

    def test_brazen_idol_rejects_invalid_idol_choice(self):
        game, p1, _p2, army1, _army2 = _build_game()
        source = _make_unit(
            "Daemon Prince",
            keywords=["MONSTER", "CHARACTER"],
            faction_keywords=["WORLD EATERS"],
        )
        army1.add_unit(source)
        _place_unit(game, source, 10.0, 10.0)

        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use(
            "BRAZEN IDOL",
            unit=source,
            ability_key="NOT_A_REAL_IDOL",
            phase_name="Command phase",
        )
        self.assertFalse(ok)

    def test_drawn_to_slaughter_adds_strategic_reserve_clone_once_per_battle(self):
        game, p1, p2, army1, army2 = _build_game()
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(jakhals)
        army2.add_unit(enemy)
        _place_unit(game, jakhals, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        dead_model = _destroy_unit(jakhals, game.map)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish(
            "unit_destroyed",
            unit=jakhals,
            last_model=dead_model,
            destroyed_by_unit=enemy,
        )
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "DRAWN TO THE SLAUGHTER" for r in pending))

        before = len(list(army1.units or []))
        ok = p1.stratagems.use("DRAWN TO THE SLAUGHTER", unit=jakhals, phase_name="Fight phase")
        self.assertTrue(ok)
        after = len(list(army1.units or []))
        self.assertEqual(after, before + 1)
        replacements = [u for u in list(army1.units or []) if u is not jakhals and str(getattr(u, "name", "")) == str(jakhals.name)]
        self.assertTrue(replacements)
        replacement = replacements[-1]
        self.assertEqual(str(getattr(replacement, "reserve_status", "") or ""), "strategic_reserves")
        self.assertTrue(bool(getattr(replacement, "deployed", False)))
        self.assertNotIn(replacement, list(game.map.units or []))

        p1.stratagems._used_stratagems_this_phase.clear()
        self.assertFalse(p1.stratagems.use("DRAWN TO THE SLAUGHTER", unit=jakhals, phase_name="Fight phase"))

    def test_fail_not_the_blood_god_rerolls_ones_or_all_hits(self):
        game, p1, _p2, army1, army2 = _build_game()
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(jakhals)
        army2.add_unit(enemy)
        _place_unit(game, jakhals, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("FAIL NOT THE BLOOD GOD", unit=jakhals, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit = profile._hit_target_with_tracking(enemy, jakhals.models[0], {}, roll_value=1)
        self.assertEqual(int(hit.get("reroll", 0) or 0), 5)
        self.assertTrue(any("Fail Not the Blood God" in str(r) for r in list(hit.get("reroll_value_reasons", []) or [])))

        source = _make_unit("Daemon Prince", keywords=["MONSTER"], faction_keywords=["WORLD EATERS"])
        army1.add_unit(source)
        _place_unit(game, source, 14.0, 10.0)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit2 = profile._hit_target_with_tracking(enemy, jakhals.models[0], {}, roll_value=2)
        self.assertEqual(int(hit2.get("reroll", 0) or 0), 5)
        self.assertIn("Fail Not the Blood God", list(hit2.get("reroll_full_reasons", []) or []))

    def test_in_the_shadow_of_brass_idols_queues_and_applies_dynamic_fnp(self):
        game, p1, p2, army1, army2 = _build_game()
        jakhals = _make_unit("Jakhals", keywords=["INFANTRY", "JAKHALS"], faction_keywords=["WORLD EATERS"], wounds="2")
        shooter = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(jakhals)
        army2.add_unit(shooter)
        _place_unit(game, jakhals, 10.0, 10.0)
        _place_unit(game, shooter, 18.0, 10.0)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)
        game.event_system.publish("shooting_targets_selected", attacking_unit=shooter, target_units=[jakhals])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "IN THE SHADOW OF BRASS IDOLS" for r in pending))

        ok = p1.stratagems.use(
            "IN THE SHADOW OF BRASS IDOLS",
            unit=jakhals,
            attacking_unit=shooter,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        profile = _ranged_profile()
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
            dmg = profile._apply_damage_with_tracking(
                jakhals.models[0],
                shooter.models[0],
                1,
                False,
                attack_instance={},
            )
        self.assertEqual(int(dmg.get("fnp_saves", 0) or 0), 1)
        self.assertEqual(int(dmg.get("fnp_rolls", [{}])[0].get("needed", 0) or 0), 6)

        source = _make_unit("Daemon Prince", keywords=["MONSTER"], faction_keywords=["WORLD EATERS"])
        army1.add_unit(source)
        _place_unit(game, source, 14.0, 10.0)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
            dmg2 = profile._apply_damage_with_tracking(
                jakhals.models[0],
                shooter.models[0],
                1,
                False,
                attack_instance={},
            )
        self.assertEqual(int(dmg2.get("fnp_saves", 0) or 0), 1)
        self.assertEqual(int(dmg2.get("fnp_rolls", [{}])[0].get("needed", 0) or 0), 5)

        game.event_system.publish("phase_end", player=p2, phase=phase)
        self.assertFalse(bool(jakhals.special_rules.get("cult_shadow_brass_idols_active")))


if __name__ == "__main__":
    unittest.main()
