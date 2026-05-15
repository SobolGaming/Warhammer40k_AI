import copy
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("World Eaters", "Khorne Daemonkin")
    army1.faction_id = "WE"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 3
    p2.command_points = 3
    return game, p1, p2, army1, army2


class TestKhorneDaemonkinStratagems(unittest.TestCase):
    def test_daemonic_fury_grants_lance_and_twin_linked(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, p1, _p2, army1, army2 = _build_game()
        bl_unit = _make_unit("Bloodletters", keywords=["BLOOD LEGIONS", "INFANTRY"])
        we_unit = _make_unit("World Eaters", faction_keywords=["WORLD EATERS"])
        target = _make_unit("Target", faction_keywords=["ENEMY"])
        army1.add_unit(bl_unit)
        army1.add_unit(we_unit)
        army2.add_unit(target)

        bl_unit.deployed = True
        we_unit.deployed = True
        target.deployed = True
        bl_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        we_unit.models[0].set_location(9.0, 5.0, 0.0, 0.0)
        target.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        game.map.place_unit(bl_unit)
        game.map.place_unit(we_unit)
        game.map.place_unit(target)

        army1.world_eaters_detachments.blood_tithe_active.add("DAEMONIC_RAGE")
        game.current_player_index = 0
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use(
            "DAEMONIC FURY",
            target_unit=bl_unit,
            world_eaters_unit=we_unit,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        sr = we_unit.special_rules
        self.assertTrue(sr.get("daemonic_fury_lance_active"))
        self.assertTrue(sr.get("daemonic_fury_twin_linked_active"))

        we_unit.round_state.charged_this_round = True
        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        attacker = we_unit.models[0]
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
        self.assertIn("+1 to wound from Lance (Daemonic Fury)", res.get("modifiers", []))

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
            res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
        self.assertTrue(res.get("wound"))
        self.assertEqual(res.get("reroll"), 4)
        self.assertIn("Twin-linked (Daemonic Fury)", res.get("special_effects", []))

    def test_daemontide_returns_infantry_models(self):
        game, p1, _p2, army1, _army2 = _build_game()
        we_unit = _make_unit("World Eaters", faction_keywords=["WORLD EATERS"])
        bl_unit = _make_unit("Bloodletters", keywords=["BLOOD LEGIONS", "INFANTRY"])
        army1.add_unit(we_unit)
        army1.add_unit(bl_unit)

        we_unit.deployed = True
        bl_unit.deployed = True
        we_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        bl_unit.models[0].set_location(9.0, 5.0, 0.0, 0.0)
        game.map.place_unit(we_unit)
        game.map.place_unit(bl_unit)

        lost = []
        for _ in range(3):
            m = copy.deepcopy(bl_unit.models[0])
            try:
                import uuid
                m.id = str(uuid.uuid4())
            except Exception:
                pass
            m.parent_unit = bl_unit
            lost.append(m)
        bl_unit.models_lost = lost

        game.current_player_index = 0
        phase = SimpleNamespace(name="COMMAND_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=p1, phase=phase)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            ok = p1.stratagems.use(
                "DAEMONTIDE",
                target_unit=we_unit,
                blood_legions_unit=bl_unit,
                phase_name="Command phase",
            )
        self.assertTrue(ok)
        self.assertEqual(len(bl_unit.models_lost), 0)
        self.assertEqual(len(bl_unit.models), 4)

    def test_daemontide_tool_action_context_reuses_support_scan_until_loss_state_changes(self):
        game, p1, _p2, army1, _army2 = _build_game()
        we_unit = _make_unit("World Eaters", faction_keywords=["WORLD EATERS"])
        bl_unit = _make_unit("Bloodletters", keywords=["BLOOD LEGIONS", "INFANTRY"])
        army1.add_unit(we_unit)
        army1.add_unit(bl_unit)
        we_unit.deployed = True
        bl_unit.deployed = True
        we_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        bl_unit.models[0].set_location(9.0, 5.0, 0.0, 0.0)
        game.map.place_unit(we_unit)
        game.map.place_unit(bl_unit)
        bl_unit.models_lost = [copy.deepcopy(bl_unit.models[0])]
        game.current_player_index = 0
        game.phase = SimpleNamespace(name="COMMAND_PHASE")

        calls = {"supports": 0}

        def counted_supports(_unit):
            calls["supports"] += 1
            return [bl_unit]

        p1.stratagems._we_khorne_daemonkin_daemontide_supports = counted_supports

        first = p1.stratagems._we_khorne_daemonkin_tool_action_context("DAEMONTIDE")
        second = p1.stratagems._we_khorne_daemonkin_tool_action_context("DAEMONTIDE")
        self.assertEqual(first["candidates"], second["candidates"])
        self.assertEqual(calls["supports"], 1)

        bl_unit.models_lost.append(copy.deepcopy(bl_unit.models[0]))
        third = p1.stratagems._we_khorne_daemonkin_tool_action_context("DAEMONTIDE")
        self.assertTrue(third["candidates"])
        self.assertEqual(calls["supports"], 2)

    def test_blessing_of_burning_blood_sets_invulnerable(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, p1, p2, army1, army2 = _build_game()
        bl_unit = _make_unit("Bloodletters", keywords=["BLOOD LEGIONS", "INFANTRY"])
        we_unit = _make_unit("World Eaters", faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", faction_keywords=["ENEMY"])
        army1.add_unit(bl_unit)
        army1.add_unit(we_unit)
        army2.add_unit(enemy)

        bl_unit.deployed = True
        we_unit.deployed = True
        enemy.deployed = True
        bl_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        we_unit.models[0].set_location(9.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        game.map.place_unit(bl_unit)
        game.map.place_unit(we_unit)
        game.map.place_unit(enemy)

        game.current_player_index = 1
        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)

        ok = p1.stratagems.use(
            "BLESSING OF BURNING BLOOD",
            target_unit=bl_unit,
            world_eaters_unit=we_unit,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        ranged_parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )
        save_res = profile._save_with_tracking(
            we_unit.models[0],
            {"attacker_unit": enemy},
            ap=-4,
        )
        self.assertEqual(int(save_res.get("final_save", 0)), 5)

    def test_blessing_of_burning_blood_uses_boon_of_blood(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        game, p1, p2, army1, army2 = _build_game()
        bl_unit = _make_unit("Bloodletters", keywords=["BLOOD LEGIONS", "INFANTRY"])
        we_unit = _make_unit("World Eaters", faction_keywords=["WORLD EATERS"])
        enemy = _make_unit("Enemy", faction_keywords=["ENEMY"])
        army1.add_unit(bl_unit)
        army1.add_unit(we_unit)
        army2.add_unit(enemy)

        bl_unit.deployed = True
        we_unit.deployed = True
        enemy.deployed = True
        bl_unit.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        we_unit.models[0].set_location(9.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        game.map.place_unit(bl_unit)
        game.map.place_unit(we_unit)
        game.map.place_unit(enemy)

        army1.world_eaters_detachments.blood_tithe_active.add("BOON_OF_BLOOD")
        game.current_player_index = 1
        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=p2, phase=phase)

        ok = p1.stratagems.use(
            "BLESSING OF BURNING BLOOD",
            target_unit=bl_unit,
            world_eaters_unit=we_unit,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        ranged_parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )
        save_res = profile._save_with_tracking(
            we_unit.models[0],
            {"attacker_unit": enemy},
            ap=-4,
        )
        self.assertEqual(int(save_res.get("final_save", 0)), 4)


if __name__ == "__main__":
    unittest.main()
