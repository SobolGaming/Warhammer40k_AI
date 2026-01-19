import pytest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.rules.cabal_of_sorcerers import (
    CabalOfSorcerersManager,
    RITUAL_DESTINYS_RUIN,
    RITUAL_TWIST_OF_FATE,
    RITUAL_TEMPORAL_SURGE,
)
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.event_bus import get_recent_actions, get_recent_dice


class _UnitStub:
    def __init__(self, name: str, *, keywords=None, abilities=None, army=None):
        self.name = name
        self._id = name
        self.keywords = list(keywords or [])
        self.possible_abilities = list(abilities or [])
        self.models = []
        self.special_rules = {}
        self.deployed = True
        self.reserve_status = "deployed"
        self._army = army
        self.mortals = 0

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, kw: str) -> bool:
        kw_l = str(kw or "").strip().lower()
        return kw_l in [str(k or "").strip().lower() for k in self.keywords]

    def is_alive(self) -> bool:
        return True

    def has_lone_operative(self) -> bool:
        return False

    def _apply_mortal_wounds_to_unit(self, unit, mortal_wound_amount: int, game_map=None) -> int:
        self.mortals += int(mortal_wound_amount or 0)
        return 0


class _MapStub:
    def __init__(self, *, enemies=None, friendlies=None):
        self._enemies = list(enemies or [])
        self._friendlies = list(friendlies or [])

    def get_enemy_units(self, _unit):
        return list(self._enemies)

    def get_friendly_units(self, _unit):
        return list(self._friendlies)

    def is_within_engagement_range(self, _unit, _enemy):
        return False


class _GameStub:
    def __init__(self, player, game_map):
        self.turn = 1
        self.map = game_map
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")
        self._player = player

    def is_shooting_phase(self):
        return True

    def get_current_player(self):
        return self._player


def _make_army():
    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(faction_id="TS", units=[], player=player, _id="army-ts")
    mgr = CabalOfSorcerersManager(army)
    army.cabal_of_sorcerers = mgr
    return army, player, mgr


def test_cabal_channel_warp_mortals_only_when_channeled():
    army, player, mgr = _make_army()

    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    target = _UnitStub("Enemy", army=SimpleNamespace(faction_id="SM", player=SimpleNamespace(name="P2", id="P2")))

    game_map = _MapStub(enemies=[target], friendlies=[caster])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        res = mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[3, 3],
            channel_decision=False,
        )
    assert res["success"] is True
    assert caster.mortals == 0

    # New manager so the model can attempt again
    mgr = CabalOfSorcerersManager(army)
    army.cabal_of_sorcerers = mgr
    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        res = mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[4, 4],
            channel_decision=True,
            mortal_roll=2,
        )
    assert res["success"] is True
    assert caster.mortals == 2


def test_destinys_ruin_reroll_ones():
    army, player, mgr = _make_army()
    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    target = _UnitStub("Enemy", army=SimpleNamespace(faction_id="SM", player=SimpleNamespace(name="P2", id="P2")))

    game_map = _MapStub(enemies=[target], friendlies=[caster])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[3, 4],
            channel_decision=False,
        )

    attacker_unit = _UnitStub("Attacker", keywords=["THOUSAND SONS"], army=army)
    attacker_unit.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
    attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
    data = {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""}
    profile = Wargear({"name": "Test", "type": "Ranged", **data}).profiles["default"]

    target.has_stealth = lambda: False
    target.has_first_prince_tzeentch_defense = lambda: False

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 4]):
        res = profile._hit_target_with_tracking(target, attacker_model, {})

    assert res.get("reroll") == 4
    assert any("Destiny" in m for m in (res.get("special_effects") or []))


def test_destinys_ruin_full_reroll():
    army, player, mgr = _make_army()
    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    target = _UnitStub("Enemy", army=SimpleNamespace(faction_id="SM", player=SimpleNamespace(name="P2", id="P2")))

    game_map = _MapStub(enemies=[target], friendlies=[caster])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[5, 5],
            channel_decision=False,
        )

    attacker_unit = _UnitStub("Attacker", keywords=["THOUSAND SONS"], army=army)
    attacker_unit.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
    attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
    data = {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""}
    profile = Wargear({"name": "Test", "type": "Ranged", **data}).profiles["default"]

    target.has_stealth = lambda: False
    target.has_first_prince_tzeentch_defense = lambda: False

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 5]):
        res = profile._hit_target_with_tracking(target, attacker_model, {})

    assert res.get("reroll") == 5
    assert any("Destiny" in m for m in (res.get("special_effects") or []))


def test_twist_of_fate_ap_bonus():
    army, player, mgr = _make_army()
    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    target = _UnitStub("Enemy", army=SimpleNamespace(faction_id="SM", player=SimpleNamespace(name="P2", id="P2")))

    game_map = _MapStub(enemies=[target], friendlies=[caster])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_TWIST_OF_FATE.key,
            target_unit=target,
            rolls=[6, 6],
            channel_decision=False,
        )

    attacker_unit = _UnitStub("Attacker", keywords=["THOUSAND SONS"], army=army)
    attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
    data = {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""}
    profile = Wargear({"name": "Test", "type": "Ranged", **data}).profiles["default"]

    assert profile.get_effective_ap(attacker_model, target) == -2


def test_temporal_surge_sets_no_charge():
    army, player, mgr = _make_army()
    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    friendly = _UnitStub("Rubrics", keywords=["THOUSAND SONS"], army=army)
    friendly.models = [SimpleNamespace(id="fm1", is_alive=True, parent_unit=friendly)]

    game_map = _MapStub(enemies=[], friendlies=[caster, friendly])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        res = mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_TEMPORAL_SURGE.key,
            target_unit=friendly,
            rolls=[3, 3],
            channel_decision=False,
        )

    assert res["success"] is True
    assert friendly.special_rules.get("cabal_temporal_surge_no_charge_turn_owner") == player.id


def test_cabal_ritual_logs_outcome():
    army, player, mgr = _make_army()
    caster = _UnitStub("Sorcerer", abilities=["Cabal of Sorcerers"], army=army)
    caster_model = SimpleNamespace(id="m1", is_alive=True, parent_unit=caster)
    caster.models = [caster_model]
    target = _UnitStub("Enemy", army=SimpleNamespace(faction_id="SM", player=SimpleNamespace(name="P2", id="P2")))

    game_map = _MapStub(enemies=[target], friendlies=[caster])
    game = _GameStub(player, game_map)
    player.game = game

    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        mgr.attempt_ritual(
            game,
            caster_model=caster_model,
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[3, 3],
            channel_decision=False,
        )

    actions = get_recent_actions(player, limit=5)
    dice = get_recent_dice(player, limit=5)
    assert actions and "Cabal of Sorcerers" in actions[-1]
    assert dice and "Cabal of Sorcerers" in dice[-1]
