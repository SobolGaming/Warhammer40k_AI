import unittest
from types import SimpleNamespace


class _PlayerStub:
    def __init__(self, name: str, control_name: str, choice=None):
        self.name = name
        self.control = SimpleNamespace(name=control_name)
        self.has_control = lambda: control_name == "LOCAL"
        self._choice = choice
        self.army = None

    def _choose_optional_value(self, key, options, context):
        return self._choice

    def __hash__(self):
        return id(self)


class _ArmyStub:
    def __init__(self, faction_id: str, units: list, player):
        self.faction_id = faction_id
        self.units = units
        self.player = player


class _ModelStub:
    def __init__(self, x: float, y: float, *, oc: int = 1):
        from warhammer40k_ai.utility.model_base import Base, BaseType

        self.name = "Model"
        self.is_alive = True
        self.objective_control = oc
        self.model_base = Base(BaseType.CIRCULAR, 1.0)
        self.model_base.set_position(x, y, 0.0)

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, 0.0)


class _UnitStub:
    def __init__(self, keywords: list[str], models: list, *, deployed: bool = True):
        self.name = "Unit"
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.models = list(models or [])
        self.deployed = deployed
        self.is_leader = False

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        return kw in [k.lower() for k in self.keywords]

    def is_alive(self) -> bool:
        return any(bool(getattr(m, "is_alive", False)) for m in self.models)

    def get_models_for_collision(self):
        return self.models


class TestTemplarVows(unittest.TestCase):
    def _make_manager(self, *, control_name: str, choice=None, units=None):
        from warhammer40k_ai.rules.templar_vows import TemplarVowsManager

        player = _PlayerStub("P1", control_name, choice=choice)
        army = _ArmyStub("SM", units or [], player)
        player.army = army
        mgr = TemplarVowsManager(army)
        return mgr, player, army

    def test_selects_vow_for_non_human_players(self):
        from warhammer40k_ai.rules.templar_vows import VOW_ACCEPT

        mgr, _player, _army = self._make_manager(
            control_name="REMOTE",
            choice="Accept Any Challenge, No Matter the Odds",
        )
        mgr.on_battle_round_start(1)
        self.assertEqual(mgr.active_vow_key, VOW_ACCEPT.key)

    def test_human_selection_defers_without_choice(self):
        mgr, _player, _army = self._make_manager(control_name="LOCAL", choice=None)
        mgr.on_battle_round_start(1)
        self.assertIsNone(mgr.active_vow_key)

    def test_abhor_reroll_and_precision_vs_psyker(self):
        from warhammer40k_ai.rules.templar_vows import VOW_ABHOR

        mgr, _player, _army = self._make_manager(control_name="REMOTE")
        mgr.active_vow_key = VOW_ABHOR.key

        unit = _UnitStub(["ADEPTUS ASTARTES"], [object()])
        psyker = _UnitStub(["PSYKER"], [object()])
        non_psyker = _UnitStub(["INFANTRY"], [object()])

        self.assertTrue(mgr.can_reroll_charge_against(unit, psyker))
        self.assertTrue(mgr.melee_precision_against(unit, psyker))
        self.assertFalse(mgr.can_reroll_charge_against(unit, non_psyker))
        self.assertFalse(mgr.melee_precision_against(unit, non_psyker))

    def test_accept_any_challenge_melee_bonus(self):
        from warhammer40k_ai.rules.templar_vows import VOW_ACCEPT

        mgr, _player, _army = self._make_manager(control_name="REMOTE")
        mgr.active_vow_key = VOW_ACCEPT.key
        unit = _UnitStub(["ADEPTUS ASTARTES"], [object()])

        self.assertTrue(mgr.melee_wound_bonus_applies(unit, object(), strength=4, target_toughness=4))
        self.assertTrue(mgr.melee_wound_bonus_applies(unit, object(), strength=3, target_toughness=5))
        self.assertFalse(mgr.melee_wound_bonus_applies(unit, object(), strength=6, target_toughness=5))

    def test_suffer_not_the_unclean_rules(self):
        from warhammer40k_ai.rules.templar_vows import VOW_SUFFER

        mgr, _player, _army = self._make_manager(control_name="REMOTE")
        mgr.active_vow_key = VOW_SUFFER.key
        unit = _UnitStub(["ADEPTUS ASTARTES"], [object()])

        self.assertTrue(mgr.can_charge_after_fall_back(unit))
        self.assertTrue(mgr.use_closest_enemy_unit_rule(unit))

    def test_uphold_actions_and_sticky_objectives(self):
        from warhammer40k_ai.battlefield.map import ObjectivePoint, Objective, ObjectiveCategory
        from warhammer40k_ai.rules.templar_vows import VOW_UPHOLD

        model = _ModelStub(0.0, 0.0, oc=2)
        unit = _UnitStub(["ADEPTUS ASTARTES", "INFANTRY"], [model], deployed=True)
        player = _PlayerStub("P1", "LOCAL")
        army = _ArmyStub("SM", [unit], player)
        player.army = army
        opponent = _PlayerStub("P2", "REMOTE")
        opponent.army = _ArmyStub("SM", [], opponent)

        mgr = __import__("warhammer40k_ai.rules.templar_vows", fromlist=["TemplarVowsManager"]).TemplarVowsManager(army)
        mgr.active_vow_key = VOW_UPHOLD.key

        obj_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=obj_point,
        )
        game = SimpleNamespace(players=[player, opponent], map=SimpleNamespace(objectives=[objective]))

        self.assertTrue(mgr.allow_action_after_advance(unit, game))

        mgr.on_command_phase_end(game=game, player=player)
        self.assertIs(obj_point.sticky_controller, player)

        unit.deployed = False
        obj_point.update_control(game)
        self.assertIs(obj_point.controlling_player, player)
