from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.psychic_guidance import unit_within_psyker_range
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        wounds: str = "2",
        move: str = "8",
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    wounds: str = "2",
    move: str = "8",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
            move=move,
            model_count=int(quantity),
        ),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Spirit Conclave")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10

    aeldari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, aeldari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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
    return text.replace("\u2019", "'")


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


class TestAeldariSpiritConclaveStratagems(unittest.TestCase):
    def test_spirit_token_queues_and_makes_objective_sticky(self):
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        wraithguard = _make_unit(
            "Wraithguard",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "WRAITHGUARD", "WRAITH CONSTRUCT"],
            quantity=1,
        )
        aeldari_army.add_unit(wraithguard)
        _place_unit(game, wraithguard, 11.0, 10.0)

        objective_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives.append(objective)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SPIRIT TOKEN")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=wraithguard,
            objective=objective,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertIs(objective.location.sticky_controller, p1)
        self.assertEqual(str(objective.location.sticky_source or ""), "aeldari_spirit_token")

    def test_soul_bridge_queues_and_applies_virtual_psyker_range_until_next_command_phase(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        psyker = _make_unit(
            "Spiritseer",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        wraithlord = _make_unit(
            "Wraithlord",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "MONSTER", "WRAITHLORD", "WRAITH CONSTRUCT"],
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(wraithlord)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, wraithlord, 40.0, 10.0)

        self.assertFalse(unit_within_psyker_range(wraithlord))
        self.assertFalse(aeldari_army.aeldari_detachments.spirit_guides_battle_focus_applies(wraithlord))

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SOUL BRIDGE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=wraithlord,
            source_unit=psyker,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(bool(wraithlord.special_rules.get("aeldari_soul_bridge_active")))
        self.assertEqual(
            str(wraithlord.special_rules.get("aeldari_soul_bridge_psyker_unit_id", "") or ""),
            str(get_entity_id(psyker) or ""),
        )
        self.assertTrue(unit_within_psyker_range(wraithlord))
        self.assertTrue(aeldari_army.aeldari_detachments.spirit_guides_battle_focus_applies(wraithlord))

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        self.assertFalse(bool(wraithlord.special_rules.get("aeldari_soul_bridge_active")))
        self.assertFalse(unit_within_psyker_range(wraithlord))
        self.assertFalse(aeldari_army.aeldari_detachments.spirit_guides_battle_focus_applies(wraithlord))

    def test_soul_bridge_rejects_non_psyker_source(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        guardian = _make_unit(
            "Guardian Defenders",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
            quantity=1,
        )
        wraithlord = _make_unit(
            "Wraithlord",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "MONSTER", "WRAITHLORD", "WRAITH CONSTRUCT"],
            quantity=1,
        )
        aeldari_army.add_unit(guardian)
        aeldari_army.add_unit(wraithlord)
        _place_unit(game, guardian, 10.0, 10.0)
        _place_unit(game, wraithlord, 20.0, 10.0)

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        ok = p1.stratagems.use(
            "SOUL BRIDGE",
            unit=wraithlord,
            source_unit=guardian,
            phase_name="Command phase",
        )
        self.assertFalse(ok)
        self.assertEqual(int(p1.command_points or 0), 10)
        self.assertFalse(bool(wraithlord.special_rules.get("aeldari_soul_bridge_active")))

    def test_wraithbone_armour_queues_and_reduces_incoming_damage_by_one(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        wraithguard = _make_unit(
            "Wraithguard",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "WRAITHGUARD", "WRAITH CONSTRUCT"],
            wounds="8",
            quantity=1,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(wraithguard)
        enemy_army.add_unit(enemy)
        _place_unit(game, wraithguard, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[wraithguard])
        pending = _pending_by_name(p1.stratagems, "WRAITHBONE ARMOUR")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=wraithguard,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        profile = Wargear(
            {
                "name": "Test Rifle",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-1",
                "D": "3",
                "description": "",
            }
        ).profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        result = profile._damage_target_with_tracking(
            wraithguard.models[0],
            enemy.models[0],
            dict(attack_instance),
            game_map=game.map,
            roll_value=3,
            allow_rerolls=False,
        )
        self.assertEqual(int(result.get("damage_applied", 0) or 0), 2)
        self.assertTrue(any("-1D" in str(effect or "") for effect in list(result.get("special_effects", []) or [])))

    def test_seers_eye_queues_and_ignores_ap_and_damage_modifiers_against_selected_enemy(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        psyker = _make_unit(
            "Spiritseer",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "PSYKER"],
            quantity=1,
        )
        wraithguard = _make_unit(
            "Wraithguard",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "WRAITHGUARD", "WRAITH CONSTRUCT"],
            quantity=1,
        )
        enemy_marked = _make_unit(
            "Enemy Marked",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds="8",
            quantity=1,
        )
        enemy_other = _make_unit(
            "Enemy Other",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds="8",
            quantity=1,
        )
        aeldari_army.add_unit(psyker)
        aeldari_army.add_unit(wraithguard)
        enemy_army.add_unit(enemy_marked)
        enemy_army.add_unit(enemy_other)
        _place_unit(game, psyker, 10.0, 10.0)
        _place_unit(game, wraithguard, 12.0, 10.0)
        _place_unit(game, enemy_marked, 20.0, 10.0)
        _place_unit(game, enemy_other, 22.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SEER")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            source_unit=psyker,
            unit=wraithguard,
            enemy_unit=enemy_marked,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        for enemy_unit in (enemy_marked, enemy_other):
            sr = getattr(enemy_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["defensive_ap_worsen_phase"] = [
                {
                    "value": 1,
                    "attack_type": "any",
                    "expires_phase": "SHOOTING_PHASE",
                    "source": "test_ap_worsen",
                }
            ]
            sr["defensive_damage_reductions"] = [
                {
                    "value": 1,
                    "attack_type": "any",
                    "expires_phase": "SHOOTING_PHASE",
                    "source": "test_damage_reduction",
                }
            ]
            enemy_unit.special_rules = sr

        weapon = Wargear(
            {
                "name": "Wraithcannon",
                "type": "Ranged",
                "range": "18",
                "A": "1",
                "BS_WS": "4+",
                "S": "8",
                "AP": "-2",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]

        ap_marked = profile.get_effective_ap(wraithguard.models[0], enemy_marked)
        ap_other = profile.get_effective_ap(wraithguard.models[0], enemy_other)
        self.assertEqual(int(ap_marked), -2)
        self.assertEqual(int(ap_other), -1)

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        dmg_marked = profile._damage_target_with_tracking(
            enemy_marked.models[0],
            wraithguard.models[0],
            dict(attack_instance),
            game_map=game.map,
            roll_value=3,
            allow_rerolls=False,
        )
        dmg_other = profile._damage_target_with_tracking(
            enemy_other.models[0],
            wraithguard.models[0],
            dict(attack_instance),
            game_map=game.map,
            roll_value=3,
            allow_rerolls=False,
        )
        self.assertEqual(int(dmg_marked.get("damage_applied", 0) or 0), 3)
        self.assertEqual(int(dmg_other.get("damage_applied", 0) or 0), 2)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertFalse(bool(getattr(wraithguard, "special_rules", {}).get("aeldari_spirit_seers_eye_active")))

    def test_spirit_conclave_step1_stratagem_descriptors_registered(self):
        seers_eye = get_stratagem_tool_descriptor(stratagem_id="000009908002")
        self.assertIsNotNone(seers_eye)
        self.assertEqual(str(seers_eye.name), "Seer's Eye")
        self.assertEqual(int(seers_eye.cp_cost), 1)
        self.assertEqual(str(seers_eye.effect), "ignore_ap_and_damage_modifiers_against_selected_enemy")

        wraithbone = get_stratagem_tool_descriptor(stratagem_id="000009908003")
        self.assertIsNotNone(wraithbone)
        self.assertEqual(str(wraithbone.name), "Wraithbone Armour")
        self.assertEqual(int(wraithbone.cp_cost), 1)
        self.assertEqual(str(wraithbone.effect), "defensive_damage_reduction")

        soul_bridge = get_stratagem_tool_descriptor(stratagem_id="000009908005")
        self.assertIsNotNone(soul_bridge)
        self.assertEqual(str(soul_bridge.name), "Soul Bridge")
        self.assertEqual(int(soul_bridge.cp_cost), 1)
        self.assertEqual(
            str(soul_bridge.effect),
            "count_as_within_12_of_selected_psyker_for_psychic_guidance_and_spirit_guides",
        )

        spirit_token = get_stratagem_tool_descriptor(stratagem_id="000009908006")
        self.assertIsNotNone(spirit_token)
        self.assertEqual(str(spirit_token.name), "Spirit Token")
        self.assertEqual(int(spirit_token.cp_cost), 1)
        self.assertEqual(str(spirit_token.effect), "sticky_objective")

        by_name_soul_bridge = get_stratagem_tool_descriptor(name="SOUL BRIDGE")
        self.assertIsNotNone(by_name_soul_bridge)
        self.assertEqual(str(by_name_soul_bridge.stratagem_id), "000009908005")

        by_name_spirit_token = get_stratagem_tool_descriptor(name="SPIRIT TOKEN")
        self.assertIsNotNone(by_name_spirit_token)
        self.assertEqual(str(by_name_spirit_token.stratagem_id), "000009908006")

        by_name_seers_eye = get_stratagem_tool_descriptor(name="SEER'S EYE")
        self.assertIsNotNone(by_name_seers_eye)
        self.assertEqual(str(by_name_seers_eye.stratagem_id), "000009908002")

        by_name_wraithbone = get_stratagem_tool_descriptor(name="WRAITHBONE ARMOUR")
        self.assertIsNotNone(by_name_wraithbone)
        self.assertEqual(str(by_name_wraithbone.stratagem_id), "000009908003")


if __name__ == "__main__":
    unittest.main()
