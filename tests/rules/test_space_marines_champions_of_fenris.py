import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": str(save),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Champions of Fenris"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"

    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=enemy_army)
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    game.add_player(enemy_player)
    game.add_player(sm_player)
    game.current_player_index = 0

    return game, enemy_player, sm_player, sm_army, enemy_army


class TestSpaceMarinesChampionsOfFenris(unittest.TestCase):
    def test_terminator_units_gain_oc_while_not_battle_shocked(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        game, _enemy_player, _sm_player, sm_army, _enemy_army = _build_game("Champions of Fenris")
        terminator_unit = _make_unit(
            "Wolf Guard Terminators",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        infantry_unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(terminator_unit)
        sm_army.add_unit(infantry_unit)
        terminator_unit.deployed = True
        infantry_unit.deployed = True

        self.assertEqual(int(terminator_unit.objective_control), 2)
        self.assertEqual(int(infantry_unit.objective_control), 1)

        terminator_unit.apply_status_effect(BattleShockEffect(current_turn=game.turn))
        self.assertTrue(terminator_unit.is_battle_shocked())
        self.assertEqual(int(terminator_unit.objective_control), 0)

    def test_phase_end_queues_reactive_charge_decision(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases

        game, enemy_player, _sm_player, sm_army, enemy_army = _build_game("Champions of Fenris")
        game.phase = BattleRoundPhases.CHARGE_PHASE

        reacting_unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy_unit = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(reacting_unit)
        enemy_army.add_unit(enemy_unit)
        reacting_unit.deployed = True
        enemy_unit.deployed = True

        reacting_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy_unit.models[0].set_location(2.5, 0.0, 0.0, 0.0)
        game.map.units = [reacting_unit, enemy_unit]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str(getattr(req, "context", {}).get("ability", "") or "") == "great_wolf_watches_charge"
        ]

        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(getattr(request, "context", {}).get("unit_id", "") or ""), str(reacting_unit.id))
        labels = [str(getattr(opt, "label", "") or "") for opt in list(getattr(request, "options", []) or [])]
        self.assertIn("None", labels)

    def test_great_wolf_watches_choice_attempts_out_of_turn_charge_without_bonus(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.engine.phase import BattleRoundPhases
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, enemy_player, sm_player, sm_army, enemy_army = _build_game("Champions of Fenris")
        game.phase = BattleRoundPhases.CHARGE_PHASE

        reacting_unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy_unit = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(reacting_unit)
        enemy_army.add_unit(enemy_unit)
        reacting_unit.deployed = True
        enemy_unit.deployed = True

        reacting_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy_unit.models[0].set_location(2.5, 0.0, 0.0, 0.0)
        game.map.units = [reacting_unit, enemy_unit]
        game.rebuild_entity_registry()

        game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str(getattr(req, "context", {}).get("ability", "") or "") == "great_wolf_watches_charge"
        )
        target_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(enemy_unit.id)
        )

        called = {}

        def _attempt_charge(unit, target, *, out_of_turn=False, count_as_charged=True):
            called["unit"] = unit
            called["target"] = target
            called["out_of_turn"] = bool(out_of_turn)
            called["count_as_charged"] = bool(count_as_charged)
            return True

        game.attempt_charge = _attempt_charge
        value, apply_result = resolve_decision_value(game, request, target_option.option_id, player_id=sm_player.id)

        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("unit_id", "")), str(reacting_unit.id))
        self.assertEqual(str((value or {}).get("target_unit_id", "")), str(enemy_unit.id))
        self.assertTrue(bool((value or {}).get("success", False)))
        self.assertEqual(called.get("unit"), reacting_unit)
        self.assertEqual(called.get("target"), enemy_unit)
        self.assertTrue(bool(called.get("out_of_turn", False)))
        self.assertFalse(bool(called.get("count_as_charged", True)))


if __name__ == "__main__":
    unittest.main()
