import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestAdeptaSororitasHolyJudgement(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None):
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
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 2):
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

    def test_holy_judgement_queues_and_applies_chaos_modifier(self):
        army = Army("Adepta Sororitas", detachment_type="Other")
        army.faction_id = "AS"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "CSM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        holy_judgement = Ability(
            "Holy Judgement",
            "AS",
            (
                "At the start of your Shooting phase, select one enemy unit within 12\" of and visible to this unit's "
                "Ephrael Stern model. That unit must take a Battle-shock test, subtracting 2 from the result if it is "
                "a CHAOS unit. If the test is failed, that enemy unit suffers 3 mortal wounds."
            ),
            "Datasheet",
            "",
        )

        daemonifuge = self._make_unit(
            "Daemonifuge",
            army,
            faction_keywords=["ADEPTA SORORITAS"],
            keywords=["INFANTRY", "CHARACTER"],
        )
        ephrael = self._make_model("Ephrael Stern", daemonifuge, wounds=4)
        ephrael.abilities = {"Holy Judgement": holy_judgement}
        kyganil = self._make_model("Kyganil of the Bloody Tears", daemonifuge, wounds=4)
        kyganil.abilities = {}
        daemonifuge.models = [ephrael, kyganil]
        daemonifuge._has_line_of_sight_to_target = lambda _model, _target, _map: True

        def _apply_mortal_wounds(target_unit, amount, game_map=None):
            if not target_unit.models:
                return
            model = target_unit.models[0]
            model.wounds = max(0, int(model.wounds or 0) - int(amount or 0))

        daemonifuge._apply_mortal_wounds_to_unit = _apply_mortal_wounds

        enemy = self._make_unit(
            "Chaos Target",
            enemy_army,
            faction_keywords=["CHAOS", "HERETIC ASTARTES"],
            keywords=["INFANTRY"],
        )
        enemy_model = self._make_model("Chaos Marine", enemy, wounds=4)
        enemy_model.set_location(8.0, 0.0, 0.0, 0.0)
        enemy.models = [enemy_model]

        captured = {}

        def _pass_check():
            captured["modifier"] = int(enemy.special_rules.get("post_shoot_leadership_debuff_value", 0) or 0)
            return False

        enemy.pass_leadership_check = _pass_check

        army.units = [daemonifuge]
        enemy_army.units = [enemy]
        game.rebuild_entity_registry()

        before_wounds = int(enemy.models[0].wounds or 0)

        game._on_phase_start_shooting_phase_visible_battleshock(player=player, phase=game.phase)

        pending = [
            req for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("ability_name", "") or ""), "Holy Judgement")
        self.assertTrue(bool(ctx.get("use_leadership_test", False)))
        self.assertEqual(int(ctx.get("leadership_test_modifier_if_target_keyword", 0) or 0), -2)
        self.assertEqual(str(ctx.get("leadership_test_modifier_target_keyword", "") or ""), "CHAOS")
        self.assertEqual(int(ctx.get("fail_mortal_wounds", 0) or 0), 3)
        self.assertTrue(bool(ctx.get("leadership_test_counts_as_battle_shock", False)))

        resolved = resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)
        self.assertTrue(bool(getattr(resolved, "ok", False)))

        self.assertEqual(int(captured.get("modifier", 0) or 0), -2)
        self.assertEqual(int(enemy.models[0].wounds or 0), before_wounds - 3)
        self.assertTrue(bool(enemy.is_battle_shocked()))
        self.assertFalse(bool(enemy.special_rules.get("post_shoot_leadership_debuff_active", False)))


if __name__ == "__main__":
    unittest.main()
