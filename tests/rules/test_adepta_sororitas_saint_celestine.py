import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_value
from warhammer40k_ai.utility.model_base import Base, BaseType


HEALING_TEARS_TEXT = (
    "While this unit contains a Celestine model, in your Command phase, if this unit is below its Starting Strength, "
    "either one destroyed Geminae Superia model or up to D3 other Bodyguard models are returned to this unit."
)
LIFEWARDS_TEXT = "While this unit contains one or more Geminae Superia models, Celestine has the Feel No Pain 4+ ability."
MIRACULOUS_INTERVENTION_TEXT = (
    "The first time this unit's Celestine model is destroyed, roll one D6 at the end of the phase. "
    "On a 2+, set that Celestine model back up on the battlefield, as close as possible to where it was destroyed "
    "and not within Engagement Range of any enemy units, with its full wounds remaining."
)


class _SaintCelestineDatasheet:
    def __init__(self) -> None:
        self.name = "Saint Celestine"
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = ["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"]
        self.faction_keywords = ["ADEPTA SORORITAS"]
        self.datasheets_unit_composition = [
            {"description": "1 Celestine"},
            {"description": "2 Geminae Superia"},
        ]
        self.datasheets_models_cost = [{"description": "3 models", "cost": 150}]
        self.datasheets_models = [
            {
                "name": "Celestine",
                "M": "12",
                "T": "3",
                "Sv": "2",
                "W": "6",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            },
            {
                "name": "Geminae Superia",
                "M": "12",
                "T": "3",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            },
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {"name": "Healing Tears", "description": HEALING_TEARS_TEXT, "type": "Datasheet", "parameter": ""},
            {"name": "Lifewards", "description": LIFEWARDS_TEXT, "type": "Datasheet", "parameter": ""},
            {
                "name": "Miraculous Intervention",
                "description": MIRACULOUS_INTERVENTION_TEXT,
                "type": "Datasheet",
                "parameter": "",
            },
        ]
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_aux_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=3,
        save=3,
        wounds=1,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.wounds = 0
    return model


def _setup_game_with_unit(unit: Unit):
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    army = Army.with_detachment("Adepta Sororitas", detachment_type="Other")
    army.faction_id = "AS"
    player = Player("Sororitas", PlayerControl.LOCAL, army=army)
    game.add_player(player)
    game.current_player_index = 0
    army.add_unit(unit)
    unit.deployed = True
    game.map.units = [unit]
    game.rebuild_entity_registry()
    return game, player, army


class TestAdeptaSororitasSaintCelestine(unittest.TestCase):
    def test_lifewards_requires_geminae_and_only_applies_to_celestine(self):
        unit = Unit(_SaintCelestineDatasheet())
        celestine = next(model for model in unit.models if "celestine" in str(model.name).lower())
        geminae = [model for model in unit.models if "geminae" in str(model.name).lower()]

        self.assertIn((4, None), unit.has_feel_no_pain(target_model=celestine))
        self.assertNotIn((4, None), unit.has_feel_no_pain(target_model=geminae[0]))

        unit.models = [model for model in unit.models if "geminae" not in str(model.name).lower()]
        self.assertNotIn((4, None), unit.has_feel_no_pain(target_model=celestine))

    def test_miraculous_intervention_only_triggers_for_celestine_model(self):
        unit = Unit(_SaintCelestineDatasheet())
        game, player, _army = _setup_game_with_unit(unit)
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        celestine = next(model for model in unit.models if "celestine" in str(model.name).lower())
        geminae = next(model for model in unit.models if "geminae" in str(model.name).lower())

        geminae.take_damage(99, game_map=game.map)
        self.assertEqual(len(list(getattr(game, "_phoenix_gem_pending", []) or [])), 0)

        celestine.take_damage(99, game_map=game.map)
        self.assertEqual(len(list(getattr(game, "_phoenix_gem_pending", []) or [])), 1)

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        returned = [model for model in unit.models if "celestine" in str(model.name).lower()]
        self.assertEqual(len(returned), 1)
        self.assertEqual(int(getattr(returned[0], "wounds", 0) or 0), 6)

    def test_healing_tears_mode_choice_and_geminae_return_resolution(self):
        unit = Unit(_SaintCelestineDatasheet())
        game, player, _army = _setup_game_with_unit(unit)
        game.phase = BattleRoundPhases.COMMAND_PHASE

        lost_geminae = next(model for model in unit.models if "geminae" in str(model.name).lower())
        unit.models.remove(lost_geminae)
        lost_geminae.wounds = 0
        unit.models_lost.append(lost_geminae)

        lost_other = _make_aux_model("Bodyguard Acolyte", unit)
        unit.models_lost.append(lost_other)

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(player=player, phase=BattleRoundPhases.COMMAND_PHASE)

        mode_request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_CHOOSE_QUARRY
            and str((req.context or {}).get("ability", "") or "") == "command_phase_miracle_discard_return_mode"
            and "healing tears" in str((req.context or {}).get("ability_name", "") or "").lower()
        )
        labels = [str(getattr(option, "label", "") or "") for option in list(mode_request.options or [])]
        self.assertTrue(any("geminae superia" in label.lower() for label in labels))
        self.assertTrue(any("other bodyguard models" in label.lower() for label in labels))

        geminae_option = next(
            option
            for option in list(mode_request.options or [])
            if "geminae superia" in str(getattr(option, "label", "") or "").lower()
        )
        _value, apply_result = resolve_decision_value(
            game,
            mode_request,
            geminae_option.option_id,
            player_id=player.id,
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        return_request = next(
            req
            for req in game.decision_queue.list()
            if req.decision_type == DECISION_ALLOCATE_DAMAGE
            and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
            and "healing tears" in str((req.context or {}).get("ability_name", "") or "").lower()
        )
        allowed_ids = set(str(v or "") for v in list((return_request.context or {}).get("allowed_model_ids", []) or []))
        self.assertEqual(len(allowed_ids), 1)
        self.assertIn(str(getattr(lost_geminae, "_id", "") or ""), allowed_ids)

        return_option = next(
            option
            for option in list(return_request.options or [])
            if str((dict(getattr(option, "payload", {}) or {}).get("model_id", "") or ""))
            == str(getattr(lost_geminae, "_id", "") or "")
        )
        _value, return_result = resolve_decision_value(
            game,
            return_request,
            return_option.option_id,
            player_id=player.id,
        )
        self.assertTrue(bool(getattr(return_result, "ok", False)))
        returned_ids = {str(getattr(model, "_id", "") or "") for model in list(unit.models or [])}
        self.assertIn(str(getattr(lost_geminae, "_id", "") or ""), returned_ids)


if __name__ == "__main__":
    unittest.main()
