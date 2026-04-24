import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wargear_rows=None,
        toughness: str = "10",
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
                "T": str(toughness),
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = list(wargear_rows or [])
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        if wargear_rows:
            names = "; ".join(str(row.get("name", "") or "").strip() for row in wargear_rows if str(row.get("name", "") or "").strip())
            self.loadout = f"This model is equipped with: {names}."
        else:
            self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name,
    *,
    keywords=None,
    abilities=None,
    faction_keywords=None,
    wargear_rows=None,
    toughness: str = "10",
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
        wargear_rows=wargear_rows,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("A1", "Detachment1")
    army1.faction_id = "A1"
    army2 = Army.with_detachment("A2", "Detachment2")
    army2.faction_id = "A2"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


class TestModelAllocatedMonsterVehicleDamageReroll(unittest.TestCase):
    def _attacker_wargear(self):
        return [
            {
                "name": "Twin Lascannon",
                "type": "Ranged",
                "range": "48",
                "A": "1",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "D3",
                "description": "",
            }
        ]

    def test_damage_reroll_applies_vs_monster_target(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Annihilator",
            "description": (
                "Each time a ranged attack made by this model is allocated to a MONSTER or VEHICLE model, "
                "you can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit(
            "Predator",
            keywords=["VEHICLE"],
            abilities=[ability],
            wargear_rows=self._attacker_wargear(),
            toughness="10",
        )
        target = _make_unit("Target Monster", keywords=["MONSTER"], toughness="9")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        calls = []
        game.install_decision_providers(roll_reroll_provider=lambda **kwargs: calls.append(kwargs) or True)

        profile = next(iter(attacker.models[0].wargear[0].profiles.values()))
        rolls = iter([4, 4, 1, 1, 3])  # hit, wound, save, damage, damage re-roll
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertTrue(result.damage_results, "Expected at least one damage result")
        damage = result.damage_results[0]
        self.assertIn("reroll", damage)
        self.assertTrue(any(c.get("roll_type") == "damage" for c in calls))
        self.assertTrue(any("Annihilator" in str(c.get("reason", "")) for c in calls))

    def test_damage_reroll_not_applied_vs_non_monster_vehicle_target(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Annihilator",
            "description": (
                "Each time a ranged attack made by this model is allocated to a MONSTER or VEHICLE model, "
                "you can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit(
            "Predator",
            keywords=["VEHICLE"],
            abilities=[ability],
            wargear_rows=self._attacker_wargear(),
            toughness="10",
        )
        target = _make_unit("Target Infantry", keywords=["INFANTRY"], toughness="4")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        calls = []
        game.install_decision_providers(roll_reroll_provider=lambda **kwargs: calls.append(kwargs) or True)

        profile = next(iter(attacker.models[0].wargear[0].profiles.values()))
        rolls = iter([4, 3, 1, 1])  # hit, wound, save, damage (no reroll expected)
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls, 6)
        try:
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertTrue(result.damage_results, "Expected at least one damage result")
        damage = result.damage_results[0]
        self.assertNotIn("reroll", damage)
        self.assertFalse(any(c.get("roll_type") == "damage" for c in calls))


if __name__ == "__main__":
    unittest.main()
