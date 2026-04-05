import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
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
                "Sv": str(save),
                "W": "3",
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Saga of the Beastslayer"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, p1, army_sm, army_enemy


def _make_ranged_profile():
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
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesSagaOfTheBeastslayer(unittest.TestCase):
    def test_beastslayer_target_initializes_round_one_with_round_up_and_embarked_keyword_units(self):
        game, _player, army_sm, army_enemy = _build_game()
        manager = army_sm.space_marines_detachments

        enemy_character = _make_unit("Enemy Character", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ENEMY"])
        enemy_vehicle = _make_unit("Enemy Vehicle", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
        enemy_monster_embarked = _make_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"])
        enemy_transport = _make_unit("Enemy Transport", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ENEMY"])
        enemy_infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

        enemy_monster_embarked.embarked_in = enemy_transport

        army_enemy.add_unit(enemy_character)
        army_enemy.add_unit(enemy_vehicle)
        army_enemy.add_unit(enemy_monster_embarked)
        army_enemy.add_unit(enemy_transport)
        army_enemy.add_unit(enemy_infantry)

        manager.on_battle_round_start(1, game=game)

        self.assertEqual(int(manager.beastslayer_tally or 0), 0)
        self.assertEqual(int(manager.beastslayer_target or 0), 2)
        self.assertTrue(bool(manager.beastslayer_initialized))
        self.assertFalse(bool(manager.beastslayer_completed))

    def test_legendary_slayers_grants_lethal_hits_vs_character_monster_vehicle(self):
        _game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_vehicle = _make_unit(
            "Enemy Tank",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_vehicle)

        profile = _make_ranged_profile()
        attack_instance = {"distance_to_target": 18.0}
        hit = profile._hit_target_with_tracking(
            target_vehicle,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(attack_instance.get("lethal_hit", False)))
        self.assertTrue(any("Lethal Hits" in s for s in list(hit.get("special_effects", []) or [])))

    def test_legendary_slayers_grants_lethal_hits_after_saga_completion(self):
        _game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        non_keyword_target = _make_unit(
            "Enemy Infantry",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(non_keyword_target)

        manager = army_sm.space_marines_detachments
        manager.beastslayer_initialized = True
        manager.beastslayer_target = 1
        manager.beastslayer_tally = 1
        self.assertTrue(manager.legendary_slayers_saga_completed())

        profile = _make_ranged_profile()
        attack_instance = {"distance_to_target": 18.0}
        hit = profile._hit_target_with_tracking(
            non_keyword_target,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(attack_instance.get("lethal_hit", False)))
        self.assertTrue(any("Lethal Hits" in s for s in list(hit.get("special_effects", []) or [])))

    def test_shooting_resolved_increments_beastslayer_tally_for_destroyed_keyword_units(self):
        game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_vehicle = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
        target_infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_vehicle)
        army_enemy.add_unit(target_infantry)
        game.rebuild_entity_registry()

        target_vehicle.models = []
        target_infantry.models = []
        game._on_unit_shooting_resolved_legendary_slayers(
            attacker_unit=attacker,
            hits_by_target={target_vehicle: 2, target_infantry: 3},
        )

        manager = army_sm.space_marines_detachments
        self.assertEqual(int(manager.beastslayer_tally or 0), 1)

    def test_fight_sequence_completion_increments_beastslayer_tally_for_destroyed_keyword_units(self):
        game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Bladeguard",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_monster = _make_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_monster)
        game.rebuild_entity_registry()

        game._on_fight_attacks_resolved_legendary_slayers(
            unit=attacker,
            hits_by_target={target_monster: 1},
        )
        sr = getattr(attacker, "special_rules", None) or {}
        self.assertTrue(bool(sr.get("legendary_slayers_pending_target_ids")))

        target_monster.models = []
        game._on_fight_sequence_complete_legendary_slayers(unit=attacker)

        manager = army_sm.space_marines_detachments
        self.assertEqual(int(manager.beastslayer_tally or 0), 1)
        sr_after = getattr(attacker, "special_rules", None) or {}
        self.assertFalse(bool(sr_after.get("legendary_slayers_pending_target_ids")))


if __name__ == "__main__":
    unittest.main()
