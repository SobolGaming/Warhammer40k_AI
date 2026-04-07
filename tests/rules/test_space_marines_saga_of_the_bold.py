import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.phase import BattleRoundPhases


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 3,
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
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, wounds: int = 3):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        wounds=wounds,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Saga of the Bold"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_ranged_profile(damage_expr: str = "1"):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": str(damage_expr),
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(damage_expr: str = "1"):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Frost Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": str(damage_expr),
            "description": "",
        },
        parent_wargear=parent,
    )


class _StaticObjectiveLocation:
    def __init__(self, x: float, y: float, controller=None):
        self.x = float(x)
        self.y = float(y)
        self.removed = False
        self.controlling_player = controller

    def update_control(self, _game):
        return None


class TestSpaceMarinesSagaOfTheBold(unittest.TestCase):
    def test_pre_saga_character_unit_gets_one_reroll_choice(self):
        _game, _sm_player, _enemy_player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        character = _make_unit(
            "Wolf Lord",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        non_character = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(character)
        army_sm.add_unit(non_character)
        character.deployed = True
        non_character.deployed = True

        self.assertTrue(manager.heroes_all_start_selection(character, action="shoot"))
        self.assertFalse(manager.heroes_all_start_selection(non_character, action="shoot"))
        self.assertTrue(manager.heroes_all_reroll_is_available(character, "hit", action="shoot"))
        self.assertTrue(manager.heroes_all_reroll_is_available(character, "wound", action="shoot"))
        self.assertTrue(manager.heroes_all_reroll_is_available(character, "damage", action="shoot"))
        self.assertTrue(manager.consume_heroes_all_reroll(character, "hit", action="shoot"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "hit", action="shoot"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "wound", action="shoot"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "damage", action="shoot"))

    def test_completed_saga_grants_one_each_hit_wound_damage(self):
        _game, _sm_player, _enemy_player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        character = _make_unit(
            "Wolf Lord",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(character)
        character.deployed = True

        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_HIDE_AS_TROPHY)
        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_SLAY_THEM_ALL)
        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION)
        self.assertTrue(manager.heroes_all_saga_completed())

        self.assertTrue(manager.heroes_all_start_selection(character, action="fight"))
        self.assertTrue(manager.consume_heroes_all_reroll(character, "hit", action="fight"))
        self.assertTrue(manager.heroes_all_reroll_is_available(character, "wound", action="fight"))
        self.assertTrue(manager.heroes_all_reroll_is_available(character, "damage", action="fight"))
        self.assertTrue(manager.consume_heroes_all_reroll(character, "wound", action="fight"))
        self.assertTrue(manager.consume_heroes_all_reroll(character, "damage", action="fight"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "hit", action="fight"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "wound", action="fight"))
        self.assertFalse(manager.heroes_all_reroll_is_available(character, "damage", action="fight"))

    def test_oath_target_kills_track_hide_and_slay_boasts(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        attacker = _make_unit(
            "Wolf Lord",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target_one = _make_unit("Target One", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_two = _make_unit("Target Two", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_one)
        army_enemy.add_unit(target_two)
        attacker.deployed = True
        target_one.deployed = True
        target_two.deployed = True
        game.rebuild_entity_registry()

        oath_mgr = army_sm.oath_of_moment
        oath_mgr.set_target(target_one)
        self.assertTrue(manager.heroes_all_on_unit_destroyed(target_one, destroyed_by_unit=attacker, game=game))
        self.assertIn(manager._HEROES_ALL_BOAST_HIDE_AS_TROPHY, set(manager.heroes_all_achieved_boasts()))
        self.assertNotIn(manager._HEROES_ALL_BOAST_SLAY_THEM_ALL, set(manager.heroes_all_achieved_boasts()))

        oath_mgr.set_target(target_two)
        self.assertTrue(manager.heroes_all_on_unit_destroyed(target_two, destroyed_by_unit=attacker, game=game))
        self.assertIn(manager._HEROES_ALL_BOAST_SLAY_THEM_ALL, set(manager.heroes_all_achieved_boasts()))

    def test_phase_end_checks_mark_overrun_and_hold_the_line_boasts(self):
        game, sm_player, enemy_player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        character = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(character)
        character.deployed = True
        character.models[0].set_location(10.0, 10.0, 0.0, 0.0)

        game.deployment_zones = {sm_player.id: {}, enemy_player.id: {}}
        game.is_model_wholly_in_deployment_zone = lambda _model, player_id: str(player_id) == str(enemy_player.id)
        manager.heroes_all_handle_phase_end(
            BattleRoundPhases.FIGHT_PHASE,
            active_player=enemy_player,
            game=game,
        )
        self.assertIn(manager._HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION, set(manager.heroes_all_achieved_boasts()))

        objective = SimpleNamespace(
            location=_StaticObjectiveLocation(10.0, 10.0, controller=sm_player),
            id="obj-1",
        )
        game.map.objectives = [objective]
        game.is_position_in_deployment_zone = lambda _x, _y, _player_id: False
        game.turn = 2
        manager.heroes_all_handle_phase_end(
            BattleRoundPhases.COMMAND_PHASE,
            active_player=sm_player,
            game=game,
        )
        self.assertIn(manager._HEROES_ALL_BOAST_HOLD_THE_LINE, set(manager.heroes_all_achieved_boasts()))

    def test_heroes_all_hit_reroll_applies_once_pre_saga(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Wolf Lord",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        game.rebuild_entity_registry()

        manager = army_sm.space_marines_detachments
        self.assertTrue(manager.heroes_all_start_selection(attacker, action="shoot", game=game))

        profile = _make_ranged_profile()
        first = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        second = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertTrue(any("Heroes All" in s for s in list(first.get("special_effects", []) or [])))
        self.assertFalse(any("Heroes All" in s for s in list(second.get("special_effects", []) or [])))

    def test_heroes_all_damage_reroll_applies_in_fight_after_saga_completion(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        attacker = _make_unit(
            "Wolf Lord",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=6)
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        game.rebuild_entity_registry()

        manager = army_sm.space_marines_detachments
        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_HIDE_AS_TROPHY)
        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_SLAY_THEM_ALL)
        manager._heroes_all_mark_boast(manager._HEROES_ALL_BOAST_OVERRUN_THEIR_POSITION)
        self.assertTrue(manager.heroes_all_start_selection(attacker, action="fight", game=game))

        profile = _make_melee_profile("D6")
        result = profile._damage_target_with_tracking(
            target.models[0],
            attacker.models[0],
            {},
            roll_value=1,
            roll_values=[1],
            allow_rerolls=True,
        )
        self.assertTrue(any("Heroes All" in s for s in list(result.get("special_effects", []) or [])))


if __name__ == "__main__":
    unittest.main()
