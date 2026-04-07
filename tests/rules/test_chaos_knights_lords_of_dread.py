import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.utility.entity_ids import get_entity_id


_LORDS_ENHANCEMENT_TEXT = {
    "000010308002": "CHAOS KNIGHTS model only. You can re-roll Charge rolls made for the bearer's unit. Once per battle, in your Charge phase, the bearer can use this Enhancement; until end of phase, the bearer's unit can charge in a turn in which it Advanced.",
    "000010308003": "CHAOS KNIGHTS model only. The bearer's ranged weapons have [ASSAULT]. Once per battle, in the Fight phase, the bearer can use this Enhancement; until end of phase, models in the bearer's unit have Fights First.",
    "000010308004": "CHAOS KNIGHTS model only. The bearer has Deep Strike. Once per battle, at the end of your opponent's turn, if the bearer is not within Engagement Range, you can remove it from the battlefield and place it into Strategic Reserves.",
    "000010308005": "CHAOS KNIGHTS model only. The bearer has a Save characteristic of 2+. Once per battle, at the start of either player's Command phase, the bearer can use this Enhancement; it regains up to D6 lost wounds.",
    "000010308006": "CHAOS KNIGHTS model only. Once per battle round, you can target the bearer's unit with the Command Re-roll Stratagem for 0CP, even if another unit from your army has already been targeted this phase. Lord of Deceit (Aura): each time your opponent targets a unit from their army with a Stratagem, if that unit is within 12\" of this model, increase the cost by 1CP.",
    "000010308007": "CHAOS KNIGHTS model only. The bearer has Stealth. Once per battle, after you make a saving throw for the bearer, you can change the Damage characteristic of that attack to 0.",
}


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
        wounds: int = 12,
        model_count: int = 1,
        abilities=None,
        base_size: str = "100mm",
    ):
        self.name = name
        self.faction_data = {"name": "Chaos Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        wounds_value = max(1, int(wounds or 1))
        self.datasheets_unit_composition = [
            {"description": f"{count} Test Model" if count == 1 else f"{count} Test Models"}
        ]
        self.datasheets_models_cost = [{"description": f"{count} model" if count == 1 else f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": str(wounds_value),
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": str(base_size),
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name,
    *,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
    wounds: int = 12,
    model_count: int = 1,
    abilities=None,
    base_size: str = "100mm",
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
        wounds=wounds,
        model_count=model_count,
        abilities=abilities,
        base_size=base_size,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(detachment_type: str = "Lords of Dread"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    game.turn = 1

    ck_army = Army.with_detachment("Chaos Knights", detachment_type)
    ck_army.faction_id = "QT"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ck_player = Player("CK", control=PlayerControl.LOCAL, army=ck_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ck_player)
    game.add_player(enemy_player)
    return game, ck_player, ck_army, enemy_army


def _set_model_location(unit, x: float, y: float) -> None:
    model = unit.models[0]
    model.set_location(float(x), float(y), 0.0, 0.0)


def _deploy_unit(game, unit, x: float, y: float, *, spacing: float = 0.5) -> None:
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(float(x + spacing * idx), float(y), 0.0, 0.0)
    if unit not in list(game.map.units or []):
        game.map.units.append(unit)
    game.rebuild_entity_registry()


def _apply_lords_enhancement(unit, *, enhancement_id: str, enhancement_name: str):
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="QT",
        detachment="Lords of Dread",
        detachment_id="000010308",
        points=0,
        description=str(_LORDS_ENHANCEMENT_TEXT.get(str(enhancement_id), enhancement_name)),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


class TestChaosKnightsLordsOfDread(unittest.TestCase):
    def test_tyrannical_court_objective_control_bonus_applies_to_character_models(self):
        _game, _player, ck_army, _enemy_army = _build_game("Lords of Dread")
        character_unit = _make_unit(
            "Knight Character",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        non_character_unit = _make_unit(
            "War Dog",
            keywords=["CHAOS KNIGHTS", "WAR DOG"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(character_unit)
        ck_army.add_unit(non_character_unit)

        character_model = character_unit.models[0]
        non_character_model = non_character_unit.models[0]
        base_character_oc = int(getattr(character_model, "_base_objective_control", 0) or 0)
        base_non_character_oc = int(getattr(non_character_model, "_base_objective_control", 0) or 0)

        self.assertEqual(
            int(character_unit.get_effective_model_characteristic(character_model, "objective_control") or 0),
            base_character_oc + 2,
        )
        self.assertEqual(
            int(non_character_unit.get_effective_model_characteristic(non_character_model, "objective_control") or 0),
            base_non_character_oc,
        )

        mgr = ck_army.chaos_knights_detachments
        bonus, source = mgr.tyrannical_court_objective_control_bonus(character_model, unit=character_unit)
        self.assertEqual(int(bonus or 0), 2)
        self.assertEqual(str(source), "Tyrannical Court")

    def test_tyrannical_court_claimed_for_dark_gods_zero_cp_once_per_battle_round(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, ck_army, _enemy_army = _build_game("Lords of Dread")
        warlord = _make_unit(
            "Knight Warlord",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(warlord)
        ck_army.select_warlord(warlord)
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS"

        strat = Stratagem(
            id="claimed-for-dark-gods-test",
            name="CLAIMED FOR THE DARK GODS",
            type="Lords of Dread - Epic Deed Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Lords of Dread",
            faction_id="QT",
        )

        self.assertTrue(strat.can_use(player, game, target_unit=warlord))
        self.assertTrue(strat.use(player, game, target_unit=warlord))
        self.assertEqual(int(player.command_points or 0), 0)

        self.assertFalse(strat.can_use(player, game, target_unit=warlord))

        game.turn = 2
        self.assertTrue(strat.can_use(player, game, target_unit=warlord))

    def test_tyrannical_court_discount_requires_warlord_on_battlefield(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, ck_army, _enemy_army = _build_game("Lords of Dread")
        warlord = _make_unit(
            "Knight Warlord",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(warlord)
        ck_army.select_warlord(warlord)
        warlord.deployed = False
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS"

        strat = Stratagem(
            id="claimed-for-dark-gods-test",
            name="CLAIMED FOR THE DARK GODS",
            type="Lords of Dread - Epic Deed Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Lords of Dread",
            faction_id="QT",
        )

        self.assertFalse(strat.can_use(player, game, target_unit=warlord))

    def test_lords_enhancements_activation_and_effect_specs(self):
        game, _player, ck_army, _enemy_army = _build_game("Lords of Dread")

        throne_unit = _make_unit(
            "Throne Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        putrid_unit = _make_unit(
            "Putrid Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        blade_unit = _make_unit(
            "Blade Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        warp_unit = _make_unit(
            "Warp Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        blessing_unit = _make_unit(
            "Blessed Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(throne_unit)
        ck_army.add_unit(putrid_unit)
        ck_army.add_unit(blade_unit)
        ck_army.add_unit(warp_unit)
        ck_army.add_unit(blessing_unit)

        _apply_lords_enhancement(
            throne_unit,
            enhancement_id="000010308002",
            enhancement_name="Throne Mechanicum of Skulls",
        )
        _apply_lords_enhancement(
            putrid_unit,
            enhancement_id="000010308005",
            enhancement_name="Putrid Carapace",
        )
        _apply_lords_enhancement(
            blade_unit,
            enhancement_id="000010308003",
            enhancement_name="Blade of Celerity",
        )
        _apply_lords_enhancement(
            warp_unit,
            enhancement_id="000010308004",
            enhancement_name="Warp-borne Stalker",
        )
        _apply_lords_enhancement(
            blessing_unit,
            enhancement_id="000010308007",
            enhancement_name="Blessing of the Dark Master",
        )

        throne_unit.round_state.advanced_this_round = True
        self.assertTrue(throne_unit.can_use_enhancement_charge_after_advance_once())
        self.assertTrue(throne_unit.activate_enhancement_charge_after_advance_once())
        game.phase = BattleRoundPhases.CHARGE_PHASE
        self.assertTrue(throne_unit.can_charge_after_advance())
        self.assertFalse(throne_unit.can_use_enhancement_charge_after_advance_once())

        putrid_model = putrid_unit.models[0]
        putrid_model.wounds = max(1, int(getattr(putrid_model, "_base_wounds", putrid_model.wounds) or 0) - 4)
        self.assertEqual(
            int(putrid_unit.get_effective_model_characteristic(putrid_model, "save") or 0),
            2,
        )
        self.assertTrue(putrid_unit.can_use_enhancement_putrid_carapace())
        healed = int(putrid_unit.activate_enhancement_putrid_carapace(heal_amount=6) or 0)
        self.assertGreaterEqual(healed, 1)
        self.assertFalse(putrid_unit.can_use_enhancement_putrid_carapace())

        self.assertTrue(blade_unit.has_enhancement_fight_first_once_per_battle())
        self.assertTrue(blade_unit.can_use_enhancement_fight_first())
        self.assertTrue(blade_unit.activate_enhancement_fight_first())
        self.assertTrue(bool(blade_unit.special_rules.get("enhancement_fight_first_active", False)))
        self.assertFalse(blade_unit.can_use_enhancement_fight_first())

        self.assertTrue(warp_unit.has_deep_strike())
        warp_sr = dict(getattr(warp_unit, "special_rules", {}) or {})
        warp_once_key = str(warp_sr.get("enhancement_warp_borne_stalker_once_key", "warp_borne_stalker") or "warp_borne_stalker")
        spec_before = warp_unit.get_end_of_opponent_turn_strategic_reserves_ability()
        self.assertIsInstance(spec_before, dict)
        self.assertEqual(str(spec_before.get("ability_key", "") or ""), warp_once_key)
        self.assertTrue(bool(spec_before.get("once_per_battle", False)))

        self.assertTrue(blessing_unit.has_stealth())
        blessing_specs = list(blessing_unit.model_allocated_damage_zero_specs(blessing_unit.models[0]) or [])
        self.assertTrue(blessing_specs)
        self.assertTrue(
            any(
                "blessing_of_the_dark_master" in str(spec.get("key", "") or "").lower()
                for spec in blessing_specs
            )
        )

    def test_mirror_of_fates_command_reroll_zero_cp_and_repeat_exception(self):
        game, player, ck_army, _enemy_army = _build_game("Lords of Dread")
        mirror_unit = _make_unit(
            "Mirror Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        other_unit = _make_unit(
            "Other Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(mirror_unit)
        ck_army.add_unit(other_unit)
        _apply_lords_enhancement(
            mirror_unit,
            enhancement_id="000010308006",
            enhancement_name="Mirror of Fates",
        )

        strat = player.stratagems.get_by_name("COMMAND RE-ROLL")
        self.assertIsNotNone(strat)

        player.command_points = 0
        player.set_next_optional_decision("MIRROR_OF_FATES", True)
        first = player.apply_stratagem_cp_cost(strat, target_unit=mirror_unit)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertIn("Mirror of Fates", " ".join(list(first.get("reasons", []) or [])))

        player.set_next_optional_decision("MIRROR_OF_FATES", True)
        second = player.apply_stratagem_cp_cost(strat, target_unit=mirror_unit)
        self.assertEqual(int(second.get("cost", -1)), 1)

        game.turn = 2
        player.set_next_optional_decision("MIRROR_OF_FATES", True)
        third = player.apply_stratagem_cp_cost(strat, target_unit=mirror_unit)
        self.assertEqual(int(third.get("cost", -1)), 0)

        game.turn = 1
        player._ability_used_battle_round.pop("MIRROR_OF_FATES", None)
        mgr = player.stratagems
        mgr._current_phase_name = "Shooting phase"
        mgr._used_stratagems_this_phase = {"COMMAND RE-ROLL"}
        mgr._command_reroll_units_this_phase = set()
        player.command_points = 0

        mirror_ctx = {"phase_name": "Shooting phase", "target_unit": mirror_unit, "unit": mirror_unit}
        avail_mirror = mgr._evaluate_availability(strat, mirror_ctx, is_active_turn=True)
        self.assertTrue(bool(avail_mirror.get("available", False)))
        self.assertEqual(int(avail_mirror.get("cp_cost", 99)), 0)

        other_ctx = {"phase_name": "Shooting phase", "target_unit": other_unit, "unit": other_unit}
        avail_other = mgr._evaluate_availability(strat, other_ctx, is_active_turn=True)
        self.assertFalse(bool(avail_other.get("available", True)))
        self.assertEqual(str(avail_other.get("reason", "") or ""), "Already used this phase")

        mgr._record_command_reroll_use(mirror_unit)
        avail_mirror_again = mgr._evaluate_availability(strat, mirror_ctx, is_active_turn=True)
        self.assertFalse(bool(avail_mirror_again.get("available", True)))

    def test_mirror_of_fates_lord_of_deceit_increases_enemy_stratagem_cp_within_12(self):
        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        source = _make_unit(
            "Mirror Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        enemy = _make_unit(
            "Enemy Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            objective_control=2,
        )
        ck_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _apply_lords_enhancement(
            source,
            enhancement_id="000010308006",
            enhancement_name="Mirror of Fates",
        )
        source.deployed = True
        enemy.deployed = True
        _set_model_location(source, 0.0, 0.0)
        _set_model_location(enemy, 10.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        specs = list(source.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("source_model_id", "") or ""), str(get_entity_id(source.models[0]) or ""))

        preview_in = player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertTrue(bool(preview_in.get("auto")))
        applied_in = player.apply_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertEqual(int(applied_in.get("increase", 0) or 0), 1)

        _set_model_location(enemy, 20.0, 0.0)
        preview_out = player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertFalse(bool(preview_out.get("auto")))
        self.assertFalse(bool(preview_out.get("optional")))

    def test_claimed_for_dark_gods_sets_sticky_minimum_control_and_breaks_only_above_five(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        enemy_player = next(iter([p for p in list(game.players or []) if p is not player]), None)
        self.assertIsNotNone(enemy_player)

        character = _make_unit(
            "Knight Desecrator",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        enemy = _make_unit(
            "Enemy Objective Holder",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            objective_control=4,
            wounds=1,
            base_size="32mm",
        )
        ck_army.add_unit(character)
        enemy_army.add_unit(enemy)

        objective_point = ObjectivePoint(x=10.0, y=10.0, z=0.0, control_radius=3.0)
        objective_point.controlling_player = player
        objective = Objective(
            name="Central Objective",
            category=ObjectiveCategory.PRIMARY,
            points=5,
            description="Hold the center",
            conditions=lambda _game: True,
            location=objective_point,
        )
        game.map.objectives = [objective]
        game.objectives = [objective]

        _deploy_unit(game, character, 10.0, 10.0)
        _deploy_unit(game, enemy, 30.0, 30.0)
        player.command_points = 5
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0

        ok = player.stratagems.use(
            "CLAIMED FOR THE DARK GODS",
            unit=character,
            objective=objective,
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertIs(objective_point.sticky_controller, player)
        self.assertEqual(int(objective_point.sticky_minimum_control or 0), 5)

        _set_model_location(character, 30.0, 30.0)
        enemy_model = enemy.models[0]
        enemy_model.objective_control = 4
        _set_model_location(enemy, 10.0, 10.0)
        objective_point.update_control(game)
        self.assertIs(objective_point.controlling_player, player)
        self.assertIs(objective_point.sticky_controller, player)
        self.assertEqual(int(objective_point.sticky_minimum_control or 0), 5)

        enemy_model.objective_control = 6
        objective_point.update_control(game)
        self.assertIs(objective_point.controlling_player, enemy_player)
        self.assertIsNone(objective_point.sticky_controller)
        self.assertEqual(int(objective_point.sticky_minimum_control or 0), 0)

    def test_titanic_duel_grants_reroll_ones_or_full_against_selected_target(self):
        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        source = _make_unit(
            "Knight Rampager",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        selected_vehicle = _make_unit(
            "Enemy Tank",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            objective_control=2,
        )
        other_vehicle = _make_unit(
            "Enemy Walker",
            keywords=["MONSTER"],
            faction_keywords=["ENEMY"],
            objective_control=2,
        )
        ck_army.add_unit(source)
        enemy_army.add_unit(selected_vehicle)
        enemy_army.add_unit(other_vehicle)
        _deploy_unit(game, source, 0.0, 0.0)
        _deploy_unit(game, selected_vehicle, 8.0, 0.0)
        _deploy_unit(game, other_vehicle, 16.0, 0.0)
        player.command_points = 5
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ok = player.stratagems.use(
            "TITANIC DUEL",
            unit=source,
            enemy_unit=selected_vehicle,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        hit_mods = source.get_unit_hit_reroll_modifiers("ranged", target=selected_vehicle)
        wound_mods = source.get_unit_wound_reroll_modifiers("ranged", target=selected_vehicle)
        other_hit_mods = source.get_unit_hit_reroll_modifiers("ranged", target=other_vehicle)
        other_wound_mods = source.get_unit_wound_reroll_modifiers("ranged", target=other_vehicle)

        self.assertIn(1, tuple(hit_mods.get("reroll_hit_values", ()) or ()))
        self.assertIn(1, tuple(wound_mods.get("reroll_wound_values", ()) or ()))
        self.assertFalse(bool(other_hit_mods.get("reroll_hit_full", False)))
        self.assertFalse(bool(other_wound_mods.get("reroll_wound_full", False)))
        self.assertNotIn(1, tuple(other_hit_mods.get("reroll_hit_values", ()) or ()))
        self.assertNotIn(1, tuple(other_wound_mods.get("reroll_wound_values", ()) or ()))

        game2, player2, ck_army2, enemy_army2 = _build_game("Lords of Dread")
        source2 = _make_unit(
            "Knight Abominant",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        selected_titanic = _make_unit(
            "Enemy Titanic Engine",
            keywords=["VEHICLE", "TITANIC"],
            faction_keywords=["ENEMY"],
            objective_control=2,
        )
        other_target = _make_unit(
            "Enemy Stalker",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            objective_control=2,
        )
        ck_army2.add_unit(source2)
        enemy_army2.add_unit(selected_titanic)
        enemy_army2.add_unit(other_target)
        _deploy_unit(game2, source2, 0.0, 0.0)
        _deploy_unit(game2, selected_titanic, 8.0, 0.0)
        _deploy_unit(game2, other_target, 16.0, 0.0)
        player2.command_points = 5
        game2.phase = BattleRoundPhases.FIGHT_PHASE
        game2.current_player_index = 0

        ok = player2.stratagems.use(
            "TITANIC DUEL",
            unit=source2,
            enemy_unit=selected_titanic,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)

        hit_mods = source2.get_unit_hit_reroll_modifiers("melee", target=selected_titanic)
        wound_mods = source2.get_unit_wound_reroll_modifiers("melee", target=selected_titanic)
        other_hit_mods = source2.get_unit_hit_reroll_modifiers("melee", target=other_target)
        other_wound_mods = source2.get_unit_wound_reroll_modifiers("melee", target=other_target)

        self.assertTrue(bool(hit_mods.get("reroll_hit_full", False)))
        self.assertTrue(bool(wound_mods.get("reroll_wound_full", False)))
        self.assertFalse(bool(other_hit_mods.get("reroll_hit_full", False)))
        self.assertFalse(bool(other_wound_mods.get("reroll_wound_full", False)))

    def test_crushed_like_vermin_inflicts_mortal_wounds_and_triggers_battleshock_on_destroy(self):
        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        source = _make_unit(
            "Knight Desecrator",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        enemy = _make_unit(
            "Enemy Screening Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            objective_control=2,
            wounds=1,
            model_count=2,
            base_size="32mm",
        )
        ck_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, source, 8.0, 0.0)
        _deploy_unit(game, enemy, 0.0, 0.0, spacing=0.8)
        source.models[0].last_move_path = [(-8.0, 0.0, 0.0), (8.0, 0.0, 0.0)]
        player.command_points = 5
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        candidates = list(player.stratagems._lords_of_dread_crushed_like_vermin_enemy_candidates(source) or [])
        self.assertIn(enemy, candidates)

        battle_shock_turns = []
        enemy.take_battle_shock_test = lambda current_turn=1: battle_shock_turns.append(int(current_turn or 0))
        destroyed_model = enemy.models[0]

        def _apply_mortal_wounds(_target_unit, mortal_wound_amount, game_map=None):
            del game_map
            if int(mortal_wound_amount or 0) <= 0:
                return 0
            if destroyed_model in list(enemy.models or []):
                enemy.models.remove(destroyed_model)
                enemy.models_lost.append(destroyed_model)
                destroyed_model.wounds = 0
                return 1
            return 0

        source._apply_mortal_wounds_to_unit = _apply_mortal_wounds
        with patch("warhammer40k_ai.rules.stratagems_chaos_knights.get_roll", side_effect=[4, 1, 1, 1, 1, 1]):
            ok = player.stratagems.use(
                "CRUSHED LIKE VERMIN",
                unit=source,
                enemy_unit=enemy,
                enemy_candidates=candidates,
                action="normal move",
                phase_name="Movement phase",
            )
        self.assertTrue(ok)
        self.assertEqual(int(len(list(enemy.models_lost or []))), 1)
        self.assertEqual(battle_shock_turns, [1])

    def test_spiteful_demise_allows_deadly_demise_on_four_plus(self):
        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        source = _make_unit(
            "Exploding Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
            wounds=10,
            abilities=[
                {
                    "name": "Deadly Demise",
                    "description": "Deadly Demise",
                    "type": "Ability",
                    "parameter": "D3",
                }
            ],
        )
        enemy = _make_unit(
            "Enemy Victim",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            objective_control=2,
            wounds=1,
            base_size="32mm",
        )
        ck_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, source, 0.0, 0.0)
        _deploy_unit(game, enemy, 0.5, 0.0)
        player.command_points = 5
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        destroyed_model = source.models[0]
        source.models = []
        source.models_lost.append(destroyed_model)
        destroyed_model.wounds = 0

        ok = player.stratagems.use(
            "SPITEFUL DEMISE",
            destroyed_unit=source,
            destroyed_model=destroyed_model,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(getattr(destroyed_model, "_chaos_knights_spiteful_demise_trigger_threshold_once", 0) or 0), 4)

        explosion_calls = []
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4), patch.object(
            source,
            "_apply_deadly_demise_explosion",
            side_effect=lambda **kwargs: explosion_calls.append(dict(kwargs)),
        ):
            triggered = source._trigger_deadly_demise(destroyed_model, game.map)
        self.assertFalse(triggered)
        self.assertEqual(len(explosion_calls), 1)
        self.assertIs(explosion_calls[0]["game_map"], game.map)
        self.assertEqual(int(getattr(destroyed_model, "_chaos_knights_spiteful_demise_trigger_threshold_once", 0) or 0), 0)

    def test_trophy_hunter_generic_parser_applies_six_inch_consolidate(self):
        game, player, ck_army, enemy_army = _build_game("Lords of Dread")
        hunter = _make_unit(
            "Hunter Knight",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        enemy = _make_unit(
            "Enemy Screen",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            objective_control=2,
            base_size="32mm",
        )
        ck_army.add_unit(hunter)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, hunter, 10.0, 10.0)
        _deploy_unit(game, enemy, 16.5, 10.0)
        player.command_points = 5
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ok = player.stratagems.use(
            "TROPHY HUNTER",
            unit=hunter,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        sr = dict(getattr(hunter, "special_rules", {}) or {})
        self.assertEqual(float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0), 6.0)
        self.assertTrue(bool(sr.get("stratagem_consolidate_requires_engagement", False)))
        self.assertEqual(str(sr.get("stratagem_consolidate_source", "") or ""), "TROPHY HUNTER")


if __name__ == "__main__":
    unittest.main()
