from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.psychic_guidance import unit_within_psyker_range
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
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

    def test_spirit_conclave_step1_stratagem_descriptors_registered(self):
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


if __name__ == "__main__":
    unittest.main()
