import unittest


class _BattleShockedUnit:
    def __init__(self):
        self.special_rules = {"cannot_use_stratagems": True}

    def is_battle_shocked(self):
        return True


class _NotBattleShockedUnit:
    def __init__(self):
        self.special_rules = {"cannot_use_stratagems": False}

    def is_battle_shocked(self):
        return False


class _Player:
    def __init__(self, cp: int = 1):
        self.command_points = cp

    def spend_command_points(self, amount: int) -> bool:
        if self.command_points < amount:
            return False
        self.command_points -= int(amount)
        return True


class _Game:
    def __init__(self, current_player):
        self._p = current_player

    def get_current_player(self):
        return self._p


class TestBattleShockStratagemTargeting(unittest.TestCase):
    def test_battle_shocked_unit_cannot_be_target(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        p = _Player(cp=1)
        g = _Game(current_player=p)
        s = Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )
        self.assertFalse(s.can_use(p, g, target_unit=_BattleShockedUnit()))

    def test_non_battle_shocked_unit_can_be_target(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        p = _Player(cp=1)
        g = _Game(current_player=p)
        s = Stratagem(
            id="x",
            name="Test Strat",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )
        self.assertTrue(s.can_use(p, g, target_unit=_NotBattleShockedUnit()))

    def test_insane_bravery_exempt_from_battle_shock_targeting_rule(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        p = _Player(cp=1)
        g = _Game(current_player=p)
        s = Stratagem(
            id="x",
            name="INSANE BRAVERY",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )
        # The unit will be battle-shocked in our engine at reaction time, so we must allow this.
        self.assertTrue(s.can_use(p, g, unit=_BattleShockedUnit()))


if __name__ == "__main__":
    unittest.main()


