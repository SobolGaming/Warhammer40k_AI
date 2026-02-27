import unittest
from unittest.mock import patch


class _RandomStub:
    def randint(self, _min_val: int, _max_val: int) -> int:
        return 2


class _EventSystemStub:
    def __init__(self):
        self.events = []

    def publish(self, event_name: str, **kwargs):
        self.events.append((str(event_name), dict(kwargs or {})))


class _EntityRegistryStub:
    def __init__(self, unit):
        self._unit = unit

    def get(self, entity_id: str, *, kind: str | None = None):
        if kind == "unit" and str(entity_id) == str(getattr(self._unit, "id", "")):
            return self._unit
        return None


class _ModelStub:
    def __init__(self, *, wounds: int, base_wounds: int, name: str = "Model"):
        self.name = name
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
    def __init__(
        self,
        *,
        models=None,
        lost=None,
        battleline=False,
        abilities=None,
        army=None,
        name="Test Unit",
        keywords=None,
        faction_keywords=None,
        unit_id="unit-shadow-of-chaos",
    ):
        self.id = str(unit_id)
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
        self.keywords = [str(k).strip().upper() for k in (keywords or []) if str(k).strip()]
        self.faction_keywords = [str(k).strip().upper() for k in (faction_keywords or []) if str(k).strip()]

    @property
    def is_battleline(self) -> bool:
        return self._battleline

    def is_alive(self) -> bool:
        return self._alive

    def get_parent_army(self):
        return self._army

    def get_attached_unit_models(self):
        return self.models

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        return kw in set(self.keywords + self.faction_keywords)

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
        self.id = name
        self.army = army
        self.game = None


class _GameStub:
    def __init__(self, players):
        self.players = list(players or [])

    def _shadow_of_chaos_zones(self, player):
        return set()

    def is_position_in_deployment_zone(self, x: float, y: float, player_id: str) -> bool:
        return False


class _DiceGameStub(_GameStub):
    def __init__(self, players, unit):
        super().__init__(players)
        from warhammer40k_ai.engine.decisions import DecisionQueue
        from warhammer40k_ai.engine.dice_rolls import DiceRollManager

        self.is_authoritative = True
        self.decision_queue = DecisionQueue()
        self.roll_manager = DiceRollManager()
        self.entity_registry = _EntityRegistryStub(unit)
        self.event_system = _EventSystemStub()
        self.random_source = _RandomStub()

    def request_decision(self, request):
        self.decision_queue.add(request)

    def request_dice_roll(self, *, player_id, spec, prompt=None):
        return self.roll_manager.request_roll(self, player_id=player_id, spec=spec, prompt=prompt)


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

    def test_daemonic_terror_requests_dice_roll_and_applies_mortals(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        unit = _UnitStub(
            models=[_ModelStub(wounds=3, base_wounds=3)],
            lost=[],
            battleline=False,
            unit_id="unit-daemonic-terror",
        )
        army = _ArmyStub(units=[unit], faction_id="CD")
        unit._army = army
        player = _PlayerStub("Daemons", army)
        army.player = player
        game = _DiceGameStub([player], unit=unit)
        player.game = game
        ctx = ShadowBattleShockContext(terror_active=True)

        ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=False, context=ctx, game=game)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertIn("Daemonic Terror mortal wounds", str(getattr(request, "prompt", "") or ""))

        roll_id = int((getattr(request, "context", {}) or {}).get("roll_id", 0) or 0)
        self.assertGreater(roll_id, 0)
        state = game.roll_manager.resolve_roll(game, roll_id)
        self.assertIsNotNone(state)
        self.assertEqual(int(unit.mortal_applied or 0), 2)

        roll_events = [
            payload
            for event_name, payload in list(game.event_system.events or [])
            if str(event_name) == "roll_made"
            and str(payload.get("roll_type", "") or "") == "daemonic_terror_mortals"
        ]
        self.assertTrue(roll_events)
        self.assertEqual(int(roll_events[-1].get("value", 0) or 0), 2)

    def test_manifestation_return_respects_starting_strength_cap(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        alive = _ModelStub(wounds=3, base_wounds=3, name="Blue Horror")
        lost = _ModelStub(wounds=0, base_wounds=3, name="Brimstone Horror")
        unit = _UnitStub(models=[alive], lost=[lost], battleline=True)
        unit.starting_model_count = 1
        ctx = ShadowBattleShockContext(manifestation_active=True)

        with patch("warhammer40k_ai.rules.shadow_of_chaos.get_roll", return_value=3):
            ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=True, context=ctx, game=None)

        self.assertEqual(len(unit.models), 1)
        self.assertEqual(len(unit.models_lost), 1)
        self.assertIs(unit.models_lost[0], lost)

    def test_manifestation_return_skips_pink_after_horrors_swap(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowBattleShockContext, ShadowOfChaosManager

        alive = _ModelStub(wounds=3, base_wounds=3, name="Blue Horror")
        lost_pink = _ModelStub(wounds=0, base_wounds=3, name="Pink Horror")
        lost_blue = _ModelStub(wounds=0, base_wounds=3, name="Blue Horror")
        unit = _UnitStub(models=[alive], lost=[lost_pink, lost_blue], battleline=True)
        unit.starting_model_count = 3
        unit._horrors_origin = "pink"
        unit._horrors_state = "blue"
        unit._horrors_can_return_model = lambda model: "pink horror" not in str(getattr(model, "name", "")).lower()
        ctx = ShadowBattleShockContext(manifestation_active=True)

        with patch("warhammer40k_ai.rules.shadow_of_chaos.get_roll", return_value=2):
            ShadowOfChaosManager.apply_battle_shock_outcome(unit, passed=True, context=ctx, game=None)

        self.assertEqual(len(unit.models), 2)
        self.assertIn(lost_blue, unit.models)
        self.assertIn(lost_pink, unit.models_lost)
        self.assertNotIn(lost_pink, unit.models)

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

    def test_greater_daemon_shadow_aura_counts_for_matching_god(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowOfChaosManager

        source = _UnitStub(
            models=[_ModelStub(wounds=6, base_wounds=6)],
            abilities=[_AbilityStub("Greater Daemon of Khorne (Aura)")],
            keywords=["LEGIONES DAEMONICA", "KHORNE"],
            name="Bloodthirster",
        )
        target = _UnitStub(
            models=[_ModelStub(wounds=2, base_wounds=2)],
            keywords=["LEGIONES DAEMONICA", "KHORNE"],
            name="Target",
        )

        daemon_army = _ArmyStub(units=[source, target], faction_id="CD")
        source._army = daemon_army
        target._army = daemon_army
        player = _PlayerStub("Daemons", daemon_army)
        daemon_army.player = player
        game = _GameStub([player])
        player.game = game

        mgr = ShadowOfChaosManager(daemon_army)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            self.assertTrue(mgr.is_unit_within_shadow(target, game=game))

    def test_greater_daemon_shadow_aura_requires_matching_god(self):
        from warhammer40k_ai.rules.shadow_of_chaos import ShadowOfChaosManager

        source = _UnitStub(
            models=[_ModelStub(wounds=6, base_wounds=6)],
            abilities=[_AbilityStub("Greater Daemon of Khorne (Aura)")],
            keywords=["LEGIONES DAEMONICA", "KHORNE"],
            name="Bloodthirster",
        )
        target = _UnitStub(
            models=[_ModelStub(wounds=2, base_wounds=2)],
            keywords=["LEGIONES DAEMONICA", "NURGLE"],
            name="Target",
        )

        daemon_army = _ArmyStub(units=[source, target], faction_id="CD")
        source._army = daemon_army
        target._army = daemon_army
        player = _PlayerStub("Daemons", daemon_army)
        daemon_army.player = player
        game = _GameStub([player])
        player.game = game

        mgr = ShadowOfChaosManager(daemon_army)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            self.assertFalse(mgr.is_unit_within_shadow(target, game=game))


if __name__ == "__main__":
    unittest.main()
