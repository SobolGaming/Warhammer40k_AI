import unittest
from types import MethodType, SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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
        wounds: int = 4,
        toughness: int = 4,
        save: int = 3,
        move: int = 6,
    ):
        self.id = name.lower().replace(" ", "-")
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
                "Sv": str(int(save)),
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
    wounds: int = 4,
    toughness: int = 4,
    save: int = 3,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            save=save,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "The Angelic Host")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="The Angelic Host",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _make_profile(*, melee: bool, ap: str):
    parent = SimpleNamespace(
        name="Weapon",
        is_melee=(lambda: bool(melee)),
        is_ranged=(lambda: not bool(melee)),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_request(game: Game, *, decision_type: str, reactive_kind: str, unit_id: str = ""):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("reactive_move_kind", "") or "") != str(reactive_kind):
            continue
        if unit_id and str(ctx.get("reactive_move_unit_id", "") or "") != str(unit_id):
            continue
        return req
    return None


def _resolve_yes(game: Game, request, player: Player):
    yes_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if bool((getattr(opt, "payload", {}) or {}).get("choice", False))
    )
    return resolve_decision_command(game, request, yes_option.option_id, player_id=player.id)


class TestSpaceMarinesTheAngelicHostEnhancements(unittest.TestCase):
    def test_angelic_host_enhancement_descriptors_exist(self):
        expected = {
            "000009190002": ("Artisan of War", "improve_bearer_weapon_ap_and_set_bearer_save"),
            "000009190003": ("Visage of Death", "force_battleshock_for_enemy_units_within_bearer_engagement_range"),
            "000009190004": ("Archangel's Shard", "grant_bearer_melee_anti_chaos_and_lance"),
            "000009190005": ("Gleaming Pinions", "once_per_turn_reactive_normal_move_if_not_engaged"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_artisan_of_war_sets_save_to_two_and_improves_bearer_melee_and_ranged_ap(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            save=3,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            save=3,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(target, 8.0, 0.0)
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009190002", enhancement_name="Artisan of War")
        sr = getattr(source, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("enhancement_artisan_of_war")))
        self.assertEqual(int(sr.get("enhancement_artisan_of_war_save", 0) or 0), 2)

        attacker = next(m for m in list(getattr(source, "models", []) or []) if bool(getattr(m, "is_alive", False)))
        save_value, save_source = source.get_model_save_characteristic_override(attacker)
        self.assertEqual(int(save_value or 0), 2)
        self.assertIn("Artisan of War", str(save_source or ""))

        melee = _make_profile(melee=True, ap="-1")
        ranged = _make_profile(melee=False, ap="0")
        self.assertEqual(int(melee.get_effective_ap(attacker, target) or 0), -2)
        self.assertEqual(int(ranged.get_effective_ap(attacker, target) or 0), -1)

    def test_archangels_shard_grants_bearer_melee_lance_and_anti_chaos(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        chaos_target = _make_unit(
            "Chaos Unit",
            faction_name="Enemy",
            keywords=["INFANTRY", "CHAOS"],
            faction_keywords=["ENEMY", "CHAOS"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(chaos_target)
        source.deployed = True
        chaos_target.deployed = True
        game.map.units = [source, chaos_target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009190004", enhancement_name="Archangel's Shard")
        bearer = next(m for m in list(getattr(source, "models", []) or []) if bool(getattr(m, "is_alive", False)))
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=bearer,
            weapon_profile=_make_profile(melee=True, ap="-1"),
            target=chaos_target,
        )
        self.assertTrue(bool(bonuses.get("lance")))
        anti_specs = list(bonuses.get("anti_specs", []) or [])
        self.assertIn(("CHAOS", 5), anti_specs)

    def test_visage_of_death_forces_enemy_non_monster_non_vehicle_battleshock_in_opponent_command_phase(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            model_count=1,
            toughness=10,
            wounds=10,
            save=2,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_vehicle)
        source.deployed = True
        enemy_infantry.deployed = True
        enemy_vehicle.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_infantry, 0.0, 0.0)
        _set_unit_position(enemy_vehicle, 0.0, 0.0)
        game.map.units = [source, enemy_infantry, enemy_vehicle]
        game.rebuild_entity_registry()

        infantry_calls: list[int] = []
        vehicle_calls: list[int] = []

        def _record_infantry(self, turn=1):
            infantry_calls.append(int(turn))

        def _record_vehicle(self, turn=1):
            vehicle_calls.append(int(turn))

        enemy_infantry.take_battle_shock_test = MethodType(_record_infantry, enemy_infantry)
        enemy_vehicle.take_battle_shock_test = MethodType(_record_vehicle, enemy_vehicle)

        _apply_enhancement(source, enhancement_id="000009190003", enhancement_name="Visage of Death")

        game.current_player_index = 1
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.start_command_phase()

        self.assertEqual(infantry_calls, [int(game.turn)])
        self.assertEqual(vehicle_calls, [])
        self.assertEqual(game.get_current_player(), enemy_player)

    def test_gleaming_pinions_reactive_move_queues_and_marks_once_per_turn_on_successful_move(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Jump Captain",
            keywords=["CHARACTER", "INFANTRY", "JUMP PACK"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        moving_enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(moving_enemy)
        source.deployed = True
        moving_enemy.deployed = True
        _set_unit_position(source, 8.0, 0.0)
        _set_unit_position(moving_enemy, 0.0, 0.0)
        game.map.units = [source, moving_enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009190005", enhancement_name="Gleaming Pinions")
        game.current_player_index = 1
        game._on_unit_move_ended_detachment_rules(unit=moving_enemy, action="move")

        source_id = str(get_entity_id(source) or "")
        confirm_request = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            reactive_kind="gleaming_pinions",
            unit_id=source_id,
        )
        self.assertIsNotNone(confirm_request)
        confirm_result = _resolve_yes(game, confirm_request, sm_player)
        self.assertTrue(bool(getattr(confirm_result, "ok", False)))

        move_request = _find_request(
            game,
            decision_type=DECISION_MOVE_UNIT,
            reactive_kind="gleaming_pinions",
            unit_id=source_id,
        )
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("movement_type", "") or ""), "gleaming_pinions")
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 6)

        source_model = next(m for m in list(getattr(source, "models", []) or []) if bool(getattr(m, "is_alive", False)))
        x, y, z, facing = source_model.get_location()
        move_option = next(
            opt
            for opt in list(getattr(move_request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("action", "") or "") == "confirm"
        )
        move_result = resolve_decision_command(
            game,
            move_request,
            move_option.option_id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": str(get_entity_id(source_model) or ""),
                        "position": [float(x), float(y), float(z)],
                        "facing": float(facing),
                    }
                ]
            },
            player_id=sm_player.id,
        )
        self.assertTrue(bool(getattr(move_result, "ok", False)))
        self.assertTrue(sm_army.space_marines_detachments.the_angelic_host_gleaming_pinions_used_this_turn(source, game=game))

        game._on_unit_move_ended_detachment_rules(unit=moving_enemy, action="advance")
        repeat_request = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            reactive_kind="gleaming_pinions",
            unit_id=source_id,
        )
        self.assertIsNone(repeat_request)


if __name__ == "__main__":
    unittest.main()
