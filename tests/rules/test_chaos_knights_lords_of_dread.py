import unittest

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
    ):
        self.name = name
        self.faction_data = {"name": "Chaos Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, objective_control: int = 1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
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


if __name__ == "__main__":
    unittest.main()
