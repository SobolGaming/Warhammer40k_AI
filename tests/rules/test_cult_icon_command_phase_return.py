import unittest
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        model_count: int = 1,
        abilities=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(*, name, datasheet_id, model_count=1, abilities=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name=name,
        datasheet_id=datasheet_id,
        model_count=model_count,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


def _make_game_with_player(unit):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army = Army.with_detachment("Genestealer Cults", "Other")
    army.faction_id = "GSC"
    army.add_unit(unit)
    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def _remove_first_models(unit, count: int):
    removed = []
    for _ in range(int(count)):
        model = unit.models[0]
        unit.remove_model(model)
        removed.append(model)
    return removed


class TestCultIconCommandPhaseReturn(unittest.TestCase):
    _VARIANT_D3_OR_3 = (
        "In your Command phase, you can return up to D3 destroyed models to the bearer's unit. "
        "If the bearer's unit is within range of an objective marker you control, you can return up to 3 destroyed models to that unit instead. "
        "This ability cannot be used to return destroyed Character models in Attached units and any [ONE SHOT] weapons equipped by returned models "
        "that were shot before they were destroyed are still considered to have been shot."
    )

    _VARIANT_3_OR_D3_PLUS_3 = (
        "In your Command phase, you can return up to 3 destroyed models to the bearer's unit. "
        "If the bearer's unit is within range of an objective marker you control, you can return up to D3+3 destroyed models to that unit instead. "
        "This ability cannot be used to return destroyed Character models in Attached units and any [ONE SHOT] weapons equipped by returned models "
        "that were shot before they were destroyed are still considered to have been shot."
    )

    def test_parser_supports_cult_icon_d3_or_3_variant(self):
        ability = {
            "name": "Cult Icon",
            "description": self._VARIANT_D3_OR_3,
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(name="Hybrid Metamorphs", datasheet_id="culticon1", model_count=5, abilities=[ability])

        spec = unit.get_command_phase_unit_return_ability()
        self.assertIsNotNone(spec)
        self.assertEqual(int(spec.get("amount", 0) or 0), 3)
        self.assertEqual(str(spec.get("amount_roll", "") or "").upper(), "D3")
        self.assertEqual(int(spec.get("controlled_objective_amount", 0) or 0), 3)
        self.assertEqual(str(spec.get("controlled_objective_amount_roll", "") or ""), "")
        self.assertTrue(bool(spec.get("exclude_character", False)))

    def test_parser_supports_cult_icon_3_or_d3_plus_3_variant(self):
        ability = {
            "name": "Cult Icon",
            "description": self._VARIANT_3_OR_D3_PLUS_3,
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(name="Neophyte Hybrids", datasheet_id="culticon2", model_count=10, abilities=[ability])

        spec = unit.get_command_phase_unit_return_ability()
        self.assertIsNotNone(spec)
        self.assertEqual(int(spec.get("amount", 0) or 0), 3)
        self.assertEqual(str(spec.get("amount_roll", "") or ""), "")
        self.assertEqual(int(spec.get("controlled_objective_amount", 0) or 0), 6)
        self.assertEqual(str(spec.get("controlled_objective_amount_roll", "") or "").upper(), "D3+3")
        self.assertTrue(bool(spec.get("exclude_character", False)))

    def test_command_phase_uses_controlled_objective_amount_and_excludes_character_models(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Cult Icon",
            "description": self._VARIANT_D3_OR_3,
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(name="Hybrid Metamorphs", datasheet_id="culticon3", model_count=5, abilities=[ability])
        unit.deployed = True
        unit.reserve_status = "deployed"

        non_character_destroyed = _remove_first_models(unit, 2)

        leader = _make_unit(name="Attached Leader", datasheet_id="culticon_leader", model_count=1)
        leader.keywords = ["CHARACTER"]
        leader.deployed = True
        leader.reserve_status = "deployed"
        character_destroyed = _remove_first_models(leader, 1)[0]
        unit.models_lost.append(character_destroyed)
        unit._within_controlled_objective_range = lambda _game_map=None: True

        game, player = _make_game_with_player(unit)

        with patch("warhammer40k_ai.utility.dice.get_roll") as mock_roll:
            game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        mock_roll.assert_not_called()

        pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = dict(request.context or {})
        self.assertEqual(str(ctx.get("selection_kind", "")), "bodyguard_return")
        self.assertEqual(int(ctx.get("remaining", 0) or 0), 3)

        option_model_ids = {
            str((opt.payload or {}).get("model_id"))
            for opt in list(request.options or [])
            if (opt.payload or {}).get("model_id") not in (None, "")
        }
        expected_non_character_ids = {str(get_entity_id(model)) for model in non_character_destroyed}
        for model_id in expected_non_character_ids:
            self.assertIn(model_id, option_model_ids)
        self.assertNotIn(str(get_entity_id(character_destroyed)), option_model_ids)

    def test_command_phase_rolls_d3_plus_3_when_controlled_objective_variant_applies(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.engine.game import BattleRoundPhases

        ability = {
            "name": "Cult Icon",
            "description": self._VARIANT_3_OR_D3_PLUS_3,
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(name="Neophyte Hybrids", datasheet_id="culticon4", model_count=6, abilities=[ability])
        unit.deployed = True
        unit.reserve_status = "deployed"
        _remove_first_models(unit, 5)
        unit._within_controlled_objective_range = lambda _game_map=None: True

        game, player = _make_game_with_player(unit)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5) as mock_roll:
            game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        mock_roll.assert_called_once_with("D3+3")

        pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = dict(request.context or {})
        self.assertEqual(str(ctx.get("selection_kind", "")), "bodyguard_return")
        self.assertEqual(int(ctx.get("remaining", 0) or 0), 5)

    def test_returned_model_keeps_one_shot_expended_state(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        ability = {
            "name": "Cult Icon",
            "description": self._VARIANT_3_OR_D3_PLUS_3,
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(name="Neophyte Hybrids", datasheet_id="culticon5", model_count=3, abilities=[ability])
        unit.deployed = True
        unit.reserve_status = "deployed"

        returned_model = _remove_first_models(unit, 1)[0]
        setattr(returned_model, "_one_shot_used", {"demo_one_shot"})

        game, player = _make_game_with_player(unit)
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

        pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertEqual(len(pending), 1)
        request = pending[0]

        chosen_option_id = None
        wanted_model_id = str(get_entity_id(returned_model))
        for option in list(request.options or []):
            payload = option.payload or {}
            if str(payload.get("model_id", "")) == wanted_model_id:
                chosen_option_id = option.option_id
                break
        self.assertIsNotNone(chosen_option_id)

        resolve_decision_command(game, request, chosen_option_id, player_id=player.id)

        self.assertIn(returned_model, list(unit.models or []))
        self.assertEqual(getattr(returned_model, "_one_shot_used", set()), {"demo_one_shot"})


if __name__ == "__main__":
    unittest.main()
