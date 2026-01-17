import unittest
from unittest.mock import patch


class _ModelStub:
    def __init__(self, *, wounds: int, base_wounds: int):
        self._base_wounds = base_wounds
        self._wounds = wounds
        self.parent_unit = None
        self._on_death_reactions_resolved = True
        self._loc = (0.0, 0.0, 0.0, 0.0)

    @property
    def is_alive(self) -> bool:
        return self._wounds > 0

    @property
    def wounds(self) -> int:
        return self._wounds

    @wounds.setter
    def wounds(self, value: int) -> None:
        self._wounds = int(value)

    def set_parent_unit(self, unit) -> None:
        self.parent_unit = unit

    def get_location(self):
        return self._loc

    def set_location(self, *args):
        self._loc = args

    def heal(self, amount: int) -> None:
        self._wounds = min(self._base_wounds, self._wounds + int(amount or 0))


class _UnitStub:
    def __init__(self, *, models=None, lost=None, battleline=False, abilities=None, army=None, name="Test Unit"):
        self.models = list(models or [])
        self.models_lost = list(lost or [])
        self._battleline = bool(battleline)
        self.name = name
        self.coherency_updated = False
        self.mortal_applied = 0
        self.possible_abilities = list(abilities or [])
        self._army = army
        self.deployed = True
        self._alive = True

    @property
    def is_battleline(self) -> bool:
        return self._battleline

    def is_alive(self) -> bool:
        return self._alive

    def get_parent_army(self):
        return self._army

    def get_attached_unit_models(self):
        return self.models

    def is_max_health(self):
        for m in self.models:
            if m.wounds < m._base_wounds:
                return False, m
        return True, None

    def update_coherency(self) -> None:
        self.coherency_updated = True

    def _apply_mortal_wounds_to_unit(self, unit, mortal_wound_amount: int, game_map=None) -> int:
        self.mortal_applied += int(mortal_wound_amount or 0)
        return 0


class _AbilityStub:
    def __init__(self, name: str):
        self.name = name


class _ArmyStub:
    def __init__(self, *, units=None, faction_id="CD"):
        self.units = list(units or [])
        self.faction_id = faction_id
        self.player = None


class _PlayerStub:
    def __init__(self, name: str, army: _ArmyStub):
        self.name = name
        self.army = army
        self.game = None


class _GameStub:
    def __init__(self, players):
        self.players = list(players or [])

    def _shadow_of_chaos_zones(self, player):
        return set()

    def is_position_in_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        return False


class TestShadowOfChaos(unittest.TestCase):
    def test_battleline_returns_destroyed_models(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        alive = _ModelStub(wounds=3, base_wounds=3)
        lost1 = _ModelStub(wounds=0, base_wounds=3)
        lost2 = _ModelStub(wounds=0, base_wounds=3)
        unit = _UnitStub(models=[alive], lost=[lost1, lost2], battleline=True)
        ctx = ShadowBattleShockContext(manifestation_active=True)

        with patch("warhammer40k_ai.rules.shadow_of_chaos.get_roll", return_value=3):
            ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=True, context=ctx, game=None)

        self.assertEqual(len(unit.models), 3)
        self.assertEqual(len(unit.models_lost), 0)
        self.assertTrue(all(m.wounds == m._base_wounds for m in unit.models))

    def test_manifestation_heals_non_battleline(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        model = _ModelStub(wounds=1, base_wounds=3)
        unit = _UnitStub(models=[model], lost=[], battleline=False)
        ctx = ShadowBattleShockContext(manifestation_active=True)

        with patch("warhammer40k_ai.rules.shadow_of_chaos.get_roll", return_value=2):
            ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=True, context=ctx, game=None)

        self.assertEqual(model.wounds, 3)

    def test_daemonic_terror_applies_mortals_on_fail(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        unit = _UnitStub(models=[_ModelStub(wounds=3, base_wounds=3)], lost=[], battleline=False)
        ctx = ShadowBattleShockContext(terror_active=True)

        with patch("warhammer40k_ai.rules.shadow_of_chaos.get_roll", return_value=2):
            ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=False, context=ctx, game=None)

        self.assertEqual(unit.mortal_applied, 2)

    def test_dark_master_aura_counts_as_shadow(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowOfChaosManager

        belakor = _UnitStub(
            models=[_ModelStub(wounds=6, base_wounds=6)],
            abilities=[_AbilityStub("The Dark Master (Aura)")],
            name="Be'lakor",
        )
        target = _UnitStub(models=[_ModelStub(wounds=2, base_wounds=2)], name="Target")

        daemon_army = _ArmyStub(units=[belakor, target], faction_id="CD")
        belakor._army = daemon_army
        target._army = daemon_army
        player = _PlayerStub("Daemons", daemon_army)
        daemon_army.player = player
        game = _GameStub([player])
        player.game = game

        mgr = ShadowOfChaosManager(daemon_army)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            self.assertTrue(mgr.is_unit_within_shadow(target, game=game))


if __name__ == "__main__":
    unittest.main()
