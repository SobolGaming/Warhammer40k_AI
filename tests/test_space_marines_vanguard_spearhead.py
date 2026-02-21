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


def _build_game(detachment_type: str = "Vanguard Spearhead"):
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

    return game, army_sm, army_enemy


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
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesVanguardSpearhead(unittest.TestCase):
    def test_shadow_masters_applies_ranged_hit_penalty_beyond_12(self):
        _game, army_sm, army_enemy = _build_game("Vanguard Spearhead")
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(target)
        army_enemy.add_unit(attacker)
        profile = _make_ranged_profile()

        far_hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Shadow Masters" in m for m in list(far_hit.get("modifiers", []) or [])))

        near_hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 9.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Shadow Masters" in m for m in list(near_hit.get("modifiers", []) or [])))

    def test_shadow_masters_grants_cover_beyond_12_only(self):
        _game, army_sm, army_enemy = _build_game("Vanguard Spearhead")
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            save="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(target)
        army_enemy.add_unit(attacker)
        profile = _make_ranged_profile()

        far_attack = {
            "mortal_wound": False,
            "distance_to_target": 18.0,
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
        }
        profile._save_with_tracking(
            target.models[0],
            far_attack,
            ap=-1,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(far_attack.get("benefit_of_cover", False)))
        self.assertIn("Shadow Masters", str(far_attack.get("benefit_of_cover_source", "")))

        near_attack = {
            "mortal_wound": False,
            "distance_to_target": 9.0,
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
        }
        profile._save_with_tracking(
            target.models[0],
            near_attack,
            ap=-1,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(near_attack.get("benefit_of_cover", False)))

    def test_shadow_masters_does_not_apply_outside_vanguard_spearhead(self):
        _game, army_sm, army_enemy = _build_game("Gladius Task Force")
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            save="4",
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(target)
        army_enemy.add_unit(attacker)
        profile = _make_ranged_profile()

        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Shadow Masters" in m for m in list(hit.get("modifiers", []) or [])))

        attack_instance = {
            "mortal_wound": False,
            "distance_to_target": 18.0,
            "attacker_model": attacker.models[0],
            "attacker_unit": attacker,
        }
        profile._save_with_tracking(
            target.models[0],
            attack_instance,
            ap=-1,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(attack_instance.get("benefit_of_cover", False)))


if __name__ == "__main__":
    unittest.main()
