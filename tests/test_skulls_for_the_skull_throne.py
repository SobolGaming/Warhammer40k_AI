import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _TestUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.special_rules = {}
        self.deployed = True
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def get_attached_unit_root(self):
        return self

    def attached_unit_has_blessings_of_khorne(self):
        return True

    def is_alive(self):
        return True

    def is_battle_shocked(self):
        return False

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]


class _Game:
    def __init__(self, active_player):
        from warhammer40k_ai.classes.event_system import EventSystem

        self.event_system = EventSystem()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name="FIGHT_PHASE")

    def get_current_player(self):
        return self._current_player


class TestSkullsForTheSkullThrone(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        we_unit = _TestUnit("WE Unit", keywords=["Khorne"], faction_keywords=["World Eaters"])
        we_unit2 = _TestUnit("WE Unit 2", keywords=["Khorne"], faction_keywords=["World Eaters"])
        army.add_unit(we_unit)
        army.add_unit(we_unit2)

        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        enemy_unit = _TestUnit("Enemy Character", keywords=["Character"], faction_keywords=["Enemy"])
        enemy_army.add_unit(enemy_unit)

        player = Player("P1", player_type=PlayerType.HUMAN, army=army)
        enemy_player = Player("P2", player_type=PlayerType.HUMAN, army=enemy_army)
        game = _Game(active_player=enemy_player)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 1
        return player, enemy_player, we_unit, we_unit2, enemy_unit, game

    def _start_fight_phase(self, game, player):
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=player, phase=phase)

    def test_reaction_queued_on_model_destroyed(self):
        player, enemy_player, we_unit, _we_unit2, enemy_unit, game = self._build_env()
        manager = player.stratagems
        self._start_fight_phase(game, enemy_player)

        weapon = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))
        target_model = SimpleNamespace(name="Target")

        game.event_system.publish(
            "model_destroyed",
            attacker_unit=we_unit,
            attacker_model=SimpleNamespace(name="Attacker"),
            target_unit=enemy_unit,
            target_model=target_model,
            weapon_profile=weapon,
            is_mortal=False,
            game_map=None,
        )

        pending = manager.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "SKULLS FOR THE SKULL THRONE!" for r in pending))

    def test_unit_only_blessing_applies(self):
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsRollContext, BlessingsTiming
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType

        player, _enemy_player, we_unit, we_unit2, enemy_unit, game = self._build_env()
        manager = player.stratagems
        self._start_fight_phase(game, player)

        ctx = BlessingsRollContext(
            timing=BlessingsTiming.OTHER,
            battle_round=1,
            dice=[5, 5, 1, 1, 1, 1, 1, 1],
            rerolls_allowed=0,
            rerolled_indices=[],
            max_activations=1,
            counts_toward_baseline_limit=False,
            already_active_keys=set(),
            reborn_in_blood_available=False,
        )

        ok = manager.use(
            "SKULLS FOR THE SKULL THRONE!",
            unit=we_unit,
            target_unit=enemy_unit,
            phase_name="Fight phase",
            blessings_ctx=ctx,
            selected_blessings=["WARP_BLADES"],
        )
        self.assertTrue(ok)

        mgr = player.get_army().blessings_of_khorne
        self.assertNotIn("WARP_BLADES", mgr.active_blessing_keys)
        self.assertTrue(mgr.is_blessing_active_for_unit("WARP_BLADES", we_unit, battle_round=1))
        self.assertFalse(mgr.is_blessing_active_for_unit("WARP_BLADES", we_unit2, battle_round=1))

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

        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )

        attacker1 = Model(
            name="Attacker1",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker1.parent_unit = we_unit

        attacker2 = Model(
            name="Attacker2",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker2.parent_unit = we_unit2

        attack_instance = {}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, attacker1, attack_instance)
        self.assertTrue(attack_instance.get("lethal_hit", False))

        attack_instance = {}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, attacker2, attack_instance)
        self.assertFalse(attack_instance.get("lethal_hit", False))


if __name__ == "__main__":
    unittest.main()
