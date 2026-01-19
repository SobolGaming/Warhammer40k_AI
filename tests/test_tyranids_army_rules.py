import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _UnitStub:
    def __init__(self, *, name, models, keywords=None, faction_keywords=None, army=None, abilities=None):
        self.name = name
        self._id = name
        self.models = list(models or [])
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = list(abilities or [])
        self.special_rules = {}
        self.deployed = True
        self.reserve_status = "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.attached_to = None
        self.attached_leaders = []
        self._army = army
        self.tests = []

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw and any(kw == k.lower() for k in (self.keywords + self.faction_keywords))

    def is_alive(self) -> bool:
        return any(getattr(m, "is_alive", True) for m in self.models)

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def take_battle_shock_test(self, current_turn: int = 1):
        self.tests.append(dict(self.special_rules))


class _ArmyStub:
    def __init__(self, *, units, faction_id="TYR"):
        self.units = list(units or [])
        self.faction_id = faction_id
        self.player = None


class _PlayerStub:
    def __init__(self, name: str, army):
        self.name = name
        self.id = name
        self.army = army

    def get_army(self):
        return self.army


class _GameStub:
    def __init__(self, players):
        self.players = list(players or [])
        self.turn = 1
        self.phase = SimpleNamespace(name="COMMAND_PHASE")

    def get_enemy_units(self, player):
        out = []
        for p in self.players:
            if p is player:
                continue
            out.extend(list(getattr(p.get_army(), "units", []) or []))
        return out


class TestTyranidsArmyRules(unittest.TestCase):
    def _mk_unit(self, army, *, name, keywords=None, faction_keywords=None, loc=(0.0, 0.0)):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        u = Unit.__new__(Unit)
        u.name = name
        u.status_effects = []
        u.special_rules = {}
        u.attached_leaders = []
        u.attached_to = None
        u.can_be_attached_to = []
        u.deployed = True
        u.reserve_status = "deployed"
        u.embarked_in = None
        u.keywords = list(keywords or [])
        u.faction_keywords = list(faction_keywords or [])
        u.round_state = SimpleNamespace()

        model = Model(
            name=f"{name} Model",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = u
        model.model_base.set_position(float(loc[0]), float(loc[1]), 0.0)
        u.models = [model]
        u.parent_army = army
        u.get_parent_army = lambda: army
        u.get_attached_unit_root = lambda: u
        u.get_attached_unit_models = lambda: list(u.models)
        u.get_models_for_collision = lambda: list(u.models)
        return u

    def test_synapse_battleshock_uses_3d6(self):
        from warhammer40k_ai.roster.army import Army

        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"

        synapse_unit = self._mk_unit(
            army,
            name="Synapse",
            keywords=["SYNAPSE"],
            faction_keywords=["TYRANIDS"],
            loc=(0.0, 0.0),
        )
        target_unit = self._mk_unit(
            army,
            name="Target",
            keywords=[],
            faction_keywords=["TYRANIDS"],
            loc=(1.0, 0.0),
        )
        army.units = [synapse_unit, target_unit]

        rolls = []

        def _fake_roll(expr):
            rolls.append(expr)
            return 6

        with patch("warhammer40k_ai.units.unit.get_roll", side_effect=_fake_roll):
            target_unit.take_battle_shock_test(current_turn=1)

        self.assertIn("3D6", rolls)

    def test_synapse_melee_strength_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"

        synapse_unit = self._mk_unit(
            army,
            name="Synapse",
            keywords=["SYNAPSE"],
            faction_keywords=["TYRANIDS"],
            loc=(0.0, 0.0),
        )
        attacker_unit = self._mk_unit(
            army,
            name="Attacker",
            keywords=[],
            faction_keywords=["TYRANIDS"],
            loc=(1.0, 0.0),
        )
        target_unit = self._mk_unit(
            army,
            name="Target",
            keywords=[],
            faction_keywords=["OTHER"],
            loc=(12.0, 0.0),
        )
        army.units = [synapse_unit, attacker_unit]

        attacker = attacker_unit.models[0]
        target = target_unit

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            wound_res = profile._wound_target_with_tracking(target, attacker, {"_aura_attack_mods": aura_stub})
        finally:
            wargear_mod.get_roll = old_get_roll

        self.assertTrue(any("Synapse" in x for x in wound_res.get("modifiers", [])))

    def test_shadow_in_the_warp_once_per_battle_and_modifier(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.rules.synapse import SynapseManager
        from warhammer40k_ai.rules.shadow_in_the_warp import ShadowInTheWarpManager

        synapse_model = Model(
            name="Synapse",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        synapse_model.model_base.set_position(0.0, 0.0, 0.0)

        close_model = Model(
            name="Close",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        close_model.model_base.set_position(3.0, 0.0, 0.0)

        far_model = Model(
            name="Far",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        far_model.model_base.set_position(12.0, 0.0, 0.0)

        tyr_army = _ArmyStub(units=[], faction_id="TYR")
        synapse_unit = _UnitStub(
            name="Synapse Unit",
            models=[synapse_model],
            keywords=["SYNAPSE"],
            faction_keywords=["TYRANIDS"],
            army=tyr_army,
            abilities=[SimpleNamespace(name="Shadow in the Warp")],
        )
        tyr_army.units = [synapse_unit]
        tyr_army.synapse = SynapseManager(tyr_army)
        tyr_army.shadow_in_the_warp = ShadowInTheWarpManager(tyr_army)

        enemy_army = _ArmyStub(units=[], faction_id="SM")
        close_unit = _UnitStub(
            name="Enemy Close",
            models=[close_model],
            keywords=[],
            faction_keywords=["OTHER"],
            army=enemy_army,
        )
        far_unit = _UnitStub(
            name="Enemy Far",
            models=[far_model],
            keywords=[],
            faction_keywords=["OTHER"],
            army=enemy_army,
        )
        enemy_army.units = [close_unit, far_unit]

        tyr_player = _PlayerStub("Tyr", tyr_army)
        enemy_player = _PlayerStub("Enemy", enemy_army)
        game = _GameStub([tyr_player, enemy_player])

        mgr = tyr_army.shadow_in_the_warp
        self.assertTrue(mgr.can_use_now(game=game, player=tyr_player))
        self.assertTrue(mgr.activate(game=game, player=tyr_player))
        self.assertTrue(mgr.used_this_battle)
        self.assertEqual(len(close_unit.tests), 1)
        self.assertEqual(len(far_unit.tests), 1)
        self.assertEqual(int(close_unit.tests[0].get("battle_shock_test_modifier", 0)), -1)
        self.assertIsNone(far_unit.tests[0].get("battle_shock_test_modifier"))

        self.assertFalse(mgr.activate(game=game, player=tyr_player))
        self.assertEqual(len(close_unit.tests), 1)

    def test_shadow_in_the_warp_blocks_insane_bravery(self):
        from warhammer40k_ai.rules.stratagems import StratagemManager

        player = SimpleNamespace(id="P1")
        game = SimpleNamespace(get_current_player=lambda: player, battle_shock_step_active=False)
        unit = SimpleNamespace(
            special_rules={},
            get_parent_army=lambda: SimpleNamespace(player=player),
        )

        sm = StratagemManager.__new__(StratagemManager)
        sm.player = player
        sm.game = game
        sm._current_phase_name = "Command phase"
        sm._used_once_per_battle = {"INSANE BRAVERY": False}
        sm._pending_reactions = []
        sm._reaction_timeout_s = 0.0
        sm.get_by_name = lambda _n: SimpleNamespace(name="INSANE BRAVERY", cp_cost=1, can_use=lambda *_a, **_k: True)
        sm._now = lambda: 0.0
        sm._queue_reaction = StratagemManager._queue_reaction.__get__(sm)

        sm._on_battle_shock_test_started(unit)
        self.assertEqual(sm._pending_reactions, [])
        game.battle_shock_step_active = True
        unit.special_rules = {"shadow_in_the_warp_battleshock": True}
        sm._on_battle_shock_test_started(unit)
        self.assertEqual(sm._pending_reactions, [])


if __name__ == "__main__":
    unittest.main()
