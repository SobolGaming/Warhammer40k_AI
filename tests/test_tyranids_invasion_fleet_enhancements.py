import unittest

from warhammer40k_ai.engine.attack_resolution import AttackSequence
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.perfectly_adapted import (
    PERFECTLY_ADAPTED_ACTION_ID,
    build_perfectly_adapted_reroll_rule,
    mark_perfectly_adapted_reroll_used,
)
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, keywords=None, faction_keywords=None):
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
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = None
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit.transport_passengers = []
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: unit.reserve_status in ("reserves", "strategic_reserves")
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )
    return unit


def _make_model(name, unit, *, x=0.0, y=0.0, wounds=6):
    model = Model(
        name=name,
        movement=6,
        toughness=5,
        save=3,
        wounds=wounds,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


class TestTyranidsInvasionFleetEnhancements(unittest.TestCase):
    def test_alien_cunning_redeploy_filters_to_tyranids_units(self):
        army = Army("Tyranids", detachment_type="Invasion Fleet")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.auto_resolve_dice_rolls = False
        game.attacker_index = 0
        game.defender_index = 1

        enhancer = Enhancement(
            id="000008348002",
            name="Alien Cunning",
            faction_id="TYR",
            detachment="Invasion Fleet",
            description=(
                '<span class="kwb">TYRANIDS</span> model only. After both players have deployed their armies, '
                'select up to three <span class="kwb">TYRANIDS</span> units from your army and redeploy them. '
                "When doing so, you can set those units up in Strategic Reserves if you wish, regardless of how many "
                "units are already in Strategic Reserves."
            ),
        )

        bearer = _make_unit("Hive Tyrant", army, keywords=["CHARACTER"], faction_keywords=["TYRANIDS"])
        bearer.models = [_make_model("Hive Tyrant", bearer, x=0.0, y=0.0, wounds=10)]
        bearer.enhancement = enhancer
        enhancer.apply_to_unit(bearer)

        tyr_a = _make_unit("Termagants", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        tyr_a.models = [_make_model("Termagants", tyr_a, x=5.0, y=0.0, wounds=1)]

        tyr_b = _make_unit("Warriors", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        tyr_b.models = [_make_model("Warriors", tyr_b, x=7.0, y=0.0, wounds=3)]

        tyr_reserve = _make_unit("Trygon", army, keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
        tyr_reserve.reserve_status = "strategic_reserves"
        tyr_reserve.deployed = False

        ally = _make_unit("Brood Brothers", army, keywords=["INFANTRY"], faction_keywords=["ASTRA MILITARUM"])
        ally.models = [_make_model("Brood Brothers", ally, x=9.0, y=0.0, wounds=1)]

        army.units = [bearer, tyr_a, tyr_b, tyr_reserve, ally]
        game.map.units = [bearer, tyr_a, tyr_b, ally]
        game.rebuild_entity_registry()

        game.execute_redeploy_units_phase()

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("ability_name", "")), "Alien Cunning")

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertIn(tyr_a._id, target_ids)
        self.assertIn(tyr_b._id, target_ids)
        self.assertNotIn(tyr_reserve._id, target_ids)
        self.assertNotIn(ally._id, target_ids)

        reserves_opt = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == tyr_a._id
            and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")).lower()
            == "strategic_reserves"
        )
        resolve_decision_command(game, request, reserves_opt.option_id, player_id=player.id)

        self.assertEqual(str(getattr(tyr_a, "reserve_status", "")), "strategic_reserves")
        self.assertNotIn(tyr_a, list(getattr(game.map, "units", []) or []))

    def test_alien_cunning_has_tool_descriptor(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000008348002")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Alien Cunning")
        self.assertEqual(desc.effect, "redeploy_units")
        self.assertEqual(int(desc.effect_params.get("max_units", 0) or 0), 3)
        self.assertTrue(bool(desc.effect_params.get("allow_strategic_reserves", False)))

    def test_synaptic_linchpin_grants_synapse_within_nine_of_bearer(self):
        army = Army("Tyranids", detachment_type="Invasion Fleet")
        army.faction_id = "TYR"

        bearer = _make_unit("Neurotyrant", army, keywords=["CHARACTER"], faction_keywords=["TYRANIDS"])
        bearer_a = _make_model("Bearer", bearer, x=0.0, y=0.0, wounds=8)
        bearer_b = _make_model("Escort", bearer, x=30.0, y=0.0, wounds=2)
        bearer.models = [bearer_a, bearer_b]

        enhancement = Enhancement(
            id="000008348004",
            name="Synaptic Linchpin",
            faction_id="TYR",
            detachment="Invasion Fleet",
            description=(
                '<span class="kwb">TYRANIDS</span> model only. While a friendly <span class="kwb">TYRANIDS</span> '
                'unit is within 9" of the bearer, that unit is within Synapse Range of your army.'
            ),
        )
        bearer.enhancement = enhancement
        enhancement.apply_to_unit(bearer)

        in_range = _make_unit("Hormagaunts", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        in_range.models = [_make_model("Horma", in_range, x=8.0, y=0.0, wounds=1)]

        near_other_model = _make_unit("Genestealers", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        near_other_model.models = [_make_model("Stealer", near_other_model, x=30.5, y=0.0, wounds=1)]

        out_of_range = _make_unit("Termagants", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        out_of_range.models = [_make_model("Terma", out_of_range, x=12.0, y=0.0, wounds=1)]

        army.units = [bearer, in_range, near_other_model, out_of_range]

        self.assertTrue(bool(bearer.special_rules.get("enhancement_synaptic_linchpin", False)))
        self.assertEqual(float(bearer.special_rules.get("enhancement_synaptic_linchpin_range", 0.0) or 0.0), 9.0)

        synapse_mgr = getattr(army, "synapse", None)
        self.assertIsNotNone(synapse_mgr)

        self.assertTrue(synapse_mgr.unit_in_synapse_range(in_range))
        self.assertFalse(synapse_mgr.unit_in_synapse_range(near_other_model))
        self.assertFalse(synapse_mgr.unit_in_synapse_range(out_of_range))

    def test_synaptic_linchpin_has_tool_descriptor(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000008348004")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Synaptic Linchpin")
        self.assertEqual(desc.effect, "count_as_within_synapse_range")
        self.assertEqual(float(desc.range_in or 0.0), 9.0)
        self.assertEqual(str(desc.effect_params.get("keyword", "") or ""), "TYRANIDS")

    def test_perfectly_adapted_has_tool_descriptor(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000008348003")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Perfectly Adapted")
        self.assertEqual(
            desc.effect,
            "bearer_single_reroll_one_of_hit_wound_damage_advance_charge_or_save",
        )
        self.assertTrue(bool(desc.effect_params.get("once_per_turn", False)))
        self.assertTrue(bool(desc.effect_params.get("shared_pool", False)))

    def test_perfectly_adapted_shared_once_per_turn_pool(self):
        army = Army("Tyranids", detachment_type="Invasion Fleet")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.auto_resolve_dice_rolls = False
        game.attacker_index = 0
        game.defender_index = 1

        enhancement = Enhancement(
            id="000008348003",
            name="Perfectly Adapted",
            faction_id="TYR",
            detachment="Invasion Fleet",
            description=(
                '<span class="kwb">TYRANIDS</span> model only. Once per turn, you can re-roll one Hit roll, one '
                "Wound roll, one Damage roll, one Advance roll, one Charge roll or one saving throw made for the bearer."
            ),
        )
        bearer = _make_unit("Winged Tyranid Prime", army, keywords=["CHARACTER"], faction_keywords=["TYRANIDS"])
        bearer.models = [_make_model("Prime", bearer, x=0.0, y=0.0, wounds=6)]
        bearer.enhancement = enhancement
        enhancement.apply_to_unit(bearer)

        self.assertTrue(bool(bearer.special_rules.get("enhancement_perfectly_adapted", False)))

        advance_rule = build_perfectly_adapted_reroll_rule(unit=bearer, game=game, roll_type="advance")
        self.assertIsNotNone(advance_rule)
        self.assertEqual(str(advance_rule.get("action_id", "")), PERFECTLY_ADAPTED_ACTION_ID)
        self.assertEqual(str(advance_rule.get("mode", "")), "whole")

        self.assertTrue(mark_perfectly_adapted_reroll_used(unit=bearer, game=game, roll_type="advance"))

        hit_rule_same_turn = build_perfectly_adapted_reroll_rule(unit=bearer, game=game, roll_type="hit")
        self.assertIsNone(hit_rule_same_turn)

        game.turn = 2
        hit_rule_next_turn = build_perfectly_adapted_reroll_rule(unit=bearer, game=game, roll_type="hit")
        self.assertIsNotNone(hit_rule_next_turn)
        self.assertEqual(str(hit_rule_next_turn.get("mode", "")), "select")
        self.assertEqual(int(hit_rule_next_turn.get("max_select", 0) or 0), 1)

    def test_perfectly_adapted_hit_reroll_positions_only_include_bearer_attacks(self):
        army = Army("Tyranids", detachment_type="Invasion Fleet")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.auto_resolve_dice_rolls = False
        game.attacker_index = 0
        game.defender_index = 1

        enhancement = Enhancement(
            id="000008348003",
            name="Perfectly Adapted",
            faction_id="TYR",
            detachment="Invasion Fleet",
            description=(
                '<span class="kwb">TYRANIDS</span> model only. Once per turn, you can re-roll one Hit roll, one '
                "Wound roll, one Damage roll, one Advance roll, one Charge roll or one saving throw made for the bearer."
            ),
        )
        attacker = _make_unit("Tyranid Warriors", army, keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
        bearer_model = _make_model("Prime", attacker, x=0.0, y=0.0, wounds=6)
        other_model = _make_model("Warrior", attacker, x=1.0, y=0.0, wounds=3)
        attacker.models = [bearer_model, other_model]
        attacker.enhancement = enhancement
        enhancement.apply_to_unit(attacker)

        target = _make_unit("Intercessors", enemy_army, keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
        target.models = [_make_model("Marine", target, x=5.0, y=0.0, wounds=2)]

        army.units = [attacker]
        enemy_army.units = [target]
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        seq = AttackSequence(
            sequence_id=1,
            attacker_unit_id=attacker._id,
            target_unit_id=target._id,
            wargear_id="wargear-1",
            profile_name="default",
            model_ids=[str(getattr(m, "id", "") or "") for m in list(attacker.models or [])],
        )
        seq.hit_groups = [
            {
                "final_needed": 4,
                "crit_threshold": 6,
                "reroll_values": [],
                "reroll_full_reasons": [],
                "attack_indices": [0, 1, 2],
            }
        ]
        seq.hit_group_index = 0
        seq.attack_instances = [
            {"attacker_model_id": str(getattr(bearer_model, "id", "") or "")},
            {"attacker_model_id": str(getattr(other_model, "id", "") or "")},
            {"attacker_model_id": str(getattr(bearer_model, "id", "") or "")},
        ]

        game.attack_manager._request_next_hit_roll(game, seq)
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].decision_type, DECISION_REQUEST_DICE_ROLL)

        roll_id = int((pending[0].context or {}).get("roll_id", 0) or 0)
        state = game.roll_manager.get_roll(roll_id)
        self.assertIsNotNone(state)
        reroll_rules = list((state.spec or {}).get("reroll_rules", []) or [])
        pa_rule = next(rule for rule in reroll_rules if str(rule.get("action_id", "")) == PERFECTLY_ADAPTED_ACTION_ID)
        self.assertEqual(list(pa_rule.get("eligible_positions", []) or []), [0, 2])

    def test_perfectly_adapted_reroll_action_consumes_usage(self):
        army = Army("Tyranids", detachment_type="Invasion Fleet")
        army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.auto_resolve_dice_rolls = False
        game.attacker_index = 0
        game.defender_index = 1

        enhancement = Enhancement(
            id="000008348003",
            name="Perfectly Adapted",
            faction_id="TYR",
            detachment="Invasion Fleet",
            description=(
                '<span class="kwb">TYRANIDS</span> model only. Once per turn, you can re-roll one Hit roll, one '
                "Wound roll, one Damage roll, one Advance roll, one Charge roll or one saving throw made for the bearer."
            ),
        )
        bearer = _make_unit("Broodlord", army, keywords=["CHARACTER"], faction_keywords=["TYRANIDS"])
        bearer.models = [_make_model("Broodlord", bearer, x=0.0, y=0.0, wounds=7)]
        bearer.enhancement = enhancement
        enhancement.apply_to_unit(bearer)
        army.units = [bearer]
        game.map.units = [bearer]
        game.rebuild_entity_registry()

        rule = build_perfectly_adapted_reroll_rule(unit=bearer, game=game, roll_type="advance")
        self.assertIsNotNone(rule)
        req = game.request_dice_roll(
            player_id=player.id,
            spec={
                "dice_count": 1,
                "faces": 6,
                "reason": "Advance roll",
                "roll_type": "advance",
                "unit_id": bearer._id,
                "fixed_dice": [1],
                "reroll_rules": [rule],
            },
            prompt="Advance roll",
        )
        self.assertIsNotNone(req)

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        roll_request = pending[0]
        self.assertEqual(roll_request.decision_type, DECISION_REQUEST_DICE_ROLL)

        roll_option = list(roll_request.options or [])[0]
        resolve_decision_command(game, roll_request, roll_option.option_id, player_id=player.id)

        reroll_request = list(game.decision_queue.list() or [])[0]
        self.assertEqual(reroll_request.decision_type, DECISION_SELECT_DICE_REROLL)

        pa_option = next(
            option
            for option in list(reroll_request.options or [])
            if str((option.payload or {}).get("action_id", "")) == PERFECTLY_ADAPTED_ACTION_ID
        )
        roll_state = game.roll_manager.get_roll(int((reroll_request.context or {}).get("roll_id", 0) or 0))
        self.assertIsNotNone(roll_state)
        die_id = str(((roll_state.dice or [])[0] or {}).get("die_id", "") or "")
        self.assertTrue(bool(die_id))
        resolve_decision_command(
            game,
            reroll_request,
            pa_option.option_id,
            player_id=player.id,
            result_payload={"selected_die_ids": [die_id]},
        )

        used_key = str(bearer.special_rules.get("enhancement_perfectly_adapted_used_turn_key", "") or "")
        self.assertTrue(bool(used_key))
        self.assertIsNone(build_perfectly_adapted_reroll_rule(unit=bearer, game=game, roll_type="hit"))


if __name__ == "__main__":
    unittest.main()
