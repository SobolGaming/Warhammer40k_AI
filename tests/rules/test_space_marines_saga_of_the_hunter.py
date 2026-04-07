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


def _build_game(*, detachment_type: str = "Saga of the Hunter", battlefield_size=None):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    size = battlefield_size if battlefield_size is not None else BattlefieldSize.STRIKE_FORCE
    bf = Battlefield(size)
    game = Game(bf)
    game.turn = 1

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, p1, army_sm, army_enemy


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Frost Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
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
        parent_wargear=parent,
    )


class TestSpaceMarinesSagaOfTheHunter(unittest.TestCase):
    def test_pack_quarry_initializes_round_one_with_battle_size_target(self):
        game, _player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments

        manager.on_battle_round_start(1, game=game)

        self.assertEqual(int(manager.pack_quarry_tally or 0), 0)
        self.assertEqual(int(manager.pack_quarry_target or 0), 3)
        self.assertTrue(bool(manager.pack_quarry_initialized))
        self.assertFalse(bool(manager.pack_quarry_completed))

    def test_pack_quarry_hit_bonus_applies_in_melee_when_outnumbering_target(self):
        _game, _player, army_sm, army_enemy = _build_game()
        attacker = _make_unit(
            "Wolf Guard",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)

        # Simulate a larger attacking unit.
        attacker.models = [attacker.models[0], attacker.models[0], attacker.models[0]]

        profile = _make_melee_profile()
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(hit.get("hit", False)))
        self.assertTrue(any("Pack's Quarry" in str(mod) for mod in list(hit.get("modifiers", []) or [])))

    def test_pack_quarry_wound_bonus_requires_completed_saga(self):
        _game, _player, army_sm, army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        attacker = _make_unit(
            "Wolf Guard",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.models = [attacker.models[0], attacker.models[0], attacker.models[0]]

        profile = _make_melee_profile()
        wound_before = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(wound_before.get("wound", False)))

        manager.pack_quarry_initialized = True
        manager.pack_quarry_target = 2
        manager.pack_quarry_tally = 2
        self.assertTrue(manager.pack_quarry_saga_completed())

        wound_after = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound_after.get("wound", False)))
        self.assertTrue(
            any("Pack's Quarry" in str(mod) for mod in list(wound_after.get("modifiers", []) or []))
        )

    def test_pack_quarry_fight_sequence_tally_tracks_destroyed_units(self):
        from warhammer40k_ai.engine.game import BattlefieldSize

        game, _player, army_sm, army_enemy = _build_game(battlefield_size=BattlefieldSize.INCURSION)
        manager = army_sm.space_marines_detachments
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target_a)
        army_enemy.add_unit(target_b)
        game.rebuild_entity_registry()

        manager.on_battle_round_start(1, game=game)
        self.assertEqual(int(manager.pack_quarry_target or 0), 2)

        game._on_fight_attacks_resolved_pack_quarry(
            unit=attacker,
            hits_by_target={target_a: 1, target_b: 1},
        )
        sr = getattr(attacker, "special_rules", None) or {}
        self.assertTrue(bool(sr.get("pack_quarry_pending_target_ids")))

        target_a.models = []
        target_b.models = []
        game._on_fight_sequence_complete_pack_quarry(unit=attacker)

        self.assertEqual(int(manager.pack_quarry_tally or 0), 2)
        self.assertTrue(manager.pack_quarry_saga_completed())
        sr_after = getattr(attacker, "special_rules", None) or {}
        self.assertFalse(bool(sr_after.get("pack_quarry_pending_target_ids")))


if __name__ == "__main__":
    unittest.main()
