import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _UnitStub:
    def __init__(self, *, name, army=None, abilities=None, is_leader=False):
        self.name = name
        self._army = army
        self.possible_abilities = list(abilities or [])
        self.special_rules = {}
        self.deployed = True
        self.reserve_status = "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.is_leader = bool(is_leader)
        self.attached_to = None
        self.attached_leaders = []
        self.models = [SimpleNamespace(is_alive=True)]
        self.models_lost = []

    def get_parent_army(self):
        return self._army

    def is_alive(self):
        return any(getattr(m, "is_alive", True) for m in self.models)

    def get_attached_unit_root(self):
        if self.is_leader and self.attached_to is not None:
            return self.attached_to
        return self

    def get_attached_unit_members(self):
        root = self.get_attached_unit_root()
        leaders = list(getattr(root, "attached_leaders", []) or [])
        return [root] + leaders


class _ArmyStub:
    def __init__(self, faction_id="DRU"):
        self.faction_id = faction_id
        self.units = []
        self.player = None


class _PlayerStub:
    def __init__(self, name, army):
        self.name = name
        self.army = army
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True

    def get_army(self):
        return self.army


class _GameStub:
    def __init__(self, *, phase_name, current_player):
        self.phase = SimpleNamespace(name=phase_name)
        self._current_player = current_player
        self.map = None

    def get_current_player(self):
        return self._current_player


class TestDrukhariPowerFromPain(unittest.TestCase):
    def test_command_phase_tokens_and_pain_adept(self):
        from warhammer40k_ai.rules.power_from_pain import PowerFromPainManager

        army = _ArmyStub()
        player = _PlayerStub("Drukhari", army)
        army.player = player

        pain_adept = _UnitStub(
            name="Haemonculus",
            army=army,
            abilities=[SimpleNamespace(name="Pain Adept")],
        )
        army.units.append(pain_adept)

        mgr = PowerFromPainManager(army)

        with patch("warhammer40k_ai.rules.power_from_pain.get_roll", return_value=4):
            mgr.on_command_phase_start(game=_GameStub(phase_name="COMMAND_PHASE", current_player=player), player=player)

        self.assertEqual(mgr.tokens, 2)

    def test_token_gain_on_enemy_destroy_and_battleshock(self):
        from warhammer40k_ai.rules.power_from_pain import PowerFromPainManager

        army = _ArmyStub()
        player = _PlayerStub("Drukhari", army)
        army.player = player
        mgr = PowerFromPainManager(army)

        enemy_army = _ArmyStub(faction_id="SM")
        enemy_unit = _UnitStub(name="Enemy", army=enemy_army)

        mgr.on_enemy_unit_destroyed(enemy_unit)
        mgr.on_enemy_battle_shock_failed(enemy_unit)

        self.assertEqual(mgr.tokens, 2)

    def test_empower_hatred_eternal_shooting(self):
        from warhammer40k_ai.rules.power_from_pain import PowerFromPainManager

        army = _ArmyStub()
        player = _PlayerStub("Drukhari", army)
        army.player = player
        unit = _UnitStub(
            name="Kabalites",
            army=army,
            abilities=[SimpleNamespace(name="Hatred Eternal (Pain)")],
        )
        army.units.append(unit)

        mgr = PowerFromPainManager(army)
        mgr.tokens = 1
        game = _GameStub(phase_name="SHOOTING_PHASE", current_player=player)

        self.assertTrue(mgr.empower_unit_for_trigger(unit, trigger="shooting", game=game))
        self.assertEqual(mgr.tokens, 0)
        self.assertTrue(unit.special_rules.get("pain_reroll_hit"))
        self.assertEqual(unit.special_rules.get("pain_empowered_expires_phase"), "SHOOTING_PHASE")

    def test_empower_attached_leader_applies_to_all_members(self):
        from warhammer40k_ai.rules.power_from_pain import PowerFromPainManager

        army = _ArmyStub()
        player = _PlayerStub("Drukhari", army)
        army.player = player
        bodyguard = _UnitStub(name="Wyches", army=army)
        leader = _UnitStub(
            name="Succubus",
            army=army,
            abilities=[SimpleNamespace(name="Hatred Eternal (Pain)")],
            is_leader=True,
        )
        leader.attached_to = bodyguard
        bodyguard.attached_leaders.append(leader)
        army.units.extend([bodyguard, leader])

        mgr = PowerFromPainManager(army)
        mgr.tokens = 1
        game = _GameStub(phase_name="FIGHT_PHASE", current_player=player)

        self.assertTrue(mgr.empower_unit_for_trigger(bodyguard, trigger="fight", game=game))
        self.assertTrue(bodyguard.special_rules.get("pain_reroll_hit"))
        self.assertTrue(leader.special_rules.get("pain_reroll_hit"))

    def test_empower_lithe_agility_flags_rerolls(self):
        from warhammer40k_ai.rules.power_from_pain import PowerFromPainManager

        army = _ArmyStub()
        player = _PlayerStub("Drukhari", army)
        army.player = player
        unit = _UnitStub(
            name="Succubus",
            army=army,
            abilities=[SimpleNamespace(name="Lithe Agility (Pain)")],
        )
        army.units.append(unit)

        mgr = PowerFromPainManager(army)
        mgr.tokens = 1
        game = _GameStub(phase_name="MOVEMENT_PHASE", current_player=player)

        self.assertTrue(mgr.empower_unit_for_trigger(unit, trigger="advance", game=game))
        self.assertTrue(unit.special_rules.get("pain_reroll_advance"))
        self.assertTrue(unit.special_rules.get("pain_reroll_charge"))

    def test_matchless_swiftness_sets_fixed_advance_roll(self):
        from warhammer40k_ai.units.unit import Unit

        class _RoundState:
            advance_roll = None

        class _UnitStub:
            def __init__(self):
                self.name = "Scourges"
                self.round_state = _RoundState()
                self.special_rules = {"pain_advance_no_roll": True, "pain_advance_fixed_bonus": 8}
                self._army = SimpleNamespace(player=SimpleNamespace(name="P1"))

            def get_parent_army(self):
                return self._army

            def _apply_advance_roll_modifiers(self, roll):
                return roll

        unit = _UnitStub()
        with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
            advance = Unit.prepare_advance(unit)

        self.assertEqual(advance, 8)
        self.assertEqual(unit.round_state.advance_roll, 8)
        roll_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
