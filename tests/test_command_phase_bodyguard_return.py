import unittest


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
                "T": "4",
                "Sv": "3",
                "W": "2",
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
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(*, name, datasheet_id, model_count=1, abilities=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        datasheet_id,
        model_count=model_count,
        abilities=abilities,
        attached_to=attached_to,
    )
    return Unit(datasheet)


class TestCommandPhaseBodyguardReturn(unittest.TestCase):
    def test_command_phase_returns_bodyguard_model(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command

        ability = {
            "name": "Rage Eternal",
            "description": (
                "While this model is leading a unit, in your Command phase, you can return 1 destroyed "
                "Bodyguard model to that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

        bodyguard = _make_unit(name="Jakhals", datasheet_id="bodyguard1", model_count=2)
        leader = _make_unit(
            name="Slaughterbound",
            datasheet_id="leader1",
            abilities=[ability],
            attached_to=["bodyguard1"],
        )

        army = Army("Test Faction", "Detachment")
        army.faction_id = "TF"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        bodyguard.deployed = True
        bodyguard.reserve_status = "deployed"
        leader.deployed = True
        leader.reserve_status = "deployed"

        lost_model = bodyguard.models[0]
        bodyguard.remove_model(lost_model)
        self.assertEqual(len(bodyguard.models), 1)
        self.assertEqual(len(bodyguard.models_lost), 1)

        player = Player("P1", control=PlayerControl.REMOTE, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_ALLOCATE_DAMAGE)
        ctx = request.context or {}
        self.assertEqual(ctx.get("selection_kind"), "bodyguard_return")

        from warhammer40k_ai.utility.entity_ids import get_entity_id

        option_id = None
        lost_id = get_entity_id(lost_model)
        for opt in list(request.options or []):
            payload = opt.payload or {}
            if payload.get("model_id") == lost_id:
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

        self.assertEqual(len(bodyguard.models), 2)
        self.assertEqual(len(bodyguard.models_lost), 0)

    def test_bodyguard_return_requires_attached_bodyguards(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ability = {
            "name": "Rage Eternal",
            "description": (
                "While this model is leading a unit, in your Command phase, you can return 1 destroyed "
                "Bodyguard model to that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

        bodyguard = _make_unit(name="Jakhals", datasheet_id="bodyguard1", model_count=1)
        leader = _make_unit(
            name="Slaughterbound",
            datasheet_id="leader1",
            abilities=[ability],
            attached_to=["bodyguard1"],
        )

        army = Army("Test Faction", "Detachment")
        army.faction_id = "TF"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        bodyguard.deployed = True
        bodyguard.reserve_status = "deployed"
        leader.deployed = True
        leader.reserve_status = "deployed"

        lost_model = bodyguard.models[0]
        bodyguard.remove_model(lost_model)
        self.assertEqual(len(bodyguard.models), 0)
        self.assertEqual(len(bodyguard.models_lost), 1)

        player = Player("P1", control=PlayerControl.REMOTE, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertEqual(len(pending), 0)
        self.assertEqual(len(bodyguard.models), 0)
        self.assertEqual(len(bodyguard.models_lost), 1)


if __name__ == "__main__":
    unittest.main()
