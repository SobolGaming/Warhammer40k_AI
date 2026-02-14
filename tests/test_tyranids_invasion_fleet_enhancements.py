import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
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


if __name__ == "__main__":
    unittest.main()
