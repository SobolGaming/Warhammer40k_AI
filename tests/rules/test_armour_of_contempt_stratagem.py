import unittest
from types import SimpleNamespace


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


def _make_unit(name, *, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


class _Game:
    def __init__(self, active_player):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self.map = SimpleNamespace()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")

    def get_current_player(self):
        return self._current_player


class TestArmourOfContemptStratagem(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        target = _make_unit(
            "Target",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army.add_unit(target)

        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"
        attacker = _make_unit("Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_army.add_unit(attacker)

        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)
        game = _Game(active_player=enemy_player)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 2
        enemy_player.command_points = 2

        target.deployed = True
        attacker.deployed = True
        return player, enemy_player, target, attacker, game

    def _start_shooting_phase(self, game, active_player):
        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=active_player, phase=phase)

    def test_queues_reaction_on_targets_selected(self):
        player, enemy_player, target, attacker, game = self._build_env()
        manager = player.stratagems
        self._start_shooting_phase(game, enemy_player)

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )

        pending = manager.get_pending_reactions()
        self.assertTrue(any((r.get("stratagem", "") or "") == "ARMOUR OF CONTEMPT" for r in pending))

    def test_ap_worsen_clears_after_attacks_resolved(self):
        from warhammer40k_ai.units.wargear import Wargear

        player, enemy_player, target, attacker, game = self._build_env()
        self._start_shooting_phase(game, enemy_player)

        ok = player.stratagems.use(
            "ARMOUR OF CONTEMPT",
            unit=target,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-2",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attacker_model = attacker.models[0]

        self.assertEqual(profile.get_effective_ap(attacker_model, target), -1)

        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)
        self.assertEqual(profile.get_effective_ap(attacker_model, target), -2)


if __name__ == "__main__":
    unittest.main()
