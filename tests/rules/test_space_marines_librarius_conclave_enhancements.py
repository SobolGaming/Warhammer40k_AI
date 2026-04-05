import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command, resolve_decision_value
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


def _build_game(detachment_type: str = "Librarius Conclave"):
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
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Librarius Conclave",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _choose_discipline(game: Game, sm_player: Player, sm_army: Army, *, key: str) -> None:
    game.current_player_index = 0
    sm_army.on_battle_round_start(game.turn)
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "librarius_psychic_disciplines"
    )
    option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == str(key).strip().upper()
    )
    _value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(apply_result, "ok", False))


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


def _make_ranged_profile(*, range_inches: str = "24", strength: str = "4", ap: str = "0"):
    parent = SimpleNamespace(name="Force Bolt", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": str(range_inches),
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesLibrariusConclaveEnhancements(unittest.TestCase):
    def test_librarius_enhancement_descriptors_exist(self):
        expected = {
            "000009785002": ("Prescience", "reactive_normal_move_up_to_d6_or_six_if_divination_active"),
            "000009785003": ("Celerity", "charge_after_advance_and_biomancy_charge_after_fall_back"),
            "000009785004": ("Obfuscation", "prevent_fire_overwatch_and_telepathy_ranged_targeting_cap"),
            "000009785005": (
                "Fusillade",
                "grant_anti_keywords_and_conditional_pyromancy_sustained_hits_and_telekinesis_range_bonus",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_prescience_reactive_move_uses_roll_and_is_once_per_turn(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        moving_enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(moving_enemy)
        source.deployed = True
        moving_enemy.deployed = True
        _set_unit_position(source, 8.0, 0.0)
        _set_unit_position(moving_enemy, 0.0, 0.0)
        game.map.units = [source, moving_enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009785002", enhancement_name="Prescience")
        game.current_player_index = 1
        game._on_unit_move_ended_detachment_rules(unit=moving_enemy, action="move")

        req = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            reactive_kind="librarius_prescience",
            unit_id=str(get_entity_id(source) or ""),
        )
        self.assertIsNotNone(req)
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            result = _resolve_yes(game, req, sm_player)
        self.assertTrue(bool(getattr(result, "ok", False)))

        move_request = _find_request(
            game,
            decision_type=DECISION_MOVE_UNIT,
            reactive_kind="librarius_prescience",
            unit_id=str(get_entity_id(source) or ""),
        )
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 4)
        self.assertTrue(sm_army.space_marines_detachments.librarius_prescience_used_this_turn(source, game=game))

        game._on_unit_move_ended_detachment_rules(unit=moving_enemy, action="advance")
        req_again = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            reactive_kind="librarius_prescience",
            unit_id=str(get_entity_id(source) or ""),
        )
        self.assertIsNone(req_again)

    def test_prescience_uses_fixed_six_when_divination_is_active(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        moving_enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(moving_enemy)
        source.deployed = True
        moving_enemy.deployed = True
        _set_unit_position(source, 8.0, 0.0)
        _set_unit_position(moving_enemy, 0.0, 0.0)
        game.map.units = [source, moving_enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009785002", enhancement_name="Prescience")
        _choose_discipline(game, sm_player, sm_army, key="DIVINATION")
        game.current_player_index = 1
        game._on_unit_move_ended_detachment_rules(unit=moving_enemy, action="move")

        req = _find_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            reactive_kind="librarius_prescience",
            unit_id=str(get_entity_id(source) or ""),
        )
        self.assertIsNotNone(req)
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2) as mocked_roll:
            result = _resolve_yes(game, req, sm_player)
        self.assertTrue(bool(getattr(result, "ok", False)))
        mocked_roll.assert_not_called()

        move_request = _find_request(
            game,
            decision_type=DECISION_MOVE_UNIT,
            reactive_kind="librarius_prescience",
            unit_id=str(get_entity_id(source) or ""),
        )
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 6)

    def test_celerity_enables_charge_after_advance_and_biomancy_fall_back(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(source)
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009785003", enhancement_name="Celerity")
        self.assertTrue(source.can_charge_after_advance())
        self.assertFalse(source.can_charge_after_fall_back())

        _choose_discipline(game, sm_player, sm_army, key="BIOMANCY")
        self.assertTrue(source.can_charge_after_fall_back())

    def test_obfuscation_blocks_overwatch_and_applies_telepathy_targeting_cap(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        target = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        shooter = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(target)
        enemy_army.add_unit(shooter)
        target.deployed = True
        shooter.deployed = True
        _set_unit_position(target, 10.0, 0.0)
        _set_unit_position(shooter, 0.0, 0.0)
        game.map.units = [target, shooter]
        game.rebuild_entity_registry()

        _apply_enhancement(target, enhancement_id="000009785004", enhancement_name="Obfuscation")
        self.assertTrue(target.is_overwatch_prevented_against(shooter, game=game))

        dist_before, sources_before = target.get_ranged_targeting_restriction()
        self.assertFalse(any("Obfuscation" in str(src or "") for src in list(sources_before or [])))
        self.assertTrue(dist_before is None or float(dist_before) <= 0.0)

        _choose_discipline(game, sm_player, sm_army, key="TELEPATHY")
        dist_after, sources_after = target.get_ranged_targeting_restriction()
        self.assertEqual(float(dist_after or 0.0), 18.0)
        self.assertTrue(any("Obfuscation" in str(src or "") for src in list(sources_after or [])))

    def test_fusillade_adds_anti_keywords_and_pyromancy_sustained_hits(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Monster",
            faction_name="Enemy",
            keywords=["MONSTER"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009785005", enhancement_name="Fusillade")
        profile = _make_ranged_profile()
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source.models[0],
            weapon_profile=profile,
            weapon_name="Force Bolt",
            target=target,
        )
        anti_specs = set(tuple(spec) for spec in list(bonuses.get("anti_specs", []) or []))
        self.assertIn(("MONSTER", 5), anti_specs)
        self.assertIn(("VEHICLE", 5), anti_specs)
        self.assertEqual(int(bonuses.get("sustained_hits_value", 0) or 0), 0)

        _choose_discipline(game, sm_player, sm_army, key="PYROMANCY")
        bonuses_pyromancy = source.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=source.models[0],
            weapon_profile=profile,
            weapon_name="Force Bolt",
            target=target,
        )
        self.assertEqual(int(bonuses_pyromancy.get("sustained_hits_value", 0) or 0), 1)

    def test_fusillade_adds_telekinesis_range_bonus(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(source)
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009785005", enhancement_name="Fusillade")
        profile = _make_ranged_profile(range_inches="24")
        base_range = int(profile._effective_range_max(source.models[0]) or 0)
        self.assertEqual(base_range, 24)

        _choose_discipline(game, sm_player, sm_army, key="TELEKINESIS")
        boosted_range = int(profile._effective_range_max(source.models[0]) or 0)
        self.assertEqual(boosted_range, 30)


if __name__ == "__main__":
    unittest.main()
