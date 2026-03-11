import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        faction_name="Necrons",
    ):
        self.id = name
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


class _DummyPlayer:
    def __init__(self, army, *, choice=None):
        self.army = army
        self.name = "P1"
        self.id = "P1"
        self._choice = choice

    def get_army(self):
        return self.army

    def _choose_optional_value(self, _key, _options, _ctx):
        return self._choice


class _RegistryStub:
    def __init__(self, units, player=None):
        self._units = {str(getattr(u, "_id", "")): u for u in units}
        self._players = {}
        if player is not None:
            pid = str(getattr(player, "id", "") or "")
            if pid:
                self._players[pid] = player

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id))
        if kind == "player":
            return self._players.get(str(entity_id))
        return None


class _GameStub:
    def __init__(self, units, player=None):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.decision_queue = DecisionQueue()
        self.entity_registry = _RegistryStub(units, player=player)
        self.is_authoritative = True

    def request_decision(self, request):
        self.decision_queue.add(request)


class TestNecronsCommandPhaseEnhancements(unittest.TestCase):
    def _set_loc(self, unit, x, y):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)

    def test_demanding_leader_grants_fall_back_shoot_until_next_command_phase(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.rules.necrons_detachments import NecronsDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        demanding = Enhancement(
            id="demanding",
            name="Demanding Leader",
            faction_id="NEC",
            detachment="Starshatter Arsenal",
            description=(
                "NECRONS model only. In your Command phase, select one friendly Necrons Vehicle or "
                "Necrons Mounted unit (excluding Titanic units) within 6\" of the bearer. Until the "
                "start of your next Command phase, that unit is eligible to shoot in a turn in which it Fell Back."
            ),
        )

        bearer = _make_unit("Bearer", faction_keywords=["NECRONS"])
        bearer.enhancement = demanding
        demanding.apply_to_unit(bearer)

        target_a = _make_unit("Vehicle A", keywords=["VEHICLE"], faction_keywords=["NECRONS"])
        target_b = _make_unit("Mounted B", keywords=["MOUNTED"], faction_keywords=["NECRONS"])

        self._set_loc(bearer, 0, 0)
        self._set_loc(target_a, 4, 0)
        self._set_loc(target_b, 5, 0)

        army = SimpleNamespace(units=[bearer, target_a, target_b], faction_id="NEC", detachment_type="Starshatter Arsenal")
        player = _DummyPlayer(army, choice=target_b)
        army.player = player
        for u in army.units:
            u.set_parent_army(army)

        mgr = NecronsDetachmentManager(army)
        army.necrons_detachments = mgr

        game = _GameStub([bearer, target_a, target_b], player=player)
        mgr.on_command_phase_start(game=game, player=player)

        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        option = next(
            opt for opt in req.options if opt.payload.get("target_unit_id") == getattr(target_b, "_id", None)
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        self.assertFalse(target_a.special_rules.get("command_phase_fell_back_and_shoot_active", False))
        self.assertTrue(target_b.special_rules.get("command_phase_fell_back_and_shoot_active", False))
        self.assertTrue(Unit.has_fell_back_and_shoot(target_b))

        player._choice = None
        mgr.on_command_phase_start(game=game, player=player)
        self.assertFalse(target_b.special_rules.get("command_phase_fell_back_and_shoot_active", False))

    def test_chrono_impedance_fields_reduce_allocated_damage(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.rules.necrons_detachments import NecronsDetachmentManager
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        chrono = Enhancement(
            id="chrono",
            name="Chrono-impedance Fields",
            faction_id="NEC",
            detachment="Starshatter Arsenal",
            description=(
                "NECRONS model only. In your Command phase, select one friendly Necrons Vehicle or "
                "Necrons Mounted unit (excluding Titanic units) within 6\" of the bearer. Until the "
                "start of your next Command phase, each time an attack is allocated to a model in that unit, "
                "subtract 1 from the Damage characteristic of that attack."
            ),
        )

        bearer = _make_unit("Bearer", faction_keywords=["NECRONS"])
        bearer.enhancement = chrono
        chrono.apply_to_unit(bearer)

        target = _make_unit("Vehicle", keywords=["VEHICLE"], faction_keywords=["NECRONS"])
        self._set_loc(bearer, 0, 0)
        self._set_loc(target, 3, 0)

        army = SimpleNamespace(units=[bearer, target], faction_id="NEC", detachment_type="Starshatter Arsenal")
        player = _DummyPlayer(army)
        army.player = player
        for u in army.units:
            u.set_parent_army(army)

        mgr = NecronsDetachmentManager(army)
        army.necrons_detachments = mgr

        mgr.on_command_phase_start(game=None, player=player)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = SimpleNamespace(special_rules={}, get_parent_army=lambda: None)

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "2",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        profile = Wargear(data).profiles["default"]

        target_model = target.models[0]
        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 1)

        target.deployed = False
        mgr.on_command_phase_start(game=None, player=player)
        self.assertFalse(target.special_rules.get("allocated_damage_reductions", []), "Expected damage reduction to clear")

    def test_starshatter_enhancement_descriptors_registered(self):
        from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor

        dread = get_enhancement_tool_descriptor(enhancement_id="000009749002")
        self.assertIsNotNone(dread)
        self.assertIn("MONSTER", tuple(dread.effect_params.get("excluded_keywords", ())))
        self.assertIn("TITANIC", tuple(dread.effect_params.get("excluded_keywords", ())))

        nebuloscope = get_enhancement_tool_descriptor(enhancement_id="000009749003")
        self.assertIsNotNone(nebuloscope)
        self.assertEqual(nebuloscope.effect, "grant_weapon_keywords")

        demanding = get_enhancement_tool_descriptor(enhancement_id="000009749004")
        self.assertIsNotNone(demanding)
        self.assertEqual(float(demanding.effect_params.get("range_in", 0.0)), 6.0)

        chrono = get_enhancement_tool_descriptor(enhancement_id="000009749005")
        self.assertIsNotNone(chrono)
        self.assertEqual(int(chrono.effect_params.get("damage_modifier", 0)), -1)


if __name__ == "__main__":
    unittest.main()
