import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Imperial Knights", abilities=None, keywords=None, faction_keywords=None, model_count=1):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
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


def _make_unit(name, *, faction_name="Imperial Knights", abilities=None, keywords=None, faction_keywords=None, model_count=1):
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_ik = Army.with_detachment("Imperial Knights", "Valourstrike Lance")
    army_ik.faction_id = "IK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army_ik)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    return game, army_ik, army_enemy, p1, p2


def _ability_text():
    return (
        "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES ) "
        "hit by one or more of those attacks made with an Armiger autocannon. Until the start of your next turn, "
        "that enemy unit is suppressed. While a unit is suppressed, each time a model in that unit makes an attack, "
        "subtract 1 from the Hit roll."
    )


def _find_pending_suppression_request(game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET:
            continue
        return req
    return None


class TestPostShootSuppressionWeaponSpecific(unittest.TestCase):
    def test_parser_extracts_weapon_and_exclusion(self):
        ability = {
            "name": "Suppressive Barrage",
            "description": _ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit(
            "Armiger Helverin",
            abilities=[ability],
            keywords=["VEHICLE", "ARMIGER"],
            faction_keywords=["IMPERIAL KNIGHTS"],
        )

        specs = unit.unit_post_shoot_suppression_specs()
        self.assertEqual(len(specs), 1)
        self.assertTrue(bool(specs[0].get("exclude_monster_vehicle")))
        self.assertEqual(str(specs[0].get("weapon_key") or ""), "armiger autocannon")

    def test_weapon_specific_suppression_only_targets_units_hit_by_that_weapon(self):
        game, army_ik, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        ability = {
            "name": "Suppressive Barrage",
            "description": _ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit(
            "Armiger Helverin",
            abilities=[ability],
            keywords=["VEHICLE", "ARMIGER"],
            faction_keywords=["IMPERIAL KNIGHTS"],
        )
        target_hit = _make_unit(
            "Enemy Unit A",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        target_other_weapon = _make_unit(
            "Enemy Unit B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )

        army_ik.add_unit(attacker)
        enemy_army.add_unit(target_hit)
        enemy_army.add_unit(target_other_weapon)
        attacker.deployed = True
        target_hit.deployed = True
        target_other_weapon.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_hit.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        target_other_weapon.models[0].set_location(12.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target_hit, target_other_weapon]

        shooter = attacker.models[0]
        game._on_unit_shooting_resolved_post_shoot_suppression(
            attacker_unit=attacker,
            hits_by_target={target_hit: 1, target_other_weapon: 1},
            hit_models_by_target={target_hit: {shooter}, target_other_weapon: {shooter}},
            hit_models_by_target_weapon={
                target_hit: {"armiger autocannon": {shooter}},
                target_other_weapon: {"heavy stubber": {shooter}},
            },
        )

        request = _find_pending_suppression_request(game)
        self.assertIsNotNone(request)
        self.assertEqual(len(list(request.options or [])), 1)
        selected_option = request.options[0]
        self.assertEqual(
            str((selected_option.payload or {}).get("unit_id") or ""),
            str(get_entity_id(target_hit) or ""),
        )

        resolve_decision_command(game, request, selected_option.option_id, player_id=player.id)
        self.assertTrue(bool(target_hit.special_rules.get("post_shoot_suppressed_active")))
        self.assertFalse(bool(target_other_weapon.special_rules.get("post_shoot_suppressed_active")))


if __name__ == "__main__":
    unittest.main()
