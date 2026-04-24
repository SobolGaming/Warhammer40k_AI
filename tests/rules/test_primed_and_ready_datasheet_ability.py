import unittest
from types import SimpleNamespace

from tests.decision_request_helpers import install_decision_request_support


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Genestealer Cults", abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "5",
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


def _make_unit(name, *, faction_name="Genestealer Cults", abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    ds = _MockDatasheet(
        name,
        faction_name=faction_name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(ds)


def _make_players(active_units, opponent_units, *, turn=1):
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army1 = Army.with_detachment("Active", "Test")
    army2 = Army.with_detachment("Opponent", "Test")
    army1.units = list(active_units if isinstance(active_units, (list, tuple)) else [active_units])
    army2.units = list(opponent_units if isinstance(opponent_units, (list, tuple)) else [opponent_units])

    for unit in army1.units:
        unit.set_parent_army(army1)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in army2.units:
        unit.set_parent_army(army2)
        unit.deployed = True
        unit.reserve_status = "deployed"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game = install_decision_request_support(SimpleNamespace(
        turn=turn,
        current_player_index=0,
        players=[p1, p2],
        phase=BattleRoundPhases.SHOOTING_PHASE,
        map=None,
    ))
    game.get_current_player = lambda: p1
    p1.set_game(game)
    p2.set_game(game)
    return p1, p2, game


def _grenade_stratagem():
    from warhammer40k_ai.rules.stratagems import Stratagem

    return Stratagem(
        id="grenade",
        name="Grenade",
        type="Core",
        description="",
        cp_cost=1,
        turn="Your",
        phase="Shooting phase",
        detachment="",
        faction_id="",
    )


class TestPrimedAndReadyDatasheetAbility(unittest.TestCase):
    def _primed_and_ready_unit_text(self):
        return {
            "name": "Primed and Ready",
            "description": (
                "In your Shooting phase, you can select one unit from your army with this ability as the target of "
                "the Grenade Stratagem for 0CP, provided that unit has not already been the target of that Stratagem "
                "this phase. This can allow you to use the Grenade Stratagem for a second time this phase."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

    def _primed_and_ready_model_text(self):
        return {
            "name": "Primed and Ready",
            "description": (
                "In your Shooting phase, you can select one model from your army with this ability as the target of "
                "the Grenade Stratagem for 0CP, provided that model has not already been the target of that Stratagem this phase."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

    def test_primed_and_ready_parser_supports_unit_and_model_wording(self):
        unit_text_unit = _make_unit(
            "Krieg Grenadiers",
            abilities=[self._primed_and_ready_unit_text()],
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        model_text_unit = _make_unit(
            "Reductus Saboteur",
            abilities=[self._primed_and_ready_model_text()],
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["GENESTEALER CULTS"],
        )

        unit_rule = unit_text_unit.get_primed_and_ready_grenade_rule()
        model_rule = model_text_unit.get_primed_and_ready_grenade_rule()

        self.assertIsNotNone(unit_rule)
        self.assertIsNotNone(model_rule)
        self.assertEqual(str(unit_rule.get("target_scope", "")), "unit")
        self.assertEqual(str(model_rule.get("target_scope", "")), "model")
        self.assertTrue(bool(unit_rule.get("allows_repeat", False)))
        self.assertTrue(bool(model_rule.get("allows_repeat", False)))

    def test_primed_and_ready_allows_repeat_grenade_for_zero_cp(self):
        primed = _make_unit(
            "Krieg Grenadiers",
            abilities=[self._primed_and_ready_unit_text()],
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        first_target = _make_unit(
            "Regular Grenadiers",
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        player, _opponent, game = _make_players([primed, first_target], enemy, turn=2)
        player.command_points = 0

        grenade = _grenade_stratagem()
        player.stratagems.available = [grenade]
        player.stratagems._used_stratagems_this_phase.add("GRENADE")
        player.stratagems._record_grenade_use(first_target)

        player.set_next_optional_decision("PRIMED_AND_READY_GRENADE", True)
        self.assertTrue(
            player.stratagems.can_use(
                "Grenade",
                target_unit=primed,
                unit=primed,
                enemy_unit=enemy,
                phase_name="Shooting phase",
            )
        )

        used = player.stratagems.use(
            "Grenade",
            target_unit=primed,
            unit=primed,
            enemy_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)
        self.assertTrue(bool(primed.primed_and_ready_grenade_targeted_this_phase(game)))
        self.assertTrue(bool(player._ability_used_this_phase("PRIMED_AND_READY_GRENADE")))

    def test_primed_and_ready_cannot_target_same_unit_twice_in_phase(self):
        primed = _make_unit(
            "Krieg Grenadiers",
            abilities=[self._primed_and_ready_unit_text()],
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        first_target = _make_unit(
            "Regular Grenadiers",
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        player, _opponent, _game = _make_players([primed, first_target], enemy, turn=2)
        player.command_points = 1

        grenade = _grenade_stratagem()
        player.stratagems.available = [grenade]
        player.stratagems._used_stratagems_this_phase.add("GRENADE")
        player.stratagems._record_grenade_use(first_target)

        player.set_next_optional_decision("PRIMED_AND_READY_GRENADE", True)
        self.assertTrue(
            player.stratagems.use(
                "Grenade",
                target_unit=primed,
                unit=primed,
                enemy_unit=enemy,
                phase_name="Shooting phase",
            )
        )

        player.set_next_optional_decision("PRIMED_AND_READY_GRENADE", True)
        self.assertFalse(
            player.stratagems.use(
                "Grenade",
                target_unit=primed,
                unit=primed,
                enemy_unit=enemy,
                phase_name="Shooting phase",
            )
        )


if __name__ == "__main__":
    unittest.main()
