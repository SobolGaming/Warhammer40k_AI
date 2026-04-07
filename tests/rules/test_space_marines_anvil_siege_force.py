import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Anvil Siege Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
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

    return game, army_sm, army_enemy


class TestSpaceMarinesAnvilSiegeForce(unittest.TestCase):
    def _make_profile(self, *, skill: str = "3+", strength: str = "4", heavy: bool = False):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = type(
            "_Parent",
            (),
            {
                "name": "Test Gun",
                "is_melee": staticmethod(lambda: False),
                "is_ranged": staticmethod(lambda: True),
            },
        )()
        return WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": skill,
                "S": strength,
                "AP": "0",
                "D": "1",
                "description": "[HEAVY]" if heavy else "",
            },
            parent_wargear=parent,
        )

    def test_shield_of_the_imperium_grants_heavy_hit_bonus_to_non_heavy_ranged_weapon(self):
        from warhammer40k_ai.units import wargear as wargear_mod

        _game, army_sm, army_enemy = _build_game()

        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker.round_state.remained_stationary_this_round = True
        army_sm.add_unit(attacker)

        target = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)
        army_enemy.add_unit(target)

        profile = self._make_profile(skill="3+", heavy=False)

        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 2
        try:
            hit = profile._hit_target_with_tracking(target, attacker.models[0], {})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertTrue(hit["hit"])
        self.assertIn("+1 from Shield of the Imperium (counts as Heavy)", hit["modifiers"])

    def test_shield_of_the_imperium_hit_bonus_requires_stationary(self):
        from warhammer40k_ai.units import wargear as wargear_mod

        _game, army_sm, army_enemy = _build_game()

        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker.round_state.remained_stationary_this_round = False
        army_sm.add_unit(attacker)

        target = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)
        army_enemy.add_unit(target)

        profile = self._make_profile(skill="3+", heavy=False)

        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 2
        try:
            hit = profile._hit_target_with_tracking(target, attacker.models[0], {})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertFalse(hit["hit"])
        self.assertNotIn("Shield of the Imperium", " ".join(hit.get("modifiers", [])))

    def test_shield_of_the_imperium_grants_wound_bonus_for_weapons_with_heavy(self):
        from warhammer40k_ai.units import wargear as wargear_mod

        _game, army_sm, army_enemy = _build_game()

        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker.round_state.remained_stationary_this_round = True
        army_sm.add_unit(attacker)

        target = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)
        army_enemy.add_unit(target)

        profile = self._make_profile(strength="4", heavy=True)

        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 3
        try:
            wound = profile._wound_target_with_tracking(target, attacker.models[0], {})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertTrue(wound["wound"])
        self.assertIn("+1 to wound from Shield of the Imperium", wound["modifiers"])

    def test_shield_of_the_imperium_wound_bonus_requires_stationary(self):
        from warhammer40k_ai.units import wargear as wargear_mod

        _game, army_sm, army_enemy = _build_game()

        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker.round_state.remained_stationary_this_round = False
        army_sm.add_unit(attacker)

        target = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=4)
        army_enemy.add_unit(target)

        profile = self._make_profile(strength="4", heavy=True)

        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 3
        try:
            wound = profile._wound_target_with_tracking(target, attacker.models[0], {})
        finally:
            wargear_mod.get_roll = original_roll

        self.assertFalse(wound["wound"])
        self.assertNotIn("Shield of the Imperium", " ".join(wound.get("modifiers", [])))


if __name__ == "__main__":
    unittest.main()
