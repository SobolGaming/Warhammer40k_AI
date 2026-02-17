import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, save=3, wounds=6):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "5",
                "base_size": "100mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, save=3, wounds=6):
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            save=save,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    return unit


class _MapStub:
    def get_friendly_units(self, unit):
        army = unit.get_parent_army() if unit is not None else None
        return list(getattr(army, "units", []) or []) if army is not None else []

    def get_enemy_units(self, _unit):
        return []

    def get_distance_between_units(self, _a, _b):
        return 12.0

    def is_within_engagement_range(self, _a, _b):
        return False


class _GameStub:
    def __init__(self, active_player, phase_name: str):
        from warhammer40k_ai.engine.decisions import DecisionQueue
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name=phase_name)
        self.map = _MapStub()
        self.players = []
        self.is_authoritative = True

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)


class TestImperialKnightsValourstrikeStratagems(unittest.TestCase):
    def _setup_env(self, *, phase_name: str, active_is_player: bool):
        ik_army = Army("Imperial Knights", detachment_type="Valourstrike Lance")
        ik_army.faction_id = "QI"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        ik_player = Player("IK", control=PlayerControl.LOCAL, army=ik_army)
        enemy_player = Player("EN", control=PlayerControl.LOCAL, army=enemy_army)
        active_player = ik_player if active_is_player else enemy_player
        game = _GameStub(active_player=active_player, phase_name=phase_name)
        game.players = [ik_player, enemy_player]

        ik_player.set_game(game)
        enemy_player.set_game(game)
        ik_player.command_points = 5
        enemy_player.command_points = 5

        knight = _make_unit(
            "Knight",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
            faction_keywords=["IMPERIUM"],
            save=3,
            wounds=12,
        )
        enemy = _make_unit(
            "Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            save=3,
            wounds=3,
        )
        ik_army.add_unit(knight)
        enemy_army.add_unit(enemy)
        return ik_player, enemy_player, game, knight, enemy

    def test_vow_of_retribution_grants_ranged_lethal_hits(self):
        ik_player, _enemy_player, _game, knight, enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=True,
        )

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("VOW OF RETRIBUTION", unit=knight, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        weapon = Wargear(
            {
                "name": "Rapid-Fire Cannon",
                "type": "Ranged",
                "range": "36",
                "A": "1",
                "BS_WS": "3+",
                "S": "9",
                "AP": "-2",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attack_instance = {}
        hit = profile._hit_target_with_tracking(
            enemy,
            knight.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit.get("hit"))
        self.assertTrue(bool(attack_instance.get("lethal_hit")))
        self.assertIn("Lethal Hits", list(hit.get("special_effects", []) or []))

    def test_vow_of_retribution_rejects_unit_that_already_shot(self):
        ik_player, _enemy_player, _game, knight, _enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=True,
        )
        knight.round_state.shot_this_round = True

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("VOW OF RETRIBUTION", unit=knight, phase_name="Shooting phase")
        self.assertFalse(ok)
        self.assertEqual(int(ik_player.command_points), before_cp)

    def test_rotate_ion_shields_is_supported_by_generic_defensive_reaction(self):
        ik_player, _enemy_player, _game, knight, enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=False,
        )

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use(
            "ROTATE ION SHIELDS",
            unit=knight,
            attacker_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        weapon = Wargear(
            {
                "name": "Anti-Tank Rifle",
                "type": "Ranged",
                "range": "48",
                "A": "1",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        save_result = profile._save_with_tracking(knight.models[0], {}, -3)
        self.assertEqual(save_result.get("save_type"), "invulnerable")
        self.assertEqual(int(save_result.get("final_save", 0) or 0), 4)

    def test_valourstrike_stratagem_descriptors_registered(self):
        vow = get_stratagem_tool_descriptor(stratagem_id="000010494005")
        self.assertIsNotNone(vow)
        self.assertEqual(vow.effect, "ranged_lethal_hits")
        self.assertEqual(int(vow.cp_cost), 1)

        rotate = get_stratagem_tool_descriptor(stratagem_id="000010494007")
        self.assertIsNotNone(rotate)
        self.assertEqual(rotate.effect, "invulnerable_save")
        self.assertEqual(int(rotate.effect_params.get("invulnerable_save", 0) or 0), 4)


if __name__ == "__main__":
    unittest.main()
