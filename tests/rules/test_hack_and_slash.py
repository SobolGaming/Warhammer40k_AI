import unittest
from types import SimpleNamespace


class _TestUnit:
    def __init__(self):
        self.name = "Khorne Berzerkers"
        self.keywords = ["Khorne", "Berzerkers"]
        self.faction_keywords = ["World Eaters"]
        self.special_rules = {}
        self.deployed = True
        self.round_state = SimpleNamespace(charged_this_round=True, fought_this_phase=False)
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def is_alive(self):
        return True

    def is_battle_shocked(self):
        return False

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]


class _Game:
    def __init__(self, player):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self._player = player
        self.turn = 1
        self.phase = SimpleNamespace(name="FIGHT_PHASE")

    def get_current_player(self):
        return self._player


class TestHackAndSlash(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = _TestUnit()
        army.add_unit(unit)
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game = _Game(player)
        player.set_game(game)
        player.command_points = 1
        return player, unit, game

    def test_use_sets_ap_bonus(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType

        player, unit, game = self._build_env()
        manager = player.stratagems

        ok = manager.use("HACK AND SLASH", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(unit.special_rules.get("hack_and_slash_ap_bonus"), 1)

        attacker = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker.parent_unit = unit

        target_unit = SimpleNamespace(models=[])
        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        profile = Wargear(data).profiles["default"]

        ap_val = profile.get_effective_ap(attacker, target_unit)
        self.assertEqual(ap_val, -1)


if __name__ == "__main__":
    unittest.main()
