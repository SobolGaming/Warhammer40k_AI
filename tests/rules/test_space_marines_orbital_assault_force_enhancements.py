import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
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
        objective_control: int = 1,
        toughness: int = 4,
        wounds: int = 4,
        move: int = 6,
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
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
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
    objective_control: int = 1,
    toughness: int = 4,
    wounds: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            toughness=toughness,
            wounds=wounds,
            move=move,
        )
    )


def _build_game(detachment_type: str = "Orbital Assault Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Orbital Assault Force",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _find_optional_request(game: Game, *, unit: Unit, ability_key: str):
    uid = str(get_entity_id(unit) or "")
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "opponent_turn_strategic_reserves":
            continue
        if str(ctx.get("ability_key", "") or "") != str(ability_key):
            continue
        if str(ctx.get("unit_id", "") or "") != uid:
            continue
        return req
    return None


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


class TestSpaceMarinesOrbitalAssaultForceEnhancements(unittest.TestCase):
    def test_orbital_assault_enhancement_descriptors_exist(self):
        expected = {
            "000010680002": ("Laurels of Thunder", "charge_reroll_on_setup_turn"),
            "000010680003": ("Veteran of the Vanguard", "bearer_unit_gain_scouts"),
            "000010680004": ("Orbital Uplink Reliquary", "redeploy_units"),
            "000010680005": (
                "Dedicated Gunship",
                "once_per_battle_end_of_opponent_fight_phase_enter_strategic_reserves",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_laurels_of_thunder_rerolls_charge_on_setup_turn_only_while_bearer_alive(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Jump Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=5,
        )
        sm_army.add_unit(source)
        source.deployed = True
        source.reserve_status = "deployed"
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010680002", enhancement_name="Laurels of Thunder")
        self.assertFalse(bool(source.can_reroll_charge_roll(game=game)))

        source.round_state.reinforced_this_round = True
        self.assertTrue(bool(source.can_reroll_charge_roll(game=game)))

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(source.can_reroll_charge_roll(game=game)))

    def test_veteran_of_the_vanguard_grants_scouts_6(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Vanguard Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=5,
        )
        sm_army.add_unit(source)
        source.deployed = True
        source.reserve_status = "deployed"
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010680003", enhancement_name="Veteran of the Vanguard")
        has_scout, distance = source.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(float(distance or 0.0), 6.0)

    def test_orbital_uplink_reliquary_redeploy_filters_to_adeptus_astartes_and_can_place_in_reserves(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Orbital Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        astartes_target = _make_unit(
            "Astartes Target",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        allied_target = _make_unit(
            "Allied Target",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        for unit in (source, astartes_target, allied_target):
            sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        for unit in (source, astartes_target, allied_target, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [source, astartes_target, allied_target, enemy]
        game.rebuild_entity_registry()
        game.attacker_index = 0
        game.defender_index = 1

        _apply_enhancement(source, enhancement_id="000010680004", enhancement_name="Orbital Uplink Reliquary")
        game.execute_redeploy_units_phase()

        request = _find_redeploy_request(game, player_id=sm_player.id, ability_name="Orbital Uplink Reliquary")
        self.assertIsNotNone(request)

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertIn(str(get_entity_id(astartes_target) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(allied_target) or ""), target_ids)

        reserve_option_id = next(
            opt.option_id
            for opt in list(getattr(request, "options", []) or [])
            if (
                str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
                == str(get_entity_id(astartes_target) or "")
                and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
                == "strategic_reserves"
            )
        )
        result = resolve_decision_command(game, request, reserve_option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(astartes_target.is_in_strategic_reserves())
        self.assertNotIn(astartes_target, list(getattr(game.map, "units", []) or []))

    def test_dedicated_gunship_queues_at_end_of_opponent_fight_phase_and_moves_to_reserves(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Terminator Captain",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        source.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010680005", enhancement_name="Dedicated Gunship")
        game.current_player_index = 1
        game._on_phase_end_opponent_fight_phase_strategic_reserves(
            player=enemy_player,
            phase=BattleRoundPhases.FIGHT_PHASE,
        )

        request = _find_optional_request(game, unit=source, ability_key="dedicated_gunship")
        self.assertIsNotNone(request)
        yes_option = next(
            opt.option_id
            for opt in list(getattr(request, "options", []) or [])
            if bool((getattr(opt, "payload", {}) or {}).get("choice", False))
        )
        result = resolve_decision_command(game, request, yes_option, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(source.is_in_strategic_reserves())
        self.assertNotIn(source, list(getattr(game.map, "units", []) or []))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("dedicated_gunship")))

    def test_dedicated_gunship_does_not_queue_at_end_of_opponent_turn(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Terminator Captain",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        source.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010680005", enhancement_name="Dedicated Gunship")
        game.current_player_index = 1
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

        request = _find_optional_request(game, unit=source, ability_key="dedicated_gunship")
        self.assertIsNone(request)

    def test_dedicated_gunship_does_not_queue_when_bearer_is_destroyed(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Terminator Command",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        source.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010680005", enhancement_name="Dedicated Gunship")
        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        game.current_player_index = 1
        game._on_phase_end_opponent_fight_phase_strategic_reserves(
            player=enemy_player,
            phase=BattleRoundPhases.FIGHT_PHASE,
        )
        request = _find_optional_request(game, unit=source, ability_key="dedicated_gunship")
        self.assertIsNone(request)


if __name__ == "__main__":
    unittest.main()
