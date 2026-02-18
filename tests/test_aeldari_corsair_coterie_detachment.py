import json
import types
import unittest
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _DummyUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.special_rules = {}
        self.enhancement = None
        self._parent_army = None

    @property
    def is_character(self) -> bool:
        return any(str(k).strip().upper() == "CHARACTER" for k in (self.keywords or []))

    @property
    def is_epic_hero(self) -> bool:
        return any(str(k).strip().upper() == "EPIC HERO" for k in (self.keywords or []))

    def get_effective_keywords(self):
        return list(self.keywords or [])

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords or [])

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        wounds: int = 3,
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
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


def _load_enhancement(name: str) -> Enhancement:
    with open("wahapedia_data/Enhancements.json", "r", encoding="utf-8") as handle:
        rows = json.load(handle)
    row = next(item for item in rows if str(item.get("name", "")) == name)
    return Enhancement.from_waha_dict(row)


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
    model_count: int = 1,
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
        model_count=model_count,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_corsair_game():
    aeldari_army = Army("Aeldari", "Corsair Coterie")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    aeldari_player = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    enemy_player = Player("Enemy", control=PlayerControl.LOCAL, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[aeldari_player, enemy_player])
    return game, aeldari_army, enemy_army, aeldari_player, enemy_player


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = types.SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper().replace("\u2019", "'")
    for reaction in list(stratagems.get_pending_reactions() or []):
        actual = str(reaction.get("stratagem", "") or "").strip().upper().replace("\u2019", "'")
        if wanted in actual:
            return reaction
    return None


def _make_test_ranged_profile(
    *,
    name: str = "Long rifle",
    attacks: str = "1",
    range_value: str = "24",
    ap: str = "-1",
    description: str = "",
):
    clean_range = str(range_value or "").replace('"', "").strip()
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": clean_range,
            "A": attacks,
            "BS_WS": "3+",
            "S": "4",
            "AP": ap,
            "D": "1",
            "description": description,
        }
    )
    return next(iter(weapon.profiles.values()))


class TestAeldariCorsairCoterieEnhancements(unittest.TestCase):
    def test_veterans_of_the_void_allows_non_character_anhrathe_enhancement(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"
        unit = _DummyUnit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enhancement = _load_enhancement("Infamy (Aura)")
        army.add_unit(unit)
        army.add_enhancement(enhancement, unit)
        self.assertIs(unit.enhancement, enhancement)

    def test_non_veterans_detachment_keeps_character_requirement(self):
        army = Army("Aeldari", "Warhost")
        army.faction_id = "AE"
        unit = _DummyUnit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enhancement = _load_enhancement("Infamy (Aura)")
        army.add_unit(unit)
        with self.assertRaises(ArmyValidationError):
            army.add_enhancement(enhancement, unit)

    def test_veterans_of_the_void_replaces_three_enhancement_cap(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"

        units = [
            _DummyUnit("Corsair Unit 1", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit("Corsair Unit 2", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit("Corsair Unit 3", keywords=["INFANTRY"], faction_keywords=["AELDARI", "ANHRATHE"]),
            _DummyUnit(
                "Corsair Prince",
                keywords=["INFANTRY", "CHARACTER"],
                faction_keywords=["AELDARI", "ANHRATHE"],
            ),
        ]
        for unit in units:
            army.add_unit(unit)

        enhancements = [
            _load_enhancement("Infamy (Aura)"),
            _load_enhancement("Webway Pathstone"),
            _load_enhancement("Voidstone"),
            _load_enhancement("Archraider"),
        ]
        for unit, enhancement in zip(units, enhancements):
            army.add_enhancement(enhancement, unit)

        try:
            army.validate_enhancements()
        except ArmyValidationError as exc:
            self.fail(f"Veterans of the Void should allow 4 Corsair Enhancements here: {exc}")


class TestAeldariCorsairCoterieEnhancementEffects(unittest.TestCase):
    def test_infamy_aura_reduces_enemy_objective_control_to_minimum_one(self):
        game, aeldari_army, enemy_army, _aeldari_player, _enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Prince",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy_oc_one = _make_unit(
            "Enemy OC1",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        enemy_oc_two = _make_unit(
            "Enemy OC2",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=2,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy_oc_one, x=1.0, y=0.0)
        _set_model_location(enemy_oc_two, x=1.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy_oc_one)
        enemy_army.add_unit(enemy_oc_two)
        aeldari_army.add_enhancement(_load_enhancement("Infamy (Aura)"), source)

        game.map.units = [source, enemy_oc_one, enemy_oc_two]

        self.assertEqual(int(enemy_oc_one.models[0].objective_control), 1)
        self.assertEqual(int(enemy_oc_two.models[0].objective_control), 1)

    def test_voidstone_grants_5_plus_invulnerable_save_to_bearer_unit(self):
        army = Army("Aeldari", "Corsair Coterie")
        army.faction_id = "AE"
        unit = _make_unit(
            "Corsair Voidreavers",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        army.add_unit(unit)
        army.add_enhancement(_load_enhancement("Voidstone"), unit)

        invuln, source = unit.get_model_invulnerable_save_override(unit.models[0])
        self.assertEqual(int(invuln or 0), 5)
        self.assertIn("Voidstone", str(source))

    def test_webway_pathstone_grants_deep_strike_and_end_of_opponent_turn_reposition(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy, x=10.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        aeldari_army.add_enhancement(_load_enhancement("Webway Pathstone"), source)

        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        self.assertTrue(source.has_deep_strike())

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str((request.context or {}).get("ability_key", "")), "webway_pathstone")

        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=aeldari_player.id)

        self.assertTrue(source.is_in_strategic_reserves())
        self.assertTrue(source.has_used_unit_once_per_battle("webway_pathstone"))

    def test_archraider_applies_targeted_stratagem_cp_increase_within_12_of_bearer_model(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = _build_corsair_game()
        source = _make_unit(
            "Corsair Prince",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(source, x=0.0, y=0.0)
        _set_model_location(enemy, x=10.0, y=0.0)

        aeldari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        aeldari_army.add_enhancement(_load_enhancement("Archraider"), source)

        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        specs = list(source.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("source_model_id", "")), str(source.models[0].id))

        preview_in = aeldari_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertTrue(bool(preview_in.get("auto")))

        applied_in = aeldari_player.apply_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertEqual(int(applied_in.get("increase", 0) or 0), 1)

        _set_model_location(enemy, x=20.0, y=0.0)
        preview_out = aeldari_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertFalse(bool(preview_out.get("auto")))
        self.assertFalse(bool(preview_out.get("optional")))


class TestAeldariCorsairCoterieDetachmentRules(unittest.TestCase):
    def _build_game(self):
        return _build_corsair_game()

    def test_relentless_raiders_applies_mortal_wounds_on_enemy_move(self):
        game, aeldari_army, enemy_army, _aeldari_player, _enemy_player = self._build_game()
        anhrathe = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        _set_model_location(anhrathe, x=0.0, y=0.0)
        _set_model_location(enemy, x=0.0, y=0.0)

        aeldari_army.add_unit(anhrathe)
        enemy_army.add_unit(enemy)
        game.map.units = [anhrathe, enemy]

        point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=point,
        )
        game.map.objectives = [objective]

        applied = []

        def _apply_mortals(self, target_unit, amount, game_map=None):
            applied.append(int(amount))
            return int(amount)

        enemy._apply_mortal_wounds_to_unit = types.MethodType(_apply_mortals, enemy)

        with patch("warhammer40k_ai.rules.aeldari_detachments.get_roll", side_effect=[2, 3]):
            game.event_system.publish("unit_move_ended", unit=enemy, action="move")

        self.assertEqual(applied, [3])

    def test_void_thieves_applies_sticky_control_at_phase_end(self):
        game, aeldari_army, _enemy_army, aeldari_player, enemy_player = self._build_game()
        anhrathe = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            objective_control=2,
        )
        _set_model_location(anhrathe, x=0.0, y=0.0)
        aeldari_army.add_unit(anhrathe)
        game.map.units = [anhrathe]

        point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=point,
        )
        game.map.objectives = [objective]

        game.event_system.publish(
            "phase_end",
            player=enemy_player,
            phase=BattleRoundPhases.SHOOTING_PHASE,
        )

        self.assertIs(point.sticky_controller, aeldari_player)
        self.assertEqual(str(point.sticky_source), "void_thieves")


class TestAeldariCorsairCoterieStratagems(unittest.TestCase):
    def _build_game(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = _build_corsair_game()
        aeldari_army.configure_rule_managers(force=True)
        aeldari_player.command_points = 10
        enemy_player.command_points = 10
        aeldari_player.stratagems.refresh_available()
        return game, aeldari_army, enemy_army, aeldari_player, enemy_player

    def test_cloak_and_shadow_queues_and_applies_stealth_and_18_in_targeting_cap(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        defender = _make_unit(
            "Corsair Defenders",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(defender, x=0.0, y=0.0)
        _set_model_location(attacker, x=24.0, y=0.0)

        aeldari_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        game.map.units = [defender, attacker]

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives = [objective]

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

        pending = _pending_by_name(aeldari_player.stratagems, "CLOAK AND SHADOW")
        self.assertIsNotNone(pending)

        ok = aeldari_player.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=defender,
            attacking_unit=attacker,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)
        self.assertTrue(defender.has_stealth())

        limit, sources = defender.get_ranged_targeting_restriction(game_map=game.map)
        self.assertEqual(float(limit or 0.0), 18.0)
        self.assertTrue(any("CLOAK" in str(source).upper() for source in list(sources or [])))

        game.event_system.publish("phase_end", player=enemy_player, phase=types.SimpleNamespace(name="SHOOTING_PHASE"))

        self.assertFalse(bool(defender.special_rules.get("aeldari_cloak_and_shadow_active")))
        self.assertFalse(defender.has_stealth())

    def test_cloak_and_shadow_not_offered_without_controlled_objective_targeting_window(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        defender = _make_unit(
            "Corsair Defenders",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(defender, x=0.0, y=0.0)
        _set_model_location(attacker, x=12.0, y=0.0)
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        game.map.units = [defender, attacker]
        game.map.objectives = []

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

        pending = _pending_by_name(aeldari_player.stratagems, "CLOAK AND SHADOW")
        self.assertIsNone(pending)

    def test_vengeful_sorrow_queues_after_casualties_and_rolls_d6_plus_1(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        defender = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
            model_count=3,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(defender, x=0.0, y=0.0)
        _set_model_location(attacker, x=12.0, y=0.0)
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(attacker)
        game.map.units = [defender, attacker]

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
        defender.models[0].take_damage(
            amount=99,
            is_mortal=True,
            game_map=game.map,
            wounds_cannot_be_ignored=True,
        )
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={defender: 1})

        pending = _pending_by_name(aeldari_player.stratagems, "VENGEFUL SORROW")
        self.assertIsNotNone(pending)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            ok = aeldari_player.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=defender,
                attacking_unit=attacker,
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)

        move_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "")).strip() == "vengeful_sorrow"
        ]
        self.assertEqual(len(move_requests), 1)
        context = dict(getattr(move_requests[0], "context", {}) or {})
        self.assertEqual(int(context.get("max_distance", 0) or 0), 5)
        self.assertEqual(str(context.get("movement_type", "") or ""), "blood_surge")

    def test_outcast_ambush_applies_ranged_ignores_cover_rapid_fire_and_ap_bonus_until_phase_end(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        rangers = _make_unit(
            "Rangers",
            keywords=["INFANTRY", "RANGERS"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(rangers, x=0.0, y=0.0)
        _set_model_location(enemy, x=6.0, y=0.0)
        aeldari_army.add_unit(rangers)
        enemy_army.add_unit(enemy)
        game.map.units = [rangers, enemy]

        profile = _make_test_ranged_profile(name="Long rifle", attacks="1", range_value="24", ap="-1")
        attacker_model = rangers.models[0]
        baseline_count = profile.preview_attack_count(enemy, attacker_model, publish_roll_event=False)
        self.assertEqual(int(baseline_count.num_attacks), 1)
        self.assertEqual(int(profile.get_effective_ap(attacker_model, enemy)), -1)

        _set_phase(game, aeldari_player, "SHOOTING_PHASE", 0)
        ok = aeldari_player.stratagems.use("OUTCAST AMBUSH", unit=rangers)
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)

        bonuses = rangers.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=attacker_model,
            weapon_profile=profile,
            weapon_name="Long rifle",
            target=enemy,
        )
        self.assertTrue(bool(bonuses.get("ignores_cover")))

        boosted_count = profile.preview_attack_count(enemy, attacker_model, publish_roll_event=False)
        self.assertEqual(int(boosted_count.num_attacks), 2)
        self.assertEqual(int(profile.get_effective_ap(attacker_model, enemy)), -2)

        game.event_system.publish("phase_end", player=aeldari_player, phase=types.SimpleNamespace(name="SHOOTING_PHASE"))
        post_count = profile.preview_attack_count(enemy, attacker_model, publish_roll_event=False)
        self.assertEqual(int(post_count.num_attacks), 1)
        self.assertEqual(int(profile.get_effective_ap(attacker_model, enemy)), -1)
        post_bonuses = rangers.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=attacker_model,
            weapon_profile=profile,
            weapon_name="Long rifle",
            target=enemy,
        )
        self.assertFalse(bool(post_bonuses.get("ignores_cover")))

    def test_outcast_ambush_rejects_invalid_target(self):
        game, aeldari_army, _enemy_army, aeldari_player, _enemy_player = self._build_game()
        voidscarred = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        aeldari_army.add_unit(voidscarred)
        game.map.units = [voidscarred]

        _set_phase(game, aeldari_player, "SHOOTING_PHASE", 0)
        ok = aeldari_player.stratagems.use("OUTCAST AMBUSH", unit=voidscarred)
        self.assertFalse(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 10)

    def test_into_the_breach_queues_after_anhrathe_shooting_destroys_enemy(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        attacker = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(attacker, x=0.0, y=0.0)
        _set_model_location(enemy, x=8.0, y=0.0)
        aeldari_army.add_unit(attacker)
        enemy_army.add_unit(enemy)
        game.map.units = [attacker, enemy]

        _set_phase(game, aeldari_player, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=attacker)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={enemy: 1})

        pending = _pending_by_name(aeldari_player.stratagems, "INTO THE BREACH")
        self.assertIsNotNone(pending)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            ok = aeldari_player.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=attacker,
                attacking_unit=attacker,
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)

        move_requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "")).strip()
            == "into_the_breach"
        ]
        self.assertEqual(len(move_requests), 1)
        context = dict(getattr(move_requests[0], "context", {}) or {})
        self.assertEqual(int(context.get("max_distance", 0) or 0), 4)
        self.assertEqual(str(context.get("movement_type", "") or ""), "reactive")

    def test_into_the_breach_not_offered_for_non_anhrathe_shooter(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        attacker = _make_unit(
            "Guardian Defenders",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ASURYANI"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(attacker, x=0.0, y=0.0)
        _set_model_location(enemy, x=8.0, y=0.0)
        aeldari_army.add_unit(attacker)
        enemy_army.add_unit(enemy)
        game.map.units = [attacker, enemy]

        _set_phase(game, aeldari_player, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=attacker)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={enemy: 1})

        pending = _pending_by_name(aeldari_player.stratagems, "INTO THE BREACH")
        self.assertIsNone(pending)

    def test_pirates_due_grants_melee_wound_rerolls_and_anhrathe_objective_full_rerolls(self):
        game, aeldari_army, enemy_army, aeldari_player, enemy_player = self._build_game()
        corsairs = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(corsairs, x=0.0, y=0.0)
        _set_model_location(enemy, x=0.0, y=0.0)
        aeldari_army.add_unit(corsairs)
        enemy_army.add_unit(enemy)
        game.map.units = [corsairs, enemy]

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives = [objective]

        _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
        pirates_name = next(
            str(s.name)
            for s in list(aeldari_player.stratagems.list_available() or [])
            if "PIRATES" in str(getattr(s, "name", "") or "").upper()
        )
        ok = aeldari_player.stratagems.use(pirates_name, unit=corsairs)
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)

        mods = corsairs.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(mods.get("reroll_wound_ones")))
        self.assertTrue(bool(mods.get("reroll_wound_full")))

    def test_lethal_ruse_queues_after_fall_back_and_applies_anhrathe_mortal_wounds(self):
        game, aeldari_army, enemy_army, aeldari_player, _enemy_player = self._build_game()
        corsairs = _make_unit(
            "Corsair Voidscarred",
            keywords=["INFANTRY"],
            faction_keywords=["AELDARI", "ANHRATHE"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        _set_model_location(corsairs, x=0.0, y=0.0)
        _set_model_location(enemy, x=0.0, y=0.0)
        aeldari_army.add_unit(corsairs)
        enemy_army.add_unit(enemy)
        game.map.units = [corsairs, enemy]

        _set_phase(game, aeldari_player, "MOVEMENT_PHASE", 0)
        corsairs.round_state.fell_back_this_round = True
        game.event_system.publish("unit_move_ended", unit=corsairs, action="fall_back")

        pending = _pending_by_name(aeldari_player.stratagems, "LETHAL RUSE")
        self.assertIsNotNone(pending)

        applied = []

        def _apply_mortals(self, target_unit, amount, game_map=None):
            applied.append(int(amount))
            return int(amount)

        enemy._apply_mortal_wounds_to_unit = types.MethodType(_apply_mortals, enemy)
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 1, 5, 3, 6, 2]):
            ok = aeldari_player.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=corsairs,
                enemy_unit=enemy,
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(int(aeldari_player.command_points or 0), 9)
        self.assertEqual(applied, [3])
        self.assertTrue(corsairs.can_charge_after_fall_back())

        game.event_system.publish("phase_end", player=aeldari_player, phase=types.SimpleNamespace(name="FIGHT_PHASE"))
        self.assertFalse(corsairs.can_charge_after_fall_back())

    def test_corsair_coterie_stratagem_descriptors_registered(self):
        pirates = get_stratagem_tool_descriptor(stratagem_id="000010705002")
        self.assertIsNotNone(pirates)
        self.assertEqual(str(pirates.name), "Pirates' Due")
        self.assertEqual(str(pirates.effect), "wound_reroll_ones_and_conditional_full_reroll")
        self.assertTrue(bool(pirates.effect_params.get("reroll_wound_ones", False)))

        lethal = get_stratagem_tool_descriptor(stratagem_id="000010705003")
        self.assertIsNotNone(lethal)
        self.assertEqual(str(lethal.name), "Lethal Ruse")
        self.assertEqual(str(lethal.effect), "charge_after_fall_back_and_conditional_mortal_wounds")
        self.assertEqual(str(lethal.effect_params.get("anhrathe_mortal_roll", "") or ""), "6D6")

        outcast = get_stratagem_tool_descriptor(stratagem_id="000010705004")
        self.assertIsNotNone(outcast)
        self.assertEqual(str(outcast.name), "Outcast Ambush")
        self.assertEqual(str(outcast.effect), "grant_ranged_ignores_cover_rapid_fire_and_ap_bonus")
        self.assertEqual(int(outcast.effect_params.get("ap_bonus", 0) or 0), 1)

        breach = get_stratagem_tool_descriptor(stratagem_id="000010705005")
        self.assertIsNotNone(breach)
        self.assertEqual(str(breach.name), "Into the Breach")
        self.assertEqual(str(breach.effect), "reactive_normal_move")
        self.assertEqual(str(breach.effect_params.get("distance_roll", "") or ""), "D6+1")

        cloak = get_stratagem_tool_descriptor(stratagem_id="000010705006")
        self.assertIsNotNone(cloak)
        self.assertEqual(str(cloak.name), "Cloak and Shadow")
        self.assertEqual(str(cloak.effect), "grant_stealth_and_ranged_targeting_distance_cap")
        self.assertEqual(int(cloak.effect_params.get("max_targeting_distance", 0) or 0), 18)

        vengeful = get_stratagem_tool_descriptor(stratagem_id="000010705007")
        self.assertIsNotNone(vengeful)
        self.assertEqual(str(vengeful.name), "Vengeful Sorrow")
        self.assertEqual(str(vengeful.effect), "reactive_surge_move_toward_closest_enemy")
        self.assertEqual(str(vengeful.effect_params.get("distance_roll", "") or ""), "D6+1")


if __name__ == "__main__":
    unittest.main()
