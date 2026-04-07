import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Angelic Inheritors")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_yes_option(request):
    for option in list(getattr(request, "options", []) or []):
        if bool(dict(getattr(option, "payload", {}) or {}).get("choice")):
            return option
    return None


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    return next(
        (model for model in list(getattr(unit, "models", []) or []) if str(get_entity_id(model) or "") == bearer_id),
        None,
    )


class TestSpaceMarinesAngelicInheritorsEnhancements(unittest.TestCase):
    def test_prescient_flash_grants_scouts_6_to_bearer_unit(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Captain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        sm_army.add_unit(unit)

        Enhancement(
            id="000009835002",
            name="Prescient Flash",
            faction_id="SM",
            detachment="Angelic Inheritors",
            points=20,
            description="",
        ).apply_to_unit(unit)

        has_scout, distance = unit.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(int(distance or 0), 6)

    def test_troubling_visions_activates_all_angelic_legacy_effects_for_bearer_unit_until_next_command_phase(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.turn = 1

        bearer_unit = _make_unit(
            "Captain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        other_character_unit = _make_unit(
            "Chaplain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(bearer_unit)
        sm_army.add_unit(other_character_unit)
        bearer_unit.deployed = True
        other_character_unit.deployed = True
        game.map.units = [bearer_unit, other_character_unit]
        game.rebuild_entity_registry()

        mgr = getattr(sm_army, "space_marines_detachments", None)
        self.assertIsNotNone(mgr)
        self.assertTrue(
            mgr.select_angelic_legacy_options(
                ["SANGUINARY_GRACE", "CARMINE_WRATH"],
                battle_round=1,
            )
        )

        Enhancement(
            id="000009835003",
            name="Troubling Visions",
            faction_id="SM",
            detachment="Angelic Inheritors",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        self.assertFalse(bool(mgr.legacy_of_the_angel_their_appointed_hour_applies(bearer_unit)))
        self.assertFalse(bool(mgr.legacy_of_the_angel_their_appointed_hour_applies(other_character_unit)))

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="troubling_visions",
        )
        self.assertIsNotNone(request)
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

        self.assertTrue(bool(mgr.legacy_of_the_angel_sanguinary_grace_applies(bearer_unit)))
        self.assertTrue(bool(mgr.legacy_of_the_angel_carmine_wrath_applies(bearer_unit)))
        self.assertTrue(bool(mgr.legacy_of_the_angel_their_appointed_hour_applies(bearer_unit)))
        self.assertFalse(bool(mgr.legacy_of_the_angel_their_appointed_hour_applies(other_character_unit)))
        self.assertTrue(bool(bearer_unit.has_used_unit_once_per_battle("troubling_visions")))

        game.turn = 2
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        self.assertFalse(bool(mgr.legacy_of_the_angel_their_appointed_hour_applies(bearer_unit)))
        second_request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="troubling_visions",
        )
        self.assertIsNone(second_request)

    def test_blazing_icon_prevents_fire_overwatch_only_while_bearer_is_alive(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Captain and Retinue",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        enemy_unit = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy_unit)
        bearer_unit.deployed = True
        enemy_unit.deployed = True
        game.map.units = [bearer_unit, enemy_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000009835004",
            name="Blazing Icon",
            faction_id="SM",
            detachment="Angelic Inheritors",
            points=20,
            description="",
        ).apply_to_unit(bearer_unit)

        self.assertTrue(bool(bearer_unit.is_overwatch_prevented_against(enemy_unit, game=game)))

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        self.assertFalse(bool(bearer_unit.is_overwatch_prevented_against(enemy_unit, game=game)))

    def test_ordained_sacrifice_returns_bearer_with_3_wounds_and_does_not_trigger_for_non_bearer(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit(
            "Captain and Guard",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=10,
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        unit.models[1].set_location(10.5, 10.0, 0.0, 0.0)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000009835005",
            name="Ordained Sacrifice",
            faction_id="SM",
            detachment="Angelic Inheritors",
            points=25,
            description="",
        ).apply_to_unit(unit)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(unit.models) if model is not bearer)

        non_bearer.take_damage(int(getattr(non_bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(game._phoenix_gem_pending))

        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertTrue(bool(game._phoenix_gem_pending))

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=sm_player, phase=game.phase)

        self.assertEqual(len(list(getattr(unit, "models", []) or [])), 1)
        returned = unit.models[0]
        self.assertTrue(bool(getattr(returned, "is_alive", False)))
        self.assertEqual(int(getattr(returned, "wounds", 0) or 0), 3)


if __name__ == "__main__":
    unittest.main()
