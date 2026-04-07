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


def _build_game(detachment_type: str = "Ironstorm Spearhead"):
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

    return game, army_sm, army_enemy


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


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
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


class TestSpaceMarinesIronstormSpearhead(unittest.TestCase):
    def test_armoured_wrath_is_once_per_phase_per_unit(self):
        game, army_sm, army_enemy = _build_game("Ironstorm Spearhead")
        attacker_a = _make_unit(
            "Intercessor Squad A",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        attacker_b = _make_unit(
            "Intercessor Squad B",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4, wounds=5)
        attacker_a.deployed = True
        attacker_b.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker_a)
        army_sm.add_unit(attacker_b)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        profile = _make_ranged_profile()
        first = profile._hit_target_with_tracking(
            target,
            attacker_a.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        second_same_unit = profile._hit_target_with_tracking(
            target,
            attacker_a.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        first_other_unit = profile._hit_target_with_tracking(
            target,
            attacker_b.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertTrue(any("Armoured Wrath" in s for s in list(first.get("special_effects", []) or [])))
        self.assertFalse(any("Armoured Wrath" in s for s in list(second_same_unit.get("special_effects", []) or [])))
        self.assertTrue(any("Armoured Wrath" in s for s in list(first_other_unit.get("special_effects", []) or [])))

    def test_armoured_wrath_shared_pool_across_hit_wound_damage(self):
        game, army_sm, army_enemy = _build_game("Ironstorm Spearhead")
        attacker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4, wounds=8)
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        profile = _make_ranged_profile("D6")
        damage_result = profile._damage_target_with_tracking(
            target.models[0],
            attacker.models[0],
            {},
            roll_value=1,
            roll_values=[1],
            allow_rerolls=True,
        )
        hit_after_damage = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertTrue(any("Armoured Wrath" in s for s in list(damage_result.get("special_effects", []) or [])))
        self.assertFalse(any("Armoured Wrath" in s for s in list(hit_after_damage.get("special_effects", []) or [])))

    def test_armoured_wrath_resets_on_phase_change(self):
        game, army_sm, army_enemy = _build_game("Ironstorm Spearhead")
        attacker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4, wounds=6)
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        ranged_profile = _make_ranged_profile()
        melee_profile = _make_melee_profile()

        shooting_hit = ranged_profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        game.phase = BattleRoundPhases.FIGHT_PHASE
        fight_hit = melee_profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertTrue(any("Armoured Wrath" in s for s in list(shooting_hit.get("special_effects", []) or [])))
        self.assertTrue(any("Armoured Wrath" in s for s in list(fight_hit.get("special_effects", []) or [])))


if __name__ == "__main__":
    unittest.main()
