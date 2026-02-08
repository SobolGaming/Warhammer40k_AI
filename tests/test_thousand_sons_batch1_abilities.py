import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, model_count: int = 2):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = []
        self.faction_keywords = ["THOUSAND SONS"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, model_count: int = 2):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name, abilities=abilities, model_count=model_count))


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("P1", "Det")
    army1.faction_id = "TST"
    army2 = Army("P2", "Det")
    army2.faction_id = "TST"

    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _make_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestThousandSonsBatch1Abilities(unittest.TestCase):
    def test_ambushing_hunters_parses_horizontal_distance_condition(self):
        ability = {
            "name": "Ambushing Hunters",
            "description": (
                "At the end of your opponent’s turn, if this unit is more than 6\" horizontally away from all enemy units, "
                "you can remove this unit from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Tzaangors", abilities=[ability])
        parsed = unit.get_end_of_opponent_turn_strategic_reserves_ability()
        self.assertIsNotNone(parsed)
        self.assertEqual(int(parsed.get("min_enemy_distance_horiz", 0) or 0), 6)

    def test_ambushing_hunters_requires_more_than_six_horizontal(self):
        ability = {
            "name": "Ambushing Hunters",
            "description": (
                "At the end of your opponent’s turn, if this unit is more than 6\" horizontally away from all enemy units, "
                "you can remove this unit from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        unit = _make_unit("Tzaangors", abilities=[ability])
        enemy = _make_unit("Enemy")
        army2.add_unit(unit)
        army1.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        game.map.units = [unit, enemy]

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=p1)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 0)
        self.assertFalse(unit.is_in_strategic_reserves())

    def test_binding_tendrils_uses_pinned_parser(self):
        ability = {
            "name": "Binding Tendrils (Psychic)",
            "description": (
                "In your Shooting phase, after this model has shot, select one enemy INFANTRY unit hit by one or more of "
                "those attacks made with Arcane Fire. Until the start of your next turn, that unit is ensnared. While a "
                "unit is ensnared, subtract 2\" from its Move characteristic and subtract 2 from Charge rolls made for it."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Exalted Sorcerer on Disc", abilities=[ability], model_count=1)
        model = unit.models[0]
        specs = unit.model_post_shoot_pinned_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("move_penalty", 0)), -2)
        self.assertEqual(int(specs[0].get("charge_penalty", 0)), -2)
        self.assertIn("arcane", str(specs[0].get("weapon_key", "")).lower())

    def test_glimpse_of_eternity_detected_as_unmodified_six_ability(self):
        ability = {
            "name": "Glimpse of Eternity (Psychic)",
            "description": (
                "Once per turn, you can change the result of one Hit roll, one Wound roll or one saving throw "
                "made for this model to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Infernal Master", abilities=[ability], model_count=1)
        model = unit.models[0]
        specs = unit.model_once_per_battle_unmodified_six_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].get("limit"), "battle_round")

    def test_regenerating_monstrosities_heals_only_one_model(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ability = {
            "name": "Regenerating Monstrosities",
            "description": (
                "At the start of each player’s Command phase, one model in this unit regains up to 3 lost wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Chaos Spawn", abilities=[ability])
        # Make both models damaged so we can verify only one gets healed.
        unit.models[0].wounds = 1
        unit.models[1].wounds = 1

        army = Army("Thousand Sons", "Det")
        army.faction_id = "TS"
        army.add_unit(unit)
        player = Player("TS", control=PlayerControl.REMOTE, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

        unit.deployed = True
        unit.reserve_status = "deployed"

        game._apply_command_phase_regain_wounds(player)

        healed = [m.wounds for m in unit.models]
        self.assertEqual(sorted(healed), [1, 2])

    def test_rites_of_coalescence_records_psyker_contains_gate(self):
        ability = {
            "name": "Rites of Coalescence",
            "description": (
                "While this unit contains one or more PSYKER models, each time an attack targets this unit, "
                "subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Scarab Occult Terminators", abilities=[ability])
        unit.models[0].keywords = ["PSYKER"]
        unit._parse_against_attack_characteristic_defensive_rules()
        entries = list(unit.special_rules.get("defensive_wound_mods", []) or [])
        self.assertTrue(entries)
        self.assertEqual(str(entries[0].get("requires_unit_contains_keyword", "")).upper(), "PSYKER")

    def test_rites_of_coalescence_requires_psyker_model(self):
        ability = {
            "name": "Rites of Coalescence",
            "description": (
                "While this unit contains one or more PSYKER models, each time an attack targets this unit, "
                "subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Scarab Occult Terminators", abilities=[ability])
        unit._parse_against_attack_characteristic_defensive_rules()
        profile = _make_profile()
        entries = list(
            profile._iter_defensive_entries(
                target_unit=unit,
                key="defensive_wound_mods",
                attacker_key=None,
                attack_type="ranged",
                phase_key="SHOOTING_PHASE",
            )
        )
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
