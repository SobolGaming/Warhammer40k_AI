from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


RITES_OF_BATTLE_TEXT = (
    "Once per battle round, one unit from your army with this ability can use it when its unit is targeted "
    "with a Stratagem. If it does, reduce the CP cost of that use of that Stratagem by 1CP."
)
ASTARTES_BANNER_TEXT = "While this model is leading a unit, add 1 to the Objective Control characteristic of models in that unit."
TACTICAL_PRECISION_TEXT = (
    "While this model is leading a unit, weapons equipped by models in that unit have the [LETHAL HITS] ability."
)
ORBITAL_COMMS_ARRAY_TEXT = (
    'While a friendly ADEPTUS ASTARTES unit is within 6" of the bearer, each time you target that unit with a Stratagem, '
    "roll one D6: on a 5+, you gain 1CP."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        abilities=None,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
    ) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


class _RegistryStub:
    def __init__(self, units, player=None):
        self._units = {str(getattr(unit, "_id", "") or ""): unit for unit in list(units or [])}
        self._players = {}
        if player is not None:
            player_id = str(getattr(player, "id", "") or "")
            if player_id:
                self._players[player_id] = player

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id or ""))
        if kind == "player":
            return self._players.get(str(entity_id or ""))
        return None


class _GameStub:
    def __init__(self, *, enemies, units, player=None):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.is_authoritative = True
        self.decision_queue = DecisionQueue()
        self.entity_registry = _RegistryStub(units, player=player)
        self._enemies = list(enemies or [])

    def request_decision(self, request):
        self.decision_queue.add(request)

    def get_enemy_units(self, _player):
        return list(self._enemies)

    def _resolve_unit_by_id(self, entity_id: str):
        return self.entity_registry.get(entity_id, kind="unit")


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    abilities=None,
    keywords=None,
    faction_keywords=None,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_player(units, *, detachment: str = "Gladius Task Force", control: PlayerControl = PlayerControl.LOCAL) -> tuple[Player, Army]:
    army = Army("Space Marines", detachment)
    army.faction_id = "SM"
    army.units = list(units if isinstance(units, (list, tuple)) else [units])
    for unit in list(army.units or []):
        unit.set_parent_army(army)
    player = Player("Space Marines", control=control, army=army)
    player.set_game(SimpleNamespace(turn=1))
    return player, army


def _build_full_game(*, detachment: str = "Gladius Task Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment)
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
    )


class TestSpaceMarinesFaqValidation(unittest.TestCase):
    def test_oath_of_moment_allows_selecting_reserve_targets(self):
        reserve_enemy = _make_unit(
            "Reserve Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        reserve_enemy.deployed = False
        reserve_enemy.reserve_status = "reserves"

        player, army = _make_player([], control=PlayerControl.REMOTE)
        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr

        game = _GameStub(enemies=[reserve_enemy], units=[reserve_enemy], player=player)
        mgr.on_command_phase_start(game=game, player=player)

        request = game.decision_queue.peek()
        self.assertIsNotNone(request)
        option = next(
            opt for opt in request.options if opt.payload.get("target_unit_id") == getattr(reserve_enemy, "_id", None)
        )
        result = DecisionResult(decision_id=request.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        applied = dispatch_decision(game, request, result)

        self.assertTrue(bool(applied.ok))
        self.assertEqual(str(mgr.oathOfMomentTargetUnitId or ""), str(reserve_enemy._id or ""))

    def test_rites_of_battle_can_target_captain_unit_in_strategic_reserves(self):
        captain = _make_unit(
            "Captain",
            abilities=[{"name": "Rites of Battle", "description": RITES_OF_BATTLE_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["CHARACTER", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        captain.deployed = False
        captain.reserve_status = "strategic_reserves"

        player, _army = _make_player([captain])
        player.command_points = 1
        player.decision_hook = lambda _player, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"

        stratagem = Stratagem(
            id="rites_reserves_test",
            name="Armor of Contempt",
            type="Core",
            description="",
            cp_cost=2,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        self.assertTrue(bool(stratagem.can_use(player, player.game, target_unit=captain)))
        self.assertTrue(bool(stratagem.use(player, player.game, target_unit=captain)))
        self.assertEqual(int(player.command_points or 0), 0)

    def test_unit_in_reserves_can_use_beacon_angelis_enhancement(self):
        bearer = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        game, sm_army, _enemy_army, player, _enemy_player = _build_full_game(detachment="Black Spear Task Force")
        sm_army.add_unit(bearer)
        game.map.units = [bearer]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522004",
            name="Beacon Angelis",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=15,
            description="",
        ).apply_to_unit(bearer)
        bearer.deployed = False
        bearer.reserve_status = "reserves"

        rapid_ingress = SimpleNamespace(name="RAPID INGRESS", cp_cost=1)
        preview = player.preview_stratagem_cp_cost(rapid_ingress, target_unit=bearer)
        applied = player.apply_stratagem_cp_cost(rapid_ingress, target_unit=bearer)

        self.assertEqual(int(preview.get("cost", 99)), 0)
        self.assertTrue(any("Beacon Angelis" in str(reason) for reason in list(preview.get("reasons", []) or [])))
        self.assertEqual(int(applied.get("cost", 99)), 0)

    def test_multiple_orbital_comms_arrays_only_roll_once(self):
        impulsor_a = _make_unit(
            "Impulsor A",
            abilities=[{"name": "Orbital Comms Array (Aura)", "description": ORBITAL_COMMS_ARRAY_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        impulsor_b = _make_unit(
            "Impulsor B",
            abilities=[{"name": "Orbital Comms Array (Aura)", "description": ORBITAL_COMMS_ARRAY_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Target Unit",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )

        impulsor_a.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        impulsor_b.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)

        player, _army = _make_player([impulsor_a, impulsor_b, target])
        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(target) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6) as mocked_roll:
            spent = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(spent)
        self.assertEqual(mocked_roll.call_count, 1)
        self.assertEqual(int(player.command_points or 0), 2)

    def test_multiple_orbital_comms_arrays_do_not_allow_second_failed_roll(self):
        impulsor_a = _make_unit(
            "Impulsor A",
            abilities=[{"name": "Orbital Comms Array (Aura)", "description": ORBITAL_COMMS_ARRAY_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        impulsor_b = _make_unit(
            "Impulsor B",
            abilities=[{"name": "Orbital Comms Array (Aura)", "description": ORBITAL_COMMS_ARRAY_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Target Unit",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )

        impulsor_a.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        impulsor_b.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)

        player, _army = _make_player([impulsor_a, impulsor_b, target])
        player.command_points = 2
        player._pending_stratagem_target_unit_id = str(get_entity_id(target) or "")
        player._pending_stratagem_name = "Rapid Fire"

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 6]) as mocked_roll:
            spent = bool(player.spend_command_points(1, reason="Stratagem: Rapid Fire", source="stratagem"))

        self.assertTrue(spent)
        self.assertEqual(mocked_roll.call_count, 1)
        self.assertEqual(int(player.command_points or 0), 1)

    def test_multiple_astartes_banners_stack(self):
        bodyguard = _make_unit(
            "Sternguard",
            keywords=["INFANTRY", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
            objective_control=1,
        )
        ancient_a = _make_unit(
            "Ancient A",
            abilities=[{"name": "Astartes Banner", "description": ASTARTES_BANNER_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["CHARACTER", "ANCIENT", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        ancient_b = _make_unit(
            "Ancient B",
            abilities=[{"name": "Astartes Banner", "description": ASTARTES_BANNER_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["CHARACTER", "ANCIENT", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )

        ancient_a.attached_to = bodyguard
        ancient_b.attached_to = bodyguard
        bodyguard.attached_leaders = [ancient_a, ancient_b]

        effective_oc = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "objective_control") or 0)

        self.assertEqual(effective_oc, 3)

    def test_firing_deck_does_not_gain_attached_leader_weapon_bonuses(self):
        transport = _make_unit(
            "Impulsor",
            abilities=[{"name": "Firing Deck 1", "description": "Firing Deck 1", "type": "Datasheet", "parameter": ""}],
            keywords=["VEHICLE", "TRANSPORT", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        lieutenant = _make_unit(
            "Lieutenant",
            abilities=[{"name": "Tactical Precision", "description": TACTICAL_PRECISION_TEXT, "type": "Datasheet", "parameter": ""}],
            keywords=["CHARACTER", "INFANTRY", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )

        lieutenant.attached_to = bodyguard
        bodyguard.attached_leaders = [lieutenant]
        bodyguard.embarked_in = transport
        lieutenant.embarked_in = transport

        rifle = Wargear(
            {
                "name": "Bolt Rifle",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        bodyguard.models[0].wargear.append(rifle)
        rifle_profile = rifle.profiles["default"]

        attack_context = {"_aura_attack_mods": _aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            bodyguard_hit = rifle_profile._hit_target_with_tracking(enemy, bodyguard.models[0], attack_context)

        self.assertIn("Lethal Hits", list(bodyguard_hit.get("special_effects", []) or []))

        transport.apply_firing_deck_virtual_wargear(
            [{"model": bodyguard.models[0], "wargear": rifle, "profile": rifle_profile, "profile_name": "default"}]
        )
        virtual_wargear = transport.models[0].wargear[-1]
        virtual_profile = virtual_wargear.profiles["default"]

        attack_context = {"_aura_attack_mods": _aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            transport_hit = virtual_profile._hit_target_with_tracking(enemy, transport.models[0], attack_context)

        self.assertNotIn("Lethal Hits", list(transport_hit.get("special_effects", []) or []))

    def test_master_of_battle_backup_target_activates_after_attacking_unit_resolves(self):
        attacker = _make_unit(
            "Aggressor Squad",
            keywords=["INFANTRY", "ADEPTUS ASTARTES"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        primary_target = _make_unit(
            "Primary Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        backup_target = _make_unit(
            "Backup Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )

        player, army = _make_player([attacker])
        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr
        mgr.set_target(primary_target, queue_followups=False)
        mgr.set_backup_target(backup_target)
        game = _GameStub(enemies=[primary_target, backup_target], units=[attacker, primary_target, backup_target], player=player)

        changed = mgr.on_oath_target_destroyed(primary_target, game=game, player=player, destroyed_by_unit=attacker)

        self.assertTrue(bool(changed))
        self.assertFalse(mgr.can_reroll_hit(attacker, backup_target))
        self.assertEqual(str(mgr.oathOfMomentPendingPromotionAttackerUnitId or ""), str(get_entity_id(attacker) or ""))

        activated = mgr.on_attacking_unit_resolved(attacker, game=game, player=player)

        self.assertTrue(bool(activated))
        self.assertTrue(mgr.can_reroll_hit(attacker, backup_target))
        self.assertEqual(str(mgr.oathOfMomentTargetUnitId or ""), str(get_entity_id(backup_target) or ""))


if __name__ == "__main__":
    unittest.main()
