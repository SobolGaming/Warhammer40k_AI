import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_ASPECT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str = "Aeldari", faction_keywords=None, keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or ["INFANTRY"])
        if faction_keywords is None:
            faction_keywords = ["AELDARI"] if faction_name == "Aeldari" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "7",
                "T": "3",
                "Sv": "3",
                "W": "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name: str, *, faction_name: str = "Aeldari", faction_keywords=None, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
        )
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _make_profile():
    parent = SimpleNamespace(name="Avenger Shuriken Catapult", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "18",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestAspectShrineToken(unittest.TestCase):
    def test_parse_it_can_have_aspect_shrine_token(self):
        from warhammer40k_ai.units.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Model") for _ in range(5)])
        desc = "For every 5 models in this unit, it can have 1 Aspect Shrine token."
        opts = parse_alternate_3([desc], unit)

        self.assertEqual(len(opts), 1)
        self.assertTrue(any("for every 5 models in this unit" in c for c in opts[0].conditionals))
        choice = opts[0].wargear_to[0]
        self.assertEqual(choice[0][1], "aspect shrine token")

    def test_parse_it_can_have_incubi_shrine_token(self):
        from warhammer40k_ai.units.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Incubi") for _ in range(5)])
        desc = "For every 5 models in this unit, it can have 1 Incubi Shrine token."
        opts = parse_alternate_3([desc], unit)

        self.assertEqual(len(opts), 1)
        self.assertTrue(any("for every 5 models in this unit" in c for c in opts[0].conditionals))
        choice = opts[0].wargear_to[0]
        self.assertEqual(choice[0][1], "incubi shrine token")

    def test_apply_wargear_option_adds_tokens(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.wargear import WargearOption, WargearOptionType, Quantity

        u = Unit.__new__(Unit)
        u.models = [
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
        ]
        for m in u.models:
            m.parent_unit = u
        u.possible_wargear = []
        u.wargear_options = []

        opt = WargearOption(
            WargearOptionType.ADDITIONAL,
            wargear_from=[],
            wargear_to=[[(1, "aspect shrine token")]],
            model_name="model",
            model_quantity=Quantity(min=1, max=2),
            item_quantity=Quantity(min=1, max=1),
            conditionals=[],
        )

        u.apply_wargear_option(opt)
        self.assertEqual(u.get_aspect_shrine_token_total(), 2)
        self.assertEqual(u.get_aspect_shrine_token_remaining(), 2)
        self.assertTrue(u._has_wargear_named("Aspect Shrine Token"))

        self.assertTrue(u.spend_aspect_shrine_token(1))
        self.assertEqual(u.get_aspect_shrine_token_remaining(), 1)
        self.assertFalse(u.spend_aspect_shrine_token(5))

    def test_aspect_shrine_tokens_not_auto_applied(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.wargear import WargearOption, WargearOptionType, Quantity

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[])]
        u.possible_wargear = []
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "aspect shrine token")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            )
        ]

        u.apply_wargear_options()
        self.assertEqual(u.get_aspect_shrine_token_total(), 0)

    def test_incubi_shrine_token_adds_shared_shrine_tokens_and_is_not_auto_applied(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.wargear import WargearOption, WargearOptionType, Quantity

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Incubi", wargear=[], optional_wargear=[])]
        for m in u.models:
            m.parent_unit = u
        u.possible_wargear = []
        opt = WargearOption(
            WargearOptionType.ADDITIONAL,
            wargear_from=[],
            wargear_to=[[(1, "incubi shrine token")]],
            model_name="incubi",
            model_quantity=Quantity(min=1, max=1),
            item_quantity=Quantity(min=1, max=1),
            conditionals=[],
        )
        u.wargear_options = [opt]

        u.apply_wargear_options()
        self.assertEqual(u.get_aspect_shrine_token_total(), 0)

        u.apply_wargear_option(opt)
        self.assertEqual(u.get_aspect_shrine_token_total(), 1)
        self.assertTrue(u._has_wargear_named("Incubi Shrine Token"))


    def test_destroyed_aspect_bodyguard_does_not_leave_tokens_on_attached_leader(self):
        bodyguard = _make_unit("Dire Avengers")
        leader = _make_unit("Autarch")

        leader.can_be_attached_to = ["dire avengers"]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        bodyguard.add_aspect_shrine_tokens(2)
        self.assertEqual(bodyguard.get_aspect_shrine_token_remaining(), 2)
        self.assertEqual(leader.get_aspect_shrine_token_remaining(), 2)

        last_model = bodyguard.models[0]
        bodyguard.remove_model(last_model, fleed=False, game_map=None)

        self.assertTrue(bool(getattr(bodyguard, "_pending_leader_separation", False)))
        self.assertEqual(bodyguard.get_aspect_shrine_token_remaining(), 0)
        self.assertEqual(leader.get_aspect_shrine_token_remaining(), 0)

        bodyguard.resolve_pending_leader_separation(game_map=None)

        self.assertIsNone(leader.attached_to)
        self.assertEqual(leader.get_aspect_shrine_token_remaining(), 0)

    def test_aspect_shrine_token_reuses_immediately_resolved_decision_request(self):
        aeldari_army = Army.with_detachment("Aeldari", detachment_type="Other")
        aeldari_army.faction_id = "AE"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        player = Player("Aeldari", PlayerControl.REMOTE, army=aeldari_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        shooter = _make_unit("Dire Avengers")
        target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"])
        aeldari_army.add_unit(shooter)
        enemy_army.add_unit(target)
        shooter.deployed = True
        target.deployed = True
        shooter.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        shooter.add_aspect_shrine_tokens(1)
        game.map.units = [shooter, target]
        game.rebuild_entity_registry()

        seen_decisions = []
        original_request_decision = game.request_decision

        def _auto_resolve(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            original_request_decision(request)
            use_option = next(
                opt
                for opt in list(request.options or [])
                if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "use"
            )
            resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        game.request_decision = _auto_resolve
        profile = _make_profile()
        hit = profile._hit_target_with_tracking(
            target,
            shooter.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertIn(DECISION_CHOOSE_ASPECT, seen_decisions)
        self.assertEqual(int(hit.get("roll", 0) or 0), 6)
        self.assertEqual(shooter.get_aspect_shrine_token_remaining(), 0)


if __name__ == "__main__":
    unittest.main()
