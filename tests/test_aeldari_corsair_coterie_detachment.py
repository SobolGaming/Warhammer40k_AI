import json
import types
import unittest
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _DummyUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.special_rules = {}
        self.enhancement = None
        self._parent_army = None

    @property
    def is_character(self) -> bool:
        return any(str(k).strip().upper() == "CHARACTER" for k in (self.keywords or []))

    @property
    def is_epic_hero(self) -> bool:
        return any(str(k).strip().upper() == "EPIC HERO" for k in (self.keywords or []))

    def get_effective_keywords(self):
        return list(self.keywords or [])

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords or [])

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        wounds: int = 3,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _load_enhancement(name: str) -> Enhancement:
    with open("wahapedia_data/Enhancements.json", "r", encoding="utf-8") as handle:
        rows = json.load(handle)
    row = next(item for item in rows if str(item.get("name", "")) == name)
    return Enhancement.from_waha_dict(row)


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_corsair_game():
    aeldari_army = Army("Aeldari", "Corsair Coterie")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    aeldari_player = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[aeldari_player, enemy_player])
    return game, aeldari_army, enemy_army, aeldari_player, enemy_player


class TestAeldariCorsairCoterieEnhancements(unittest.TestCase):
    def test_veterans_of_the_void_allows_non_character_anhrathe_enhancement(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"
        unit = _DummyUnit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enhancement = _load_enhancement("Infamy (Aura)")
        army.add_unit(unit)
        army.add_enhancement(enhancement, unit)
        self.assertIs(unit.enhancement, enhancement)

    def test_non_veterans_detachment_keeps_character_requirement(self):
        army = Army("Aeldari", "Warhost")
        army.faction_id = "AE"
        unit = _DummyUnit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enhancement = _load_enhancement("Infamy (Aura)")
        army.add_unit(unit)
        with self.assertRaises(ArmyValidationError):
            army.add_enhancement(enhancement, unit)

    def test_veterans_of_the_void_replaces_three_enhancement_cap(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"

        units = [
            _DummyUnit("Corsair Unit 1", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit("Corsair Unit 2", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit("Corsair Unit 3", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit(
                "Corsair Prince",
                keywords=["INFANTRY", "CHARACTER"],
                faction_keywords=["AELDARI", "ANHRATHE"],
            ),
        ]
        for unit in units:
            army.add_unit(unit)

        enhancements = [
            _load_enhancement("Infamy (Aura)"),
            _load_enhancement("Webway Pathstone"),
            _load_enhancement("Voidstone"),
            _load_enhancement("Archraider"),
        ]
        for unit, enhancement in zip(units, enhancements):
            army.add_enhancement(enhancement, unit)

        try:
            army.validate_enhancements()
        except ArmyValidationError as exc:
            self.fail(f"Veterans of the Void should allow 4 Corsair Enhancements here: {exc}")


class TestAeldariCorsairCoterieEnhancementEffects(unittest.TestCase):
    def test_infamy_aura_reduces_enemy_objective_control_to_minimum_one(self):
        game, aeldari_army, enemy_army, _aeldari_player, _enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Prince",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy_oc_one = _make_unit(
            "Enemy OC1",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        enemy_oc_two = _make_unit(
            "Enemy OC2",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=2,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy_oc_one, x=1.0, y=0.0)
        _set_model_location(enemy_oc_two, x=1.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy_oc_one)
        enemy_army.add_unit(enemy_oc_two)
        aeldari_army.add_enhancement(_load_enhancement("Infamy (Aura)"), source)

        game.map.units = [source, enemy_oc_one, enemy_oc_two]

        self.assertEqual(int(enemy_oc_one.models[0].objective_control), 1)
        self.assertEqual(int(enemy_oc_two.models[0].objective_control), 1)

    def test_voidstone_grants_5_plus_invulnerable_save_to_bearer_unit(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"
        unit = _make_unit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        army.add_unit(unit)
        army.add_enhancement(_load_enhancement("Voidstone"), unit)

        invuln, source = unit.get_model_invulnerable_save_override(unit.models[0])
        self.assertEqual(int(invuln or 0), 5)
        self.assertIn("Voidstone", str(source))

    def test_webway_pathstone_grants_deep_strike_and_end_of_opponent_turn_reposition(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy, x=10.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        aeldari_army.add_enhancement(_load_enhancement("Webway Pathstone"), source)

        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        self.assertTrue(source.has_deep_strike())

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str((request.context or {}).get("ability_key", "")), "webway_pathstone")

        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=aeldari_player.id)

        self.assertTrue(source.is_in_strategic_reserves())
        self.assertTrue(source.has_used_unit_once_per_battle("webway_pathstone"))

    def test_archraider_applies_targeted_stratagem_cp_increase_within_12_of_bearer_model(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Prince",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy, x=10.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        aeldari_army.add_enhancement(_load_enhancement("Archraider"), source)

        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        specs = list(source.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("source_model_id", "")), str(source.models[0].id))

        preview_in = aeldari_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertTrue(bool(preview_in.get("auto")))

        applied_in = aeldari_player.apply_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertEqual(int(applied_in.get("increase", 0) or 0), 1)

        _set_model_location(enemy, x=20.0, y=0.0)
        preview_out = aeldari_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertFalse(bool(preview_out.get("auto")))
        self.assertFalse(bool(preview_out.get("optional")))


class TestAeldariCorsairCoterieDetachmentRules(unittest.TestCase):
    def _build_game(self):
        return _build_corsair_game()

    def test_relentless_raiders_applies_mortal_wounds_on_enemy_move(self):
        game, aeldari_army, enemy_army, _aeldari_player, _enemy_player = self._build_game()
        anhrathe = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(anhrathe, x=0.0, y=0.0)
        _set_model_location(enemy, x=0.0, y=0.0)

        aeldari_army.add_unit(anhrathe)
        enemy_army.add_unit(enemy)
        game.map.units = [anhrathe, enemy]

        point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=point,
        )
        game.map.objectives = [objective]

        applied = []

        def _apply_mortals(self, target_unit, amount, game_map=None):
            applied.append(int(amount))
            return int(amount)

        enemy._apply_mortal_wounds_to_unit = types.MethodType(_apply_mortals, enemy)

        with patch("warhammer40k_ai.rules.aeldari_detachments.get_roll", side_effect=[2, 3]):
            game.event_system.publish("unit_move_ended", unit=enemy, action="move")

        self.assertEqual(applied, [3])

    def test_void_thieves_applies_sticky_control_at_phase_end(self):
        game, aeldari_army, _enemy_army, aeldari_player, enemy_player = self._build_game()
        anhrathe = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        _set_model_location(anhrathe, x=0.0, y=0.0)
        aeldari_army.add_unit(anhrathe)
        game.map.units = [anhrathe]

        point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=point,
        )
        game.map.objectives = [objective]

        game.event_system.publish(
            "phase_end",
            player=enemy_player,
            phase=BattleRoundPhases.SHOOTING_PHASE,
        )

        self.assertIs(point.sticky_controller, aeldari_player)
        self.assertEqual(str(point.sticky_source), "void_thieves")


if __name__ == "__main__":
    unittest.main()
