import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_FRENZY_TARGET,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestFrenzy(unittest.TestCase):
    def _make_unit(self, name, army, *, frenzy=False):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = "A"
        unit.deployed = True
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit._ability_cache = {}
        if frenzy:
            desc = (
                "In your opponent's Shooting phase, and in the Fight phase, "
                "each time an enemy unit targets this model, after that unit has finished "
                "making its attacks, this model can either shoot or fight, but when resolving "
                "those attacks it can only target that enemy unit (and only if it is an eligible target)."
            )
            unit.possible_abilities = [Ability("Frenzy", "WE", desc, "Datasheet")]
        return unit

    def test_frenzy_prompt_published_on_enemy_shooting(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", PlayerControl.LOCAL, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = self._make_unit("Shooter", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [object()]
        defender.models = [object()]
        army1.units = [attacker]
        army2.units = [defender]
        game.map.units = [attacker, defender]

        game._frenzy_has_eligible_shot = lambda *_a, **_k: True
        game._frenzy_can_fight_target = lambda *_a, **_k: False

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("frenzy_prompt", _capture)
        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[defender],
        )
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={},
        )

        self.assertEqual(len(prompts), 1)
        self.assertIs(prompts[0].get("unit"), defender)
        self.assertIs(prompts[0].get("attacker_unit"), attacker)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CHOOSE_FRENZY_TARGET
        )
        self.assertEqual(str((request.context or {}).get("ability", "")), "frenzy")

    def test_frenzy_can_trigger_multiple_times_in_same_phase(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", PlayerControl.LOCAL, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = self._make_unit("Shooter", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [object()]
        defender.models = [object()]
        army1.units = [attacker]
        army2.units = [defender]
        game.map.units = [attacker, defender]

        game._frenzy_has_eligible_shot = lambda *_a, **_k: True
        game._frenzy_can_fight_target = lambda *_a, **_k: False

        prompts = []
        game.event_system.subscribe("frenzy_prompt", lambda **kwargs: prompts.append(kwargs))

        for _ in range(2):
            game.event_system.publish(
                "shooting_targets_selected",
                attacking_unit=attacker,
                target_units=[defender],
            )
            game.event_system.publish(
                "unit_shooting_resolved",
                attacker_unit=attacker,
                hits_by_target={},
            )

        self.assertEqual(len(prompts), 2)

    def test_frenzy_fight_option_allows_pile_in_range(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", PlayerControl.LOCAL, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.FIGHT_PHASE

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        army1.units = [attacker]
        army2.units = [defender]

        attacker_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker
        attacker_model.set_location(5.0, 0.0, 0.0, 0.0)
        attacker.models = [attacker_model]

        defender_model = Model(
            name="Helbrute",
            movement=6,
            toughness=7,
            save=3,
            wounds=8,
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        defender_model.parent_unit = defender
        defender_model.set_location(0.0, 0.0, 0.0, 0.0)
        defender.models = [defender_model]

        game.map.units = [attacker, defender]

        game._frenzy_has_eligible_shot = lambda *_a, **_k: False

        options = game._frenzy_available_actions(defender, attacker, phase_name="FIGHT_PHASE")
        self.assertIn("fight", options)

    def test_frenzy_fight_option_requires_engagement_in_shooting_phase(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", PlayerControl.LOCAL, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        army1.units = [attacker]
        army2.units = [defender]

        attacker_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker
        attacker_model.set_location(5.0, 0.0, 0.0, 0.0)
        attacker.models = [attacker_model]

        defender_model = Model(
            name="Helbrute",
            movement=6,
            toughness=7,
            save=3,
            wounds=8,
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        defender_model.parent_unit = defender
        defender_model.set_location(0.0, 0.0, 0.0, 0.0)
        defender.models = [defender_model]

        game.map.units = [attacker, defender]

        options = game._frenzy_available_actions(defender, attacker, phase_name="SHOOTING_PHASE")
        self.assertNotIn("fight", options)

        attacker_model.set_location(2.0, 0.0, 0.0, 0.0)
        options_engaged = game._frenzy_available_actions(defender, attacker, phase_name="SHOOTING_PHASE")
        self.assertIn("fight", options_engaged)

    def test_frenzy_in_fight_phase_can_offer_shoot_option_when_eligible(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army1)
        p2 = Player("P2", PlayerControl.LOCAL, army=army2)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.FIGHT_PHASE

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [object()]
        defender.models = [object()]
        game._frenzy_has_eligible_shot = lambda *_a, **_k: True
        game._frenzy_can_fight_target = lambda *_a, **_k: False

        options = game._frenzy_available_actions(defender, attacker, phase_name="FIGHT_PHASE")
        self.assertIn("shoot", options)

    def test_frenzy_shooting_uses_out_of_phase(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.REMOTE, army=army1)
        p2 = Player("P2", PlayerControl.REMOTE, army=army2)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [object()]
        defender.models = [object()]

        captured = {}

        def _fake_execute(_decls, _map, *, out_of_phase=False):
            captured["out_of_phase"] = bool(out_of_phase)
            return True

        defender.execute_shooting_declarations = _fake_execute
        game._build_frenzy_shooting_declarations = lambda *_a, **_k: [{"weapon_profile": object(), "target_unit": attacker, "models": [object()]}]

        ok = game._execute_frenzy_shooting(defender, attacker)
        self.assertTrue(ok)
        self.assertTrue(captured.get("out_of_phase", False))

    def test_frenzy_fight_does_not_mark_unit_as_fought(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.REMOTE, army=army1)
        p2 = Player("P2", PlayerControl.REMOTE, army=army2)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.FIGHT_PHASE

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [object()]
        defender.models = [object()]
        defender.round_state.fought_this_phase = False

        game._frenzy_can_fight_target = lambda *_a, **_k: True
        game.resolve_frenzy_melee_attacks = lambda *_a, **_k: None

        with self.assertRaisesRegex(RuntimeError, "DECLARE_MELEE_WEAPONS"):
            game._execute_frenzy_fight(defender, attacker, phase_name="FIGHT_PHASE")
        self.assertFalse(bool(getattr(defender.round_state, "fought_this_phase", False)))

    def test_has_frenzy_filters_non_helbrute_text(self):
        unit = self._make_unit("Helbrute", Army.with_detachment("Army A", "Detachment A"), frenzy=True)
        unit.models = [object()]
        self.assertTrue(unit.has_frenzy())

        other = self._make_unit("Other", Army.with_detachment("Army B", "Detachment B"), frenzy=False)
        other.models = [object()]
        other.possible_abilities = [
            Ability(
                "Frenzy",
                "XX",
                "Each time an enemy unit is selected to shoot or fight, after it has finished making its attacks, "
                "if one or more of those attacks targeted this model and this model is not destroyed, this model can "
                "fight as if it were the Fight phase.",
                "Datasheet",
            )
        ]
        other._ability_cache = {}
        self.assertFalse(other.has_frenzy())


    def test_frenzy_shoot_choice_queues_declare_shots_request(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.REMOTE, army=army1)
        p2 = Player("P2", PlayerControl.REMOTE, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = self._make_unit("Shooter", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [SimpleNamespace(_id="shooter-model")]
        defender.models = [SimpleNamespace(_id="helbrute-model")]
        army1.units = [attacker]
        army2.units = [defender]
        game.map.units = [attacker, defender]
        game.rebuild_entity_registry()

        game._frenzy_has_eligible_shot = lambda *_a, **_k: True
        game._frenzy_can_fight_target = lambda *_a, **_k: False

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[defender],
        )
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={},
        )

        frenzy_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CHOOSE_FRENZY_TARGET
        )
        shoot_option = next(
            opt
            for opt in list(frenzy_request.options or [])
            if str((opt.payload or {}).get("action", "")) == "shoot"
        )

        def _fake_queue_declare_shots_request(*_args, **kwargs):
            request = DecisionRequest.create(
                DECISION_DECLARE_SHOTS,
                "Frenzy: Declare shots",
                player_id=p2.id,
                options=[
                    DecisionOption.create(
                        "Confirm",
                        payload={"action": "confirm", "unit_id": get_entity_id(defender)},
                    ),
                    DecisionOption.create(
                        "Skip",
                        payload={"action": "skip", "unit_id": get_entity_id(defender)},
                    ),
                ],
                context=dict(kwargs.get("context", {}) or {}),
            )
            game.request_decision(request)
            return request

        with patch("warhammer40k_ai.engine.decision_requests.queue_declare_shots_request", side_effect=_fake_queue_declare_shots_request):
            result = resolve_decision_command(game, frenzy_request, shoot_option.option_id, player_id=p2.id)
        self.assertTrue(result.ok)

        declare_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_DECLARE_SHOTS
        )
        self.assertTrue(bool((declare_request.context or {}).get("frenzy_flow", False)))
        self.assertEqual(str((declare_request.context or {}).get("force_target_unit_id", "")), str(get_entity_id(attacker)))

    def test_frenzy_fight_choice_queues_pile_in_move_request(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.REMOTE, army=army1)
        p2 = Player("P2", PlayerControl.REMOTE, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        attacker.models = [SimpleNamespace(_id="enemy-model")]
        defender.models = [SimpleNamespace(_id="helbrute-model")]
        army1.units = [attacker]
        army2.units = [defender]
        game.map.units = [attacker, defender]
        game.rebuild_entity_registry()

        game._frenzy_has_eligible_shot = lambda *_a, **_k: False
        game._frenzy_can_fight_target = lambda *_a, **_k: True

        game.event_system.publish(
            "fight_targets_selected",
            attacking_unit=attacker,
            target_units=[defender],
        )
        game.event_system.publish(
            "fight_attacks_resolved",
            unit=attacker,
            target_unit=defender,
        )

        frenzy_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_CHOOSE_FRENZY_TARGET
        )
        fight_option = next(
            opt
            for opt in list(frenzy_request.options or [])
            if str((opt.payload or {}).get("action", "")) == "fight"
        )

        result = resolve_decision_command(game, frenzy_request, fight_option.option_id, player_id=p2.id)
        self.assertTrue(result.ok)

        move_request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if req.decision_type == DECISION_MOVE_UNIT
        )
        self.assertEqual(str((move_request.context or {}).get("movement_type", "")), "pile_in")
        self.assertTrue(bool((move_request.context or {}).get("frenzy_flow", False)))

    def test_frenzy_declare_melee_followup_resolves_without_missing_decision_kind(self):
        army1 = Army.with_detachment("Army A", detachment_type="Detachment A")
        army2 = Army.with_detachment("Army B", detachment_type="Detachment B")
        p1 = Player("P1", PlayerControl.REMOTE, army=army1)
        p2 = Player("P2", PlayerControl.REMOTE, army=army2)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        attacker = self._make_unit("Enemy", army1)
        defender = self._make_unit("Helbrute", army2, frenzy=True)
        army1.units = [attacker]
        army2.units = [defender]
        game.map.units = [attacker, defender]
        game.rebuild_entity_registry()

        resolved_declarations = [{"weapon_profile": object(), "target_unit": attacker, "models": [object()]}]
        request = DecisionRequest.create(
            DECISION_DECLARE_MELEE_WEAPONS,
            "Frenzy: Declare melee weapons",
            player_id=p2.id,
            options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
            context={
                "frenzy_flow": True,
                "phase_name": "FIGHT_PHASE",
                "unit_id": str(get_entity_id(defender)),
                "attacker_unit_id": str(get_entity_id(attacker)),
            },
        )
        request._resolved_decision_value = list(resolved_declarations)
        resolved = []
        queued = []
        game.resolve_frenzy_melee_attacks = lambda *args, **_kwargs: resolved.append(args)
        game._queue_frenzy_fight_move_request = lambda **kwargs: queued.append(kwargs)

        game._maybe_queue_frenzy_followup(request, object())

        self.assertEqual(len(resolved), 1)
        self.assertEqual(queued[0]["movement_type"], "consolidate")

if __name__ == "__main__":
    unittest.main()

