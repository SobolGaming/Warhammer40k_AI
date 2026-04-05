import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Necrons", abilities=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, faction_name="Necrons", abilities=None) -> Unit:
    return Unit(_MockDatasheet(name, faction_name=faction_name, abilities=abilities))


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army("Necrons", "Detachment")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "ENEMY"
    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE
    return game, necron_army, enemy_army, necron_player, enemy_player


class _MeleeWargear:
    def __init__(self, name: str):
        self.name = name
        norm = str(name or "").strip().lower().replace(" ", "-")
        self._id = f"wg-{norm or 'melee'}"

    def is_melee(self):
        return True

    def is_ranged(self):
        return False


class TestNecronsPlasmacyte(unittest.TestCase):
    def _resolve_yes(self, game: Game, player_id: str):
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CONFIRM_YES_NO)
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player_id)

    def test_plasmacyte_prompt_and_apply(self):
        ability = {
            "name": "Plasmacyte",
            "description": (
                "Once per battle for each Plasmacyte this unit has, when this unit is selected to fight, you can use this ability. "
                "If you do, until the end of the phase, melee weapons equipped by models in this unit have the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        unit = _make_unit("Skorpekh Destroyers", abilities=[ability])
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", abilities=[])
        unit.models[0].wargear = [_MeleeWargear("Hyperphase Reap-blade")]
        unit.special_rules = {"plasmacyte_token_total": 1}
        necron_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        game._on_fight_unit_selected_plasmacyte(unit=unit, selecting_player=necron_player)
        request = list(game.decision_queue.list() or [])[0]
        self.assertEqual(str((request.context or {}).get("ability", "")), "plasmacyte")

        self._resolve_yes(game, necron_player.id)
        self.assertEqual(int(unit.special_rules.get("plasmacyte_uses", 0) or 0), 1)
        self.assertTrue(bool(unit.special_rules.get("plasmacyte_active", False)))
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("plasmacyte")))

        bonuses = unit.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=unit.models[0],
            weapon_name="Hyperphase Reap-blade",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("devastating_wounds", False)))

    def test_plasmacyte_does_not_prompt_again_while_active_in_phase(self):
        ability = {
            "name": "Plasmacyte",
            "description": (
                "Once per battle for each Plasmacyte this unit has, when this unit is selected to fight, you can use this ability. "
                "If you do, until the end of the phase, melee weapons equipped by models in this unit have the [DEVASTATING WOUNDS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
        unit = _make_unit("Skorpekh Destroyers", abilities=[ability])
        enemy = _make_unit("Enemy Unit", faction_name="Enemy", abilities=[])
        unit.models[0].wargear = [_MeleeWargear("Hyperphase Reap-blade")]
        unit.special_rules = {"plasmacyte_token_total": 2}
        necron_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        game._on_fight_unit_selected_plasmacyte(unit=unit, selecting_player=necron_player)
        self._resolve_yes(game, necron_player.id)
        self.assertEqual(int(unit.special_rules.get("plasmacyte_uses", 0) or 0), 1)

        game._on_fight_unit_selected_plasmacyte(unit=unit, selecting_player=necron_player)
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)

        game._on_phase_end_cleanup(player=necron_player, phase=BattleRoundPhases.FIGHT_PHASE)
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_fight_unit_selected_plasmacyte(unit=unit, selecting_player=necron_player)
        self._resolve_yes(game, necron_player.id)
        self.assertEqual(int(unit.special_rules.get("plasmacyte_uses", 0) or 0), 2)
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("plasmacyte")))


if __name__ == "__main__":
    unittest.main()
