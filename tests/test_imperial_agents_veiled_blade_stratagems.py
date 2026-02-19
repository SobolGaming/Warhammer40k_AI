import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        movement="6",
        toughness="4",
        wounds="3",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name, *, faction_name="Imperial Agents", keywords=None, faction_keywords=None, toughness="4"):
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army("Imperial Agents", "Veiled Blade Elimination Force")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.turn = 1
    ia_player.command_points = 10
    enemy_player.command_points = 10
    return game, ia_player, enemy_player, ia_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_hit_threshold=None,
        crit_wound_threshold=None,
        crit_hit_reasons=(),
        crit_wound_reasons=(),
    )


def _melee_profile(strength: str = "4"):
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestImperialAgentsVeiledBladeStratagems(unittest.TestCase):
    def test_veiled_blade_stratagem_descriptors_registered(self):
        prime = get_stratagem_tool_descriptor(stratagem_id="000009758002")
        self.assertIsNotNone(prime)
        self.assertEqual(prime.name, "Prime Target")
        self.assertEqual(prime.effect, "wound_reroll_ones_vs_character_with_officio_warlord_full_reroll")
        self.assertEqual(str(prime.effect_params.get("reroll_wound_ones_vs_keyword", "") or ""), "CHARACTER")
        self.assertTrue(bool(prime.effect_params.get("officio_assassinorum_full_reroll_vs_enemy_warlord")))

        hyper = get_stratagem_tool_descriptor(stratagem_id="000009758003")
        self.assertIsNotNone(hyper)
        self.assertEqual(hyper.name, "Hyperstimms")
        self.assertEqual(hyper.effect, "toughness_bonus_and_conditional_feel_no_pain")
        self.assertEqual(int(hyper.effect_params.get("toughness_bonus", 0) or 0), 1)
        self.assertEqual(int(hyper.effect_params.get("eversor_assassin_feel_no_pain", 0) or 0), 4)

        blind = get_stratagem_tool_descriptor(stratagem_id="000009758006")
        self.assertIsNotNone(blind)
        self.assertEqual(blind.name, "Blind Grenades")
        self.assertEqual(blind.effect, "enemy_charge_roll_penalty")
        self.assertEqual(int(blind.effect_params.get("charge_roll_modifier", 0) or 0), -1)
        self.assertEqual(int(blind.effect_params.get("vindicare_charge_roll_modifier", 0) or 0), -2)

        ensnaring = get_stratagem_tool_descriptor(stratagem_id="000009758007")
        self.assertIsNotNone(ensnaring)
        self.assertEqual(ensnaring.name, "Ensnaring Trap")
        self.assertEqual(ensnaring.effect, "out_of_turn_charge_without_charge_bonus")
        self.assertFalse(bool(ensnaring.effect_params.get("count_as_charged", True)))
        self.assertEqual(int(ensnaring.effect_params.get("callidus_melee_wound_bonus", 0) or 0), 1)

        by_name = get_stratagem_tool_descriptor(name="ENSNARING TRAP")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), "000009758007")

    def test_prime_target_applies_wound_reroll_ones_vs_character_until_phase_end(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        agents = _make_unit(
            "Agents Operatives",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_character = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(agents)
        enemy_army.add_unit(enemy_character)
        _place_unit(game, agents, 10.0, 10.0)
        _place_unit(game, enemy_character, 14.0, 10.0)

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("PRIME TARGET", unit=agents, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(ia_player.command_points or 0), 9)

        wound_mods = agents.get_unit_wound_reroll_modifiers("ranged", target=enemy_character)
        self.assertIn(1, set(wound_mods.get("reroll_wound_values", ()) or ()))
        self.assertTrue(any("PRIME TARGET" in str(r) for r in list(wound_mods.get("reroll_wound_reasons", ()) or ())))

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        sr_after = getattr(agents, "special_rules", {}) or {}
        self.assertFalse(bool(sr_after.get("imperial_agents_prime_target_active")))
        wound_mods_after = agents.get_unit_wound_reroll_modifiers("ranged", target=enemy_character)
        self.assertFalse(any("PRIME TARGET" in str(r) for r in list(wound_mods_after.get("reroll_wound_reasons", ()) or ())))

    def test_prime_target_grants_officio_full_wound_reroll_vs_enemy_warlord(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        assassin = _make_unit(
            "Vindicare Assassin",
            keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_warlord = _make_unit(
            "Enemy Warlord",
            faction_name="Enemy",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ENEMY"],
        )
        enemy_warlord.is_warlord = True
        enemy_army.warlord = enemy_warlord

        ia_army.add_unit(assassin)
        enemy_army.add_unit(enemy_warlord)
        _place_unit(game, assassin, 10.0, 10.0)
        _place_unit(game, enemy_warlord, 14.0, 10.0)

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("PRIME TARGET", unit=assassin, phase_name="Shooting phase")
        self.assertTrue(ok)

        wound_mods = assassin.get_model_wound_reroll_modifiers(
            assassin.models[0],
            attack_type="ranged",
            target=enemy_warlord,
        )
        self.assertTrue(bool(wound_mods.get("reroll_wound_full")))
        self.assertTrue(any("PRIME TARGET" in str(r) for r in list(wound_mods.get("reroll_wound_full_reasons", ()) or ())))

    def test_blind_grenades_queues_applies_penalty_and_cleans_up(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        grenadier = _make_unit(
            "Agents Grenadiers",
            keywords=["INFANTRY", "GRENADES"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        charger = _make_unit(
            "Enemy Chargers",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(grenadier)
        enemy_army.add_unit(charger)
        _place_unit(game, grenadier, 10.0, 10.0)
        _place_unit(game, charger, 17.0, 10.0)

        _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
        game.event_system.publish("charge_declared", unit=charger, target_units=[grenadier])

        pending = _pending_by_name(ia_player.stratagems, "BLIND GRENADES")
        self.assertIsNotNone(pending)
        ok = ia_player.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=grenadier,
            charging_unit=charger,
            target_units=[grenadier],
            phase_name="Charge phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        charger_sr = getattr(charger, "special_rules", {}) or {}
        charge_mods = list(charger_sr.get("charge_roll_modifiers", []) or [])
        blind_mods = [m for m in charge_mods if isinstance(m, dict) and m.get("source_key") == "imperial_agents_blind_grenades"]
        self.assertTrue(blind_mods)
        self.assertEqual(int(blind_mods[0].get("value", 0) or 0), -1)
        self.assertIn(str(get_entity_id(grenadier)), set(blind_mods[0].get("target_unit_ids", []) or []))

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
        after_mods = list((getattr(charger, "special_rules", {}) or {}).get("charge_roll_modifiers", []) or [])
        self.assertFalse(any(isinstance(m, dict) and m.get("source_key") == "imperial_agents_blind_grenades" for m in after_mods))

    def test_blind_grenades_vindicare_target_applies_minus_two(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        vindicare = _make_unit(
            "Vindicare Assassin",
            keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        charger = _make_unit(
            "Enemy Chargers",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(vindicare)
        enemy_army.add_unit(charger)
        _place_unit(game, vindicare, 10.0, 10.0)
        _place_unit(game, charger, 17.0, 10.0)

        _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
        game.event_system.publish("charge_declared", unit=charger, target_units=[vindicare])
        pending = _pending_by_name(ia_player.stratagems, "BLIND GRENADES")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=vindicare,
            charging_unit=charger,
            target_units=[vindicare],
            phase_name="Charge phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        mods = list((getattr(charger, "special_rules", {}) or {}).get("charge_roll_modifiers", []) or [])
        blind_mods = [m for m in mods if isinstance(m, dict) and m.get("source_key") == "imperial_agents_blind_grenades"]
        self.assertTrue(blind_mods)
        self.assertEqual(int(blind_mods[0].get("value", 0) or 0), -2)

    def test_ensnaring_trap_queues_and_attempts_out_of_turn_charge_without_bonus(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        operatives = _make_unit(
            "Agents Operatives",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(operatives)
        enemy_army.add_unit(enemy)
        _place_unit(game, operatives, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)
        operatives.can_declare_charge_against = lambda *_args, **_kwargs: True

        _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))

        pending = _pending_by_name(ia_player.stratagems, "ENSNARING TRAP")
        self.assertIsNotNone(pending)
        with patch.object(game, "attempt_charge", return_value=True) as charge_mock:
            ok = ia_player.stratagems.use(
                "ENSNARING TRAP",
                unit=operatives,
                enemy_unit=enemy,
                phase_name="Charge phase",
                dequeue=True,
            )
        self.assertTrue(ok)
        charge_mock.assert_called_once()
        self.assertTrue(bool(charge_mock.call_args.kwargs.get("out_of_turn")))
        self.assertFalse(bool(charge_mock.call_args.kwargs.get("count_as_charged", True)))

    def test_ensnaring_trap_callidus_bonus_applies_until_fight_phase_end(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        callidus = _make_unit(
            "Callidus Assassin",
            keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness="4",
        )
        ia_army.add_unit(callidus)
        enemy_army.add_unit(enemy)
        _place_unit(game, callidus, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)
        callidus.can_declare_charge_against = lambda *_args, **_kwargs: True

        _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
        with patch.object(game, "attempt_charge", return_value=True):
            ok = ia_player.stratagems.use(
                "ENSNARING TRAP",
                unit=callidus,
                enemy_unit=enemy,
                phase_name="Charge phase",
            )
        self.assertTrue(ok)
        sr = getattr(callidus, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("ensnaring_trap_callidus_melee_wound_bonus_active")))

        _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
        profile = _melee_profile(strength="4")
        wound_with_bonus = profile._wound_target_with_tracking(
            enemy,
            callidus.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound_with_bonus.get("wound")))
        self.assertTrue(any("ENSNARING TRAP" in str(mod) for mod in list(wound_with_bonus.get("modifiers", []) or [])))

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        sr_after = getattr(callidus, "special_rules", {}) or {}
        self.assertFalse(bool(sr_after.get("ensnaring_trap_callidus_melee_wound_bonus_active")))

        wound_after_cleanup = profile._wound_target_with_tracking(
            enemy,
            callidus.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(wound_after_cleanup.get("wound")))

    def test_hyperstimms_queues_on_shooting_targets_selected_and_applies_toughness_until_phase_end(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        target = _make_unit(
            "Agents Character",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Attackers",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 16.0, 10.0)
        base_toughness = int(target.models[0].toughness or 0)

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
        pending = _pending_by_name(ia_player.stratagems, "HYPERSTIMMS")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=target,
            attacking_unit=attacker,
            target_units=[target],
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(target.models[0].toughness or 0), base_toughness + 1)

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertEqual(int(target.models[0].toughness or 0), base_toughness)
        sr_after = getattr(target, "special_rules", {}) or {}
        self.assertFalse(bool(sr_after.get("imperial_agents_hyperstimms_active")))

    def test_hyperstimms_fight_reaction_grants_eversor_fnp_and_cleans_up(self):
        game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
        eversor = _make_unit(
            "Eversor Assassin",
            keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
            toughness="4",
        )
        attacker = _make_unit(
            "Enemy Duelists",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(eversor)
        enemy_army.add_unit(attacker)
        _place_unit(game, eversor, 10.0, 10.0)
        _place_unit(game, attacker, 14.0, 10.0)
        base_toughness = int(eversor.models[0].toughness or 0)

        _set_phase(game, ia_player, "FIGHT_PHASE", 0)
        game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[eversor])
        pending = _pending_by_name(ia_player.stratagems, "HYPERSTIMMS")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=eversor,
            attacking_unit=attacker,
            target_units=[eversor],
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(eversor.models[0].toughness or 0), base_toughness + 1)
        fnp_entries = list(eversor.models[0].get_temporary_fnp_entries() or [])
        self.assertTrue(any(int(val or 0) == 4 for val, _cond in fnp_entries))

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(int(eversor.models[0].toughness or 0), base_toughness)
        fnp_after = list(eversor.models[0].get_temporary_fnp_entries() or [])
        self.assertFalse(any(int(val or 0) == 4 for val, _cond in fnp_after))


if __name__ == "__main__":
    unittest.main()
