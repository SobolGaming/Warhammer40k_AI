import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.decision_request_helpers import install_decision_request_support


class _StubUnit:
    def __init__(self, name, army, *, toughness=5, keywords=None, faction_keywords=None, is_transport=False, is_character=False):
        self.name = name
        self._id = name
        self.toughness = toughness
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(
            remained_stationary_this_round=False,
            charged_this_round=False,
            disembarked_this_round=False,
            engaged_enemies_at_turn_start=set(),
        )
        self.parent_army = army
        self.is_transport = is_transport
        self.is_character = is_character
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_alive(self):
        return True

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        for k in (self.keywords or []) + (self.faction_keywords or []):
            if kw == str(k).strip().lower():
                return True
        return False


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, model_count=1, base_size="32mm"):
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit
    datasheet = _MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, model_count=model_count)
    return Unit(datasheet)


def _make_game(turn: int = 1, phase_name: str = "FIGHT_PHASE"):
    from warhammer40k_ai.engine.event.system import EventSystem
    return SimpleNamespace(
        turn=turn,
        phase=SimpleNamespace(name=phase_name),
        event_system=EventSystem(),
        map=None,
    )


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile
    parent = SimpleNamespace(name="Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestEmperorsChildrenDetachments(unittest.TestCase):
    def test_quicksilver_grace_allows_advance_reroll(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.unit import Unit

        army = Army.with_detachment("Emperor's Children", detachment_type="Mercurial Host")
        army.faction_id = "EC"
        unit = _StubUnit("EC Unit", army, faction_keywords=["EMPEROR'S CHILDREN"])

        self.assertTrue(Unit.can_reroll_advance_roll(unit))

        army.build_detachments[0].detachment_type = "Other"
        army.detachments[0].detachment_type = "Other"
        self.assertFalse(Unit.can_reroll_advance_roll(unit))

    def test_pact_points_reroll_hit_and_wound(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1", game=_make_game())
        army.emperors_children.pact_points = 3

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit
        attacker_unit.models = [attacker_model]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        profile = _make_melee_profile()
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

        seq = iter([1, 4, 1, 5])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 4)
            self.assertTrue(any("Pledges to the Dark Prince" in x for x in hit_res.get("special_effects", [])))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res["roll"]), 5)
            self.assertTrue(any("Pledges to the Dark Prince" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_pact_points_critical_on_five(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1", game=_make_game())
        army.emperors_children.pact_points = 7

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
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
        wargear_mod.get_roll = lambda _s: 5
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(attack_instance.get("crit_hit", False))
            self.assertTrue(any("Critical hit (5+)" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_faultless_opportunist_heroic_intervention_free_and_repeatable(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.rules.stratagems import StratagemManager, Stratagem

        army = Army.with_detachment("Test Faction", detachment_type="Peerless Bladesmen")
        army.faction_id = "TEST"
        bearer = _StubUnit("Bearer", army)
        bearer.deployed = True
        bearer.reserve_status = "deployed"
        bearer.is_embarked = False
        bearer.embarked_in = None

        Enhancement(
            id="000010002002",
            name="Faultless Opportunist",
            faction_id="TEST",
            detachment="Peerless Bladesmen",
            points=15,
            description="",
        ).apply_to_unit(bearer)

        other = _StubUnit("Other", army)
        other.deployed = True
        other.reserve_status = "deployed"
        other.is_embarked = False
        other.embarked_in = None

        army.units = [bearer, other]

        player = Player("P1", PlayerControl.LOCAL, army)
        player.command_points = 0
        player.set_game(install_decision_request_support(SimpleNamespace(turn=1)))

        strat = Stratagem(
            id="core-hi",
            name="Heroic Intervention",
            type="Core",
            description="",
            cp_cost=1,
            turn="Opponent's turn",
            phase="Charge phase",
            detachment="",
            faction_id="",
        )

        preview = player.preview_stratagem_cp_cost(strat, target_unit=bearer)
        self.assertEqual(int(preview["cost"]), 0)

        manager = StratagemManager(player)
        manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
        manager._record_heroic_intervention_use(other)

        self.assertTrue(manager._heroic_intervention_repeat_allowed(target_unit=bearer))
        self.assertFalse(manager._heroic_intervention_repeat_allowed(target_unit=other))

    def test_rise_to_challenge_candidates_and_usage(self):
        from warhammer40k_ai.engine.game import Game, Battlefield
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.rules.enhancement import Enhancement

        game = Game(Battlefield(width=44, height=30))
        army = Army.with_detachment("Emperor's Children", detachment_type="Peerless Bladesmen")
        army.faction_id = "EC"
        player = Player("P1", PlayerControl.LOCAL, army)
        army.player = player

        bearer = _make_unit("Bearer", keywords=["INFANTRY"], model_count=1)
        bearer.deployed = True
        bearer.reserve_status = "deployed"
        bearer.set_parent_army(army)
        Enhancement(
            id="000010002005",
            name="Rise to the Challenge",
            faction_id="EC",
            detachment="Peerless Bladesmen",
            points=30,
            description="",
        ).apply_to_unit(bearer)

        enemy_army = Army.with_detachment("Opponent", detachment_type="Other")
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], model_count=3)
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        enemy.set_parent_army(enemy_army)

        army.units = [bearer]
        enemy_army.units = [enemy]
        enemy_army.player = Player("P2", PlayerControl.LOCAL, enemy_army)

        bearer.models[0].model_base.set_position(0.0, 0.0, 0.0)
        enemy.models[0].model_base.set_position(0.5, 0.0, 0.0)
        enemy.models[1].model_base.set_position(0.6, 0.3, 0.0)
        enemy.models[2].model_base.set_position(0.8, -0.2, 0.0)
        game.map.units = [bearer, enemy]

        candidates = game._rise_to_challenge_candidates(player)
        self.assertIn(bearer, candidates)

        bearer.special_rules["enhancement_rise_to_challenge_used"] = True
        candidates_after = game._rise_to_challenge_candidates(player)
        self.assertNotIn(bearer, candidates_after)

    def test_rise_to_challenge_decision_handler(self):
        from warhammer40k_ai.engine.game import Game, Battlefield
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_RISE_TO_CHALLENGE
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        game = Game(Battlefield(width=44, height=30))
        army = Army.with_detachment("Emperor's Children", detachment_type="Peerless Bladesmen")
        army.faction_id = "EC"
        player = Player("P1", PlayerControl.REMOTE, army)
        army.player = player

        bearer = _make_unit("Bearer", keywords=["INFANTRY"], model_count=1)
        bearer.set_parent_army(army)
        army.units = [bearer]

        game.players = [player]
        game.rebuild_entity_registry()

        unit_id = get_entity_id(bearer)
        choose_opt = DecisionOption.create("Bearer", payload={"unit_id": unit_id})
        skip_opt = DecisionOption.create("Skip", payload={"action": "skip"})
        req = DecisionRequest.create(
            DECISION_SELECT_RISE_TO_CHALLENGE,
            "Select Rise to the Challenge unit.",
            player_id=getattr(player, "id", None),
            options=[choose_opt, skip_opt],
        )

        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=choose_opt.option_id)
        applied = dispatch_decision(game, req, result)
        self.assertTrue(applied.ok)
        self.assertIs(applied.value, bearer)

        skip_result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=skip_opt.option_id)
        skipped = dispatch_decision(game, req, skip_result)
        self.assertTrue(skipped.ok)
        self.assertIsNone(skipped.value)

    def test_pact_points_melee_lethal_and_sustained(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1", game=_make_game())
        army.emperors_children.pact_points = 5

        attacker_unit = _StubUnit("Attacker", army)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
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
        wargear_mod.get_roll = lambda _s: 6
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(attack_instance.get("lethal_hit", False))
            self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 1)
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_mechanised_murder_rerolls(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army.with_detachment("Emperor's Children", detachment_type="Rapid Evisceration")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1", game=_make_game())
        army.emperors_children.pact_points = 0

        attacker_unit = _StubUnit("Attacker", army, is_transport=True)
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit
        attacker_unit.models = [attacker_model]

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        profile = _make_melee_profile()
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

        seq = iter([1, 5, 1, 4])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Mechanised Murder" in x for x in hit_res.get("special_effects", [])))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Mechanised Murder" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_internal_rivalries_roll_modifier_choice(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE, CHOICE_KEEP_ALL

        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1")

        unit = _StubUnit("Champion", army, is_character=True)
        mods = [(-2, "Debuff"), (1, "Buff")]

        unit.round_state.advance_modifier_choice = CHOICE_IGNORE_NEGATIVE
        filtered_ignore_neg = Unit._filter_internal_rivalries_roll_modifiers(unit, mods, kind="advance")
        self.assertEqual(filtered_ignore_neg, [(1, "Buff")])

        unit.round_state.advance_modifier_choice = CHOICE_KEEP_ALL
        filtered_keep_all = Unit._filter_internal_rivalries_roll_modifiers(unit, mods, kind="advance")
        self.assertEqual(filtered_keep_all, mods)

    def test_internal_rivalries_move_modifier_choice_applies(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE, CHOICE_KEEP_ALL

        army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1")

        unit = _make_unit("Champion", keywords=["Character"])
        unit.set_parent_army(army)
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.embarked_in = None
        army.units.append(unit)

        unit.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, -2, source="Slow"))
        unit.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, 1, source="Fast"))
        model = unit.models[0]

        unit.round_state.move_modifier_choice = CHOICE_KEEP_ALL
        keep_all_val = Unit.get_effective_model_characteristic(unit, model, "movement")

        unit.round_state.move_modifier_choice = CHOICE_IGNORE_NEGATIVE
        ignore_neg_val = Unit.get_effective_model_characteristic(unit, model, "movement")

        self.assertLess(int(keep_all_val), int(ignore_neg_val))

    def test_pledges_to_dark_prince_decision_and_tracking(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLEDGE
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ec_army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        ec_army.faction_id = "EC"
        enemy_army = Army.with_detachment("Opponent", detachment_type="Other")

        ec_player = Player("EC_Pledge", PlayerControl.REMOTE, army=ec_army)
        enemy_player = Player("Enemy_Pledge", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        game.add_player(ec_player)
        game.add_player(enemy_player)
        game.turn = 1
        game.current_player_index = 0

        warlord = _StubUnit("Warlord", ec_army, is_character=True)
        warlord.is_warlord = True
        warlord.deployed = True
        warlord.reserve_status = "deployed"
        warlord.is_embarked = False
        warlord.embarked_in = None
        ec_army.units.append(warlord)
        ec_army.warlord = warlord

        attacker = _StubUnit("Attacker", ec_army, is_character=True)
        attacker.deployed = True
        attacker.reserve_status = "deployed"
        attacker.is_embarked = False
        attacker.embarked_in = None
        ec_army.units.append(attacker)

        enemy_one = _StubUnit("Enemy One", enemy_army)
        enemy_two = _StubUnit("Enemy Two", enemy_army)
        enemy_army.units.extend([enemy_one, enemy_two])

        game.rebuild_entity_registry()
        game.event_system.publish("battle_round_started", game=game, battle_round=1)

        army_id = get_entity_id(ec_army)
        pledge_req = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_PLEDGE and str(req.context.get("army_id", "")) == army_id
        )
        self.assertEqual(str(pledge_req.context.get("ability", "") or ""), "pledges_to_the_dark_prince")
        self.assertEqual(int(pledge_req.context.get("battle_round", 0) or 0), 1)
        option_id = next(
            opt.option_id for opt in pledge_req.options if int(opt.payload.get("pledge_value", 0) or 0) == 2
        )
        option_payload = next(
            dict(opt.payload or {}) for opt in pledge_req.options if int(opt.payload.get("pledge_value", 0) or 0) == 2
        )
        self.assertEqual(str(option_payload.get("ability", "") or ""), "pledges_to_the_dark_prince")
        self.assertEqual(int(option_payload.get("battle_round", 0) or 0), 1)
        value, apply_result = resolve_decision_value(game, pledge_req, option_id)
        self.assertEqual(int(value or 0), 2)
        self.assertTrue(getattr(apply_result, "ok", False))

        game.event_system.publish("unit_destroyed", unit=enemy_one, destroyed_by_unit=attacker)
        game.event_system.publish("unit_destroyed", unit=enemy_two, destroyed_by_unit=attacker)
        game.end_of_battle_round_scoring()

        self.assertEqual(int(ec_army.emperors_children.pact_points or 0), 2)

    def test_choose_pledge_requires_warlord_on_battlefield(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLEDGE
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ec_army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        ec_army.faction_id = "EC"
        player = Player("EC_InvalidPledge", PlayerControl.REMOTE, army=ec_army)
        enemy = Player("Enemy_InvalidPledge", PlayerControl.REMOTE, army=Army.with_detachment("Opponent", detachment_type="Other"))

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        game.add_player(player)
        game.add_player(enemy)
        game.turn = 1
        game.current_player_index = 0

        warlord = _StubUnit("Warlord Off Board", ec_army, is_character=True)
        warlord.is_warlord = True
        warlord.deployed = False
        warlord.reserve_status = "reserves"
        ec_army.units.append(warlord)
        ec_army.warlord = warlord

        game.rebuild_entity_registry()
        army_id = get_entity_id(ec_army)
        option = DecisionOption.create("1", payload={"pledge_value": 1, "army_id": army_id})
        request = DecisionRequest.create(
            DECISION_CHOOSE_PLEDGE,
            "Select pledge value.",
            player_id=player.id,
            options=[option],
            context={"army_id": army_id, "battle_round": 1, "max_value": 1},
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=option.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertFalse(apply_result.ok)
        self.assertTrue(any("warlord" in err.lower() for err in apply_result.errors))

    def test_internal_rivalries_favoured_champions_switch_after_attacks_resolve(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ec_army = Army.with_detachment("Emperor's Children", detachment_type="Slaanesh's Chosen")
        ec_army.faction_id = "EC"
        enemy_army = Army.with_detachment("Opponent", detachment_type="Other")

        ec_player = Player("EC_Favoured", PlayerControl.REMOTE, army=ec_army)
        enemy_player = Player("Enemy_Favoured", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        game.add_player(ec_player)
        game.add_player(enemy_player)
        game.turn = 1
        game.current_player_index = 0

        warlord = _StubUnit("Warlord Unit", ec_army, is_character=True)
        warlord.is_warlord = True
        warlord.deployed = True
        warlord.reserve_status = "deployed"
        warlord.is_embarked = False
        warlord.embarked_in = None
        ec_army.units.append(warlord)
        ec_army.warlord = warlord

        challenger = _StubUnit("Challenger", ec_army, is_character=True)
        challenger.deployed = True
        challenger.reserve_status = "deployed"
        challenger.is_embarked = False
        challenger.embarked_in = None
        ec_army.units.append(challenger)

        enemy_unit = _StubUnit("Enemy", enemy_army)
        enemy_army.units.append(enemy_unit)

        game.rebuild_entity_registry()
        game.event_system.publish("battle_round_started", game=game, battle_round=1)

        mgr = ec_army.emperors_children
        self.assertTrue(mgr.is_favoured_champions(warlord))

        game.event_system.publish("unit_destroyed", unit=enemy_unit, destroyed_by_unit=challenger)
        self.assertFalse(mgr.is_favoured_champions(challenger))

        game.event_system.publish("unit_shooting_resolved", attacker_unit=challenger)
        self.assertTrue(mgr.is_favoured_champions(challenger))

    def test_sensational_performance_restriction_only_attack_targets(self):
        from warhammer40k_ai.units.unit import Unit

        army = SimpleNamespace()
        attacker = _StubUnit("Attacker", army)
        attacker.special_rules = {
            "sensational_performance_active": True,
            "sensational_performance_expires_phase": "FIGHT_PHASE",
        }
        attacker.round_state.engaged_enemies_at_turn_start = set()

        target = _StubUnit("Target", army)
        game = SimpleNamespace(
            phase=SimpleNamespace(name="FIGHT_PHASE"),
            phase_targeted_units={target._id: {"other"}},
            phase_charge_targets={target._id: {"other"}},
        )
        reason = Unit._sensational_performance_restriction_reason(attacker, target, game)
        self.assertTrue(reason and "Sensational Performance" in reason)

        game.phase_targeted_units = {}
        reason = Unit._sensational_performance_restriction_reason(attacker, target, game)
        self.assertIsNone(reason)

    def test_sensational_performance_bonuses(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units import wargear as wargear_mod

        army = Army.with_detachment("Emperor's Children", detachment_type="Court of the Phoenician")
        army.faction_id = "EC"
        army.player = SimpleNamespace(name="P1", id="P1", game=_make_game())

        attacker_unit = _StubUnit("Attacker", army)
        attacker_unit.special_rules = {
            "sensational_performance_active": True,
            "sensational_performance_expires_phase": "FIGHT_PHASE",
            "sensational_performance_strength_bonus": 1,
            "sensational_performance_ap_bonus": 1,
        }
        target_unit = _StubUnit("Target", army, toughness=4)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        profile = _make_melee_profile()
        ap_val = profile.get_effective_ap(attacker_model, target_unit)
        self.assertEqual(int(ap_val), -1)

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
            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertTrue(any("Sensational Performance" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_sensational_performance_action_log(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.event_bus import get_recent_actions

        army = Army.with_detachment("Emperor's Children", detachment_type="Court of the Phoenician")
        army.faction_id = "EC"
        player = Player("P1_Sensational_Log", PlayerControl.REMOTE, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        game.add_player(player)

        unit = _StubUnit("Attacker", army)
        unit.round_state.charged_this_round = True
        army.units = [unit]
        game.rebuild_entity_registry()

        game._on_fight_unit_selected_emperors_children(unit=unit)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=player.id)

        actions = get_recent_actions(player, limit=5)
        self.assertTrue(any("Sensational Performance" in entry for entry in actions))

    def test_master_of_the_pageant_discount_and_usage(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.rules.stratagems import Stratagem

        army = Army.with_detachment("Emperor's Children", detachment_type="Court of the Phoenician")
        army.faction_id = "EC"
        player = Player("P1", PlayerControl.LOCAL, army=army)
        player.game = install_decision_request_support(SimpleNamespace(turn=1))

        fulgrim_unit = _StubUnit("Fulgrim", army, keywords=["FULGRIM"])
        strat = Stratagem(
            id="sinuous",
            name="Sinuous Breach",
            type="Stratagem",
            description="",
            cp_cost=1,
            turn="Your turn",
            phase="Movement phase",
            detachment="Court of the Phoenician",
            faction_id="EC",
        )

        prev = player.preview_stratagem_cp_cost(strat, target_unit=fulgrim_unit, assume_optional_discounts=True)
        self.assertEqual(int(prev.get("discount", 0)), 1)

        player.set_next_optional_decision("MASTER_OF_THE_PAGEANT", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=fulgrim_unit)
        self.assertEqual(int(applied.get("cost", 1)), 0)
        self.assertEqual(int(army.emperors_children.master_of_pageant_used_round or 0), 1)

        prev2 = player.preview_stratagem_cp_cost(strat, target_unit=fulgrim_unit, assume_optional_discounts=True)
        self.assertEqual(int(prev2.get("discount", 0)), 0)

    def test_unbound_arrogance_increases_pledge(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        player = Player("P1", PlayerControl.LOCAL, army=army)

        game = SimpleNamespace(
            turn=1,
            event_system=SimpleNamespace(subscribe=lambda *args, **kwargs: None),
        )
        player.set_game(game)
        player.command_points = 1

        unit = _StubUnit("EC Unit", army, faction_keywords=["EMPEROR'S CHILDREN"])
        manager = player.stratagems
        manager._current_phase_name = "Shooting phase"

        ok = manager.use("UNBOUND ARROGANCE", unit=unit, target_unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(army.emperors_children.pledge_target or 0), 1)
        self.assertEqual(int(army.emperors_children.unbound_arrogance_used_round or 0), 1)

    def test_unbound_arrogance_works_with_warlord_off_battlefield(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Emperor's Children", detachment_type="Coterie of the Conceited")
        army.faction_id = "EC"
        player = Player("P1", PlayerControl.LOCAL, army=army)

        game = SimpleNamespace(
            turn=1,
            event_system=SimpleNamespace(subscribe=lambda *args, **kwargs: None),
        )
        player.set_game(game)
        player.command_points = 1

        warlord = _StubUnit("Warlord", army, faction_keywords=["EMPEROR'S CHILDREN"], is_character=True)
        warlord.is_warlord = True
        warlord.deployed = False
        warlord.reserve_status = "reserves"
        warlord.is_embarked = False
        warlord.embarked_in = None
        army.warlord = warlord

        unit = _StubUnit("EC Unit", army, faction_keywords=["EMPEROR'S CHILDREN"])
        army.units = [warlord, unit]
        manager = player.stratagems
        manager._current_phase_name = "Shooting phase"

        ok = manager.use("UNBOUND ARROGANCE", unit=unit, target_unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(army.emperors_children.pledge_target or 0), 1)


if __name__ == "__main__":
    unittest.main()
