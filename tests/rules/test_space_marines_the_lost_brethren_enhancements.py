import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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
        self.id = str(name or "unit").lower().replace(" ", "-")
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
    sm_army = Army.with_detachment("Space Marines", "The Lost Brethren")
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


def _mark_deployed(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.2, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="The Lost Brethren",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _make_profile(*, melee: bool = True, bs_ws: str = "3+") -> WargearProfile:
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
            "BS_WS": str(bs_ws),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_choose_quarry_request(game: Game, *, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability):
            continue
        return req
    return None


class TestSpaceMarinesTheLostBrethrenEnhancements(unittest.TestCase):
    def test_lost_brethren_enhancement_descriptors_exist(self):
        expected = {
            "000009186002": (
                "Sanguinius' Grace",
                "fight_one_additional_time_if_bearer_engaged_with_three_plus_enemy_models",
            ),
            "000009186003": ("Blood Shard", "return_bearer_on_2plus_with_fixed_wounds"),
            "000009186004": (
                "To Slay the Warmaster",
                "select_character_unit_roll_six_d6_mortal_wounds_on_4plus_to_character_models",
            ),
            "000009186005": ("Vengeful Onslaught", "hit_roll_bonus_for_friendly_death_company_models"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_sanguinius_grace_additional_fight_candidate_honors_once_per_battle(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Death Company Captain",
            keywords=["CHARACTER", "INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=3,
            wounds=3,
        )
        sm_army.add_unit(bearer)
        enemy_army.add_unit(enemy)
        _mark_deployed(bearer, enemy)
        bearer.models[0].model_base.set_position(0.0, 0.0, 0.0)
        enemy.models[0].model_base.set_position(0.5, 0.0, 0.0)
        enemy.models[1].model_base.set_position(0.6, 0.3, 0.0)
        enemy.models[2].model_base.set_position(0.8, -0.2, 0.0)
        game.map.units = [bearer, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer,
            enhancement_id="000009186002",
            enhancement_name="Sanguinius' Grace",
        )
        candidates = game._rise_to_challenge_candidates(sm_player)
        self.assertIn(bearer, candidates)

        bearer.mark_unit_once_per_battle_used("sanguinius_grace", ability_name="Sanguinius' Grace")
        candidates_after = game._rise_to_challenge_candidates(sm_player)
        self.assertNotIn(bearer, candidates_after)

    def test_blood_shard_returns_bearer_on_two_plus_with_three_wounds(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Death Company Chaplain",
            keywords=["CHARACTER", "INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bearer)
        _mark_deployed(bearer)
        _set_unit_position(bearer, 12.0, 12.0)
        game.map.units = [bearer]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer,
            enhancement_id="000009186003",
            enhancement_name="Blood Shard",
        )
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        bearer.models[0].take_damage(6, game_map=game.map)
        self.assertEqual(len(getattr(bearer, "models", []) or []), 0)

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=sm_player, phase=game.phase)

        self.assertEqual(len(getattr(bearer, "models", []) or []), 1)
        self.assertEqual(int(getattr(bearer.models[0], "wounds", 0) or 0), 3)

    def test_to_slay_the_warmaster_queues_choose_quarry_and_applies_mortal_wounds(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Death Company Captain",
            keywords=["CHARACTER", "INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy_character = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=8,
        )
        sm_army.add_unit(bearer)
        enemy_army.add_unit(enemy_character)
        _mark_deployed(bearer, enemy_character)
        _set_unit_position(bearer, 0.0, 0.0)
        _set_unit_position(enemy_character, 0.0, 0.0)
        game.map.units = [bearer, enemy_character]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer,
            enhancement_id="000009186004",
            enhancement_name="To Slay the Warmaster",
        )
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_phase_start_to_slay_the_warmaster(player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)

        request = _find_choose_quarry_request(game, ability="to_slay_the_warmaster")
        self.assertIsNotNone(request)
        self.assertEqual(str(getattr(request, "player_id", "") or ""), str(sm_player.id))
        self.assertTrue(
            any(str((getattr(opt, "payload", {}) or {}).get("action", "") or "") == "skip" for opt in list(request.options or []))
        )

        target_option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_character))
        )
        initial_wounds = int(getattr(enemy_character.models[0], "wounds", 0) or 0)

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 4, 4, 1, 1, 1]):
            result = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(getattr(enemy_character.models[0], "wounds", 0) or 0), int(initial_wounds - 3))
        self.assertTrue(bool(bearer.has_used_unit_once_per_battle("to_slay_the_warmaster")))
        self.assertTrue(bool((getattr(bearer, "special_rules", {}) or {}).get("enhancement_to_slay_the_warmaster_used")))

        game._on_phase_start_to_slay_the_warmaster(player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
        self.assertIsNone(_find_choose_quarry_request(game, ability="to_slay_the_warmaster"))

    def test_vengeful_onslaught_grants_death_company_hit_bonus_until_end_of_next_turn(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Death Company Captain",
            keywords=["CHARACTER", "INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        death_company = _make_unit(
            "Death Company Marines",
            keywords=["INFANTRY", "DEATH COMPANY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=2,
        )
        non_death_company = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bearer)
        sm_army.add_unit(death_company)
        sm_army.add_unit(non_death_company)
        enemy_army.add_unit(enemy)
        _mark_deployed(bearer, death_company, non_death_company, enemy)
        _set_unit_position(bearer, 0.0, 0.0)
        _set_unit_position(death_company, 0.0, 1.0)
        _set_unit_position(non_death_company, 0.0, 2.0)
        _set_unit_position(enemy, 1.0, 0.0)
        game.map.units = [bearer, death_company, non_death_company, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer,
            enhancement_id="000009186005",
            enhancement_name="Vengeful Onslaught",
        )
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.turn = 1
        game.current_player_index = 0

        bearer_model = bearer.models[0]
        bearer_model.take_damage(6, game_map=game.map)
        game._on_model_destroyed_rules(
            attacker_model=enemy.models[0],
            attacker_unit=enemy,
            target_model=bearer_model,
            target_unit=bearer,
        )

        dc_sr = dict(getattr(death_company, "special_rules", {}) or {})
        self.assertTrue(bool(dc_sr.get("lost_brethren_vengeful_onslaught_active")))
        self.assertEqual(int(dc_sr.get("lost_brethren_vengeful_onslaught_hit_bonus", 0) or 0), 1)

        profile = _make_profile(melee=True, bs_ws="3+")
        dc_attack = profile._hit_target_with_tracking(
            enemy,
            death_company.models[0],
            {"target_unit": enemy},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(dc_attack.get("hit")))
        self.assertTrue(any("Vengeful Onslaught" in str(m) for m in list(dc_attack.get("modifiers", []) or [])))

        non_dc_attack = profile._hit_target_with_tracking(
            enemy,
            non_death_company.models[0],
            {"target_unit": enemy},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(non_dc_attack.get("hit")))

        game.turn = 2
        game.current_player_index = 0
        game._on_phase_end_lost_brethren_vengeful_onslaught(player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
        self.assertFalse(bool((getattr(death_company, "special_rules", {}) or {}).get("lost_brethren_vengeful_onslaught_active")))


if __name__ == "__main__":
    unittest.main()
