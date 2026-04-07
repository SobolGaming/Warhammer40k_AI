import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestExemplarOfTheCode(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None, faction_keywords=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0, disembarked_from_transport_id="")
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit._characteristic_modifiers = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_models_for_collision = lambda: list(unit.models)
        unit.get_models_for_wound_allocation = lambda: list(unit.models)
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 1):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _build_game(self):
        army = Army.with_detachment("Imperial Knights", detachment_type="Other")
        army.faction_id = "QI"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        return game, army, enemy_army, player

    @staticmethod
    def _ability() -> Ability:
        ability_desc = (
            "At the start of the battle, select one unit from your opponent's army to be this model's quarry. "
            "Each time this model makes an attack that targets its quarry, you can re-roll the Wound roll. "
            "Each time this model's quarry is destroyed, you can select a new unit from your opponent's army to be its quarry."
        )
        return Ability("Exemplar of the Code", "QI", ability_desc, "Datasheet", "")

    @staticmethod
    def _find_exemplar_request(game):
        for req in list(game.decision_queue.list() or []):
            if req.decision_type != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "")) == "exemplar_of_the_code":
                return req
        return None

    @staticmethod
    def _option_id_for_target(request, target_unit):
        target_id = str(getattr(target_unit, "_id", "") or "")
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == target_id:
                return str(option.option_id)
        return ""

    @staticmethod
    def _skip_option_id(request):
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if bool(payload.get("skip", False)) or str(payload.get("action", "") or "") == "skip":
                return str(option.option_id)
        return ""

    def test_queues_quarry_selection_at_br1(self):
        game, army, enemy_army, player = self._build_game()
        ability = self._ability()

        source_unit = self._make_unit("Knight Preceptor", army, abilities=[ability], faction_keywords=["IMPERIAL KNIGHTS"])
        source_model = self._make_model("Preceptor", source_unit)
        source_model.abilities = {"Exemplar of the Code": ability}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()
        army.on_battle_round_start(1)

        request = self._find_exemplar_request(game)
        self.assertIsNotNone(request)
        self.assertEqual(str(request.context.get("ability", "")), "exemplar_of_the_code")

        option_id = self._option_id_for_target(request, target_unit)
        self.assertTrue(bool(option_id))
        resolved = resolve_decision_command(game, request, option_id, player_id=player.id)
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertIn(target_unit._id, getattr(source_unit, "_exemplar_of_the_code_quarry_ids", set()))

    def test_rejects_invalid_choice(self):
        game, army, enemy_army, player = self._build_game()
        ability = self._ability()

        source_unit = self._make_unit("Knight Preceptor", army, abilities=[ability], faction_keywords=["IMPERIAL KNIGHTS"])
        source_model = self._make_model("Preceptor", source_unit)
        source_model.abilities = {"Exemplar of the Code": ability}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        enemy_army.units = [target_unit]

        game.rebuild_entity_registry()
        army.on_battle_round_start(1)

        request = self._find_exemplar_request(game)
        self.assertIsNotNone(request)
        result = resolve_decision_command(game, request, "invalid-option-id", player_id=player.id)
        self.assertFalse(bool(getattr(result, "ok", True)))
        self.assertFalse(bool(getattr(source_unit, "_exemplar_of_the_code_quarry_ids", None)))

    def test_wound_reroll_vs_quarry(self):
        game = SimpleNamespace(
            event_system=EventSystem(),
            map=SimpleNamespace(roll_reroll_provider=lambda **k: not k.get("success")),
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = SimpleNamespace(player=player)

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

        attacker_unit = _Unit("Preceptor")
        target_unit = _Unit("QuarryUnit")
        attacker_unit._exemplar_of_the_code_quarry_ids = {target_unit._id}
        attacker_unit._exemplar_of_the_code_source = "Exemplar of the Code"

        attacker_model = Model(
            name="Preceptor",
            movement=6,
            toughness=10,
            save=3,
            wounds=12,
            leadership=6,
            objective_control=4,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Enemy",
            movement=6,
            toughness=5,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        ranged_parent = SimpleNamespace(name="Test Ranged Weapon", is_melee=lambda: False, is_ranged=lambda: True)
        prof = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
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

        from warhammer40k_ai.units import wargear as wargear_mod
        seq = iter([2, 6])  # fail then reroll success
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res["roll"]), 6)
            self.assertTrue(any("Exemplar of the Code" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_repick_on_destroyed_supports_optional_skip(self):
        game, army, enemy_army, player = self._build_game()
        ability = self._ability()

        source_unit = self._make_unit("Knight Preceptor", army, abilities=[ability], faction_keywords=["IMPERIAL KNIGHTS"])
        source_model = self._make_model("Preceptor", source_unit)
        source_model.abilities = {"Exemplar of the Code": ability}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        extra_unit = self._make_unit("Other Target", enemy_army)
        extra_unit.models = [self._make_model("Other Target Model", extra_unit)]
        enemy_army.units = [target_unit, extra_unit]

        source_unit._exemplar_of_the_code_quarry_ids = {target_unit._id}
        target_unit.is_alive = lambda: False

        game.rebuild_entity_registry()
        game._on_unit_destroyed_monarch_of_the_hunt(unit=target_unit)

        request = self._find_exemplar_request(game)
        self.assertIsNotNone(request)
        skip_option_id = self._skip_option_id(request)
        self.assertTrue(bool(skip_option_id))

        resolved = resolve_decision_command(game, request, skip_option_id, player_id=player.id)
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertEqual(set(getattr(source_unit, "_exemplar_of_the_code_quarry_ids", set())), set())

    def test_repick_on_destroyed_can_select_new_quarry(self):
        game, army, enemy_army, player = self._build_game()
        ability = self._ability()

        source_unit = self._make_unit("Knight Preceptor", army, abilities=[ability], faction_keywords=["IMPERIAL KNIGHTS"])
        source_model = self._make_model("Preceptor", source_unit)
        source_model.abilities = {"Exemplar of the Code": ability}
        source_unit.models = [source_model]
        army.units = [source_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_unit.models = [self._make_model("Target Model", target_unit)]
        extra_unit = self._make_unit("Other Target", enemy_army)
        extra_unit.models = [self._make_model("Other Target Model", extra_unit)]
        enemy_army.units = [target_unit, extra_unit]

        source_unit._exemplar_of_the_code_quarry_ids = {target_unit._id}
        target_unit.is_alive = lambda: False

        game.rebuild_entity_registry()
        game._on_unit_destroyed_monarch_of_the_hunt(unit=target_unit)

        request = self._find_exemplar_request(game)
        self.assertIsNotNone(request)
        option_id = self._option_id_for_target(request, extra_unit)
        self.assertTrue(bool(option_id))

        resolved = resolve_decision_command(game, request, option_id, player_id=player.id)
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertIn(extra_unit._id, getattr(source_unit, "_exemplar_of_the_code_quarry_ids", set()))


if __name__ == "__main__":
    unittest.main()
