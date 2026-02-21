import unittest
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
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


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


class TestNecronsDatasheetGroup3Abilities(unittest.TestCase):
    def test_crimson_harvest_parses_charge_end_mortal_table(self):
        ability = {
            "name": "Crimson Harvest",
            "description": (
                "Each time this model ends a Charge move, select one enemy unit within Engagement Range of this model and "
                "roll one D6: on a 2-5, that unit suffers D3 mortal wounds; on a 6, that unit suffers D3+3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Skorpekh Lord", abilities=[ability])
        entries = list(unit.special_rules.get("charge_end_mortal_wounds", []) or [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(str(entries[0].get("kind", "")), "table_d6_2_5_6")

    def test_self_destruction_parses_start_fight_malign_variant(self):
        ability = {
            "name": "Self-destruction",
            "description": (
                "At the start of the Fight phase, if this unit is within Engagement Range of one or more enemy units, "
                "you can select one model in this unit to destroy. If you do, select one enemy unit within Engagement "
                "Range of that model and roll one D6, adding 1 to the result if that unit is a VEHICLE. On a 2-5, that "
                "unit suffers D3 mortal wounds; on a 6+, that unit suffers 3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Canoptek Scarab Swarms", abilities=[ability])
        specs = unit.unit_start_fight_phase_malign_sacrifice_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("allow_any_model", False)))
        self.assertEqual(int(specs[0].get("roll_bonus_vs_vehicle", 0)), 1)
        self.assertEqual(str(specs[0].get("roll_low_mortal", "")), "d3")
        self.assertEqual(str(specs[0].get("roll_high_mortal", "")), "3")

    def test_living_lightning_parses_dice_pool_mortals(self):
        ability = {
            "name": "Living Lightning",
            "description": (
                "In your Shooting phase, select one enemy unit within 18\" of and visible to this model (excluding units "
                "with the Lone Operative ability that are not part of an Attached unit and are not within 12\" of this "
                "model) and roll four D6: for each 4+, that enemy unit suffers 1 mortal wound."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Plasmancer", abilities=[ability])
        specs = unit.model_start_shooting_phase_eater_plague_specs(unit.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("roll_mode", "")), "dice_pool_threshold")
        self.assertEqual(int(specs[0].get("dice_count", 0)), 4)
        self.assertEqual(int(specs[0].get("threshold", 0)), 4)
        self.assertEqual(str(specs[0].get("mortal_per_success", "")), "1")

    def test_matter_absorption_parses_vehicle_mortals_and_heal(self):
        ability = {
            "name": "Matter Absorption",
            "description": (
                "At the start of your Shooting phase, select one enemy VEHICLE unit within 12\" of this model and roll "
                "one D6: on a 2+, that enemy unit suffers D3 mortal wounds and this model regains up to that many lost wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("C'tan Shard of the Void Dragon", abilities=[ability])
        specs = unit.model_start_shooting_phase_corrupt_machine_spirits_specs(unit.models[0])
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("roll_mode", "")), "single_threshold")
        self.assertEqual(int(specs[0].get("threshold", 0)), 2)
        self.assertEqual(str(specs[0].get("mortal_on_success", "")), "d3")
        self.assertTrue(bool(specs[0].get("heal_self_on_success", False)))

    def test_malevolent_arcing_parses_thundershock(self):
        ability = {
            "name": "Malevolent Arcing",
            "description": (
                "In your Shooting phase, each time you select a target for this model's twin tesla destructor, roll one D6 "
                "for the target unit and one D6 for every other enemy unit within 3\" of the target unit. On a 5+, the unit "
                "being rolled for is struck by arcing energies; after resolving all of this model's attacks against the target "
                "unit, each unit struck by arcing energies suffers D3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Annihilation Barge", abilities=[ability])
        specs = unit.unit_thundershock_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0)), 3)
        self.assertEqual(int(specs[0].get("threshold", 0)), 5)
        self.assertEqual(str(specs[0].get("mortal_wounds", "")), "d3")

    def test_overwhelming_obliteration_grants_devastating_wounds_when_stationary(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ability = {
            "name": "Overwhelming Obliteration",
            "description": (
                "In your Movement phase, if this model Remains Stationary, until the end of the turn, "
                "its doomsday cannon has the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Doomsday Ark", abilities=[ability])
        target = _make_unit("Target")

        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        army_one = Army("A1", detachment_type="Test")
        army_two = Army("A2", detachment_type="Test")
        player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
        player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
        game.add_player(player_one)
        game.add_player(player_two)

        army_one.add_unit(attacker)
        army_two.add_unit(target)
        game.current_player_index = 0
        attacker.round_state.remained_stationary_this_round = True

        bonuses = attacker.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=attacker.models[0],
            weapon_name="Doomsday Cannon",
            target=target,
        )
        self.assertTrue(bool(bonuses.get("devastating_wounds", False)))

    def test_malign_sacrifice_roll_handler_uses_vehicle_bonus_profile(self):
        from warhammer40k_ai.engine.roll_handlers import handle_malign_sacrifice_roll
        from warhammer40k_ai.engine.dice_rolls import DiceRollState

        class _MockUnit:
            def __init__(self, name, *, is_vehicle=False):
                self.name = name
                self._is_vehicle = bool(is_vehicle)
                self._applied = []

            def has_any_keyword(self, kw):
                return self._is_vehicle and str(kw or "").upper() == "VEHICLE"

            def _apply_mortal_wounds_to_unit(self, target, amount, game_map=None):
                self._applied.append((target.name, int(amount)))

            def get_parent_army(self):
                class _Army:
                    player = None

                return _Army()

        class _MockModel:
            def __init__(self):
                self.dead = False
                self.name = "Scarab Base"

            def die(self, game_map=None):
                self.dead = True

        source = _MockUnit("Scarab Swarms")
        target = _MockUnit("Enemy Vehicle", is_vehicle=True)
        model = _MockModel()

        class _Game:
            map = None

            def resolve_unit_by_id(self, uid):
                if uid == "source":
                    return source
                if uid == "target":
                    return target
                return None

            def resolve_model_by_id(self, mid):
                if mid == "model":
                    return model
                return None

        state = DiceRollState(
            roll_id=1,
            player_id="p",
            spec={
                "source_unit_id": "source",
                "target_unit_id": "target",
                "model_id": "model",
                "ability_name": "Self-destruction",
                "roll_bonus_vs_vehicle": 1,
                "roll_low_min": 2,
                "roll_low_max": 5,
                "roll_low_mortal": "d3",
                "roll_high_threshold": 6,
                "roll_high_mortal": "3",
                "destroy_selected_model": True,
            },
            status="resolved",
            dice=[{"id": "d1", "value": 5, "faces": 6}],
            total=5,
        )
        with (
            patch(
                "warhammer40k_ai.engine.roll_handlers._get_unit",
                side_effect=lambda _game, uid: source if uid == "source" else target if uid == "target" else None,
            ),
            patch(
                "warhammer40k_ai.engine.roll_handlers._get_model",
                side_effect=lambda _game, mid: model if mid == "model" else None,
            ),
        ):
            result = handle_malign_sacrifice_roll(_Game(), state)
        self.assertEqual(int(result or 0), 3)
        self.assertEqual(source._applied, [("Enemy Vehicle", 3)])
        self.assertTrue(bool(model.dead))


if __name__ == "__main__":
    unittest.main()
