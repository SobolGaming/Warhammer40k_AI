from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET, DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        movement: str = "10",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": leadership,
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Orks",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    movement: str = "10",
    toughness: str = "5",
    wounds: str = "4",
    leadership: str = "7",
) -> Unit:
    return Unit(
        MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
        )
    )


def build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[ork_player, enemy_player])
    game.turn = 1
    game.current_player_index = 0
    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    return game, ork_player, enemy_player, ork_army, enemy_army


def apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


def set_unit_location(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def register_units_on_map(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def set_phase(game: Game, *, phase_name: str, current_player_index: int, active_player: Player) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def find_quarry_request(game: Game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability or ""):
            return request
    return None


def find_battleshock_clear_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET:
            return request
    return None


def option_for_target(request, target_unit: Unit):
    target_id = str(get_entity_id(target_unit) or "")
    return next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((option.payload or {}).get("target_unit_id", "") or (option.payload or {}).get("unit_id", "") or "") == target_id
    )


def alive_wounds(unit: Unit) -> int:
    total = 0
    for model in list(getattr(unit, "models", []) or []):
        is_alive_attr = getattr(model, "is_alive", True)
        is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
        if not is_alive:
            continue
        total += int(getattr(model, "wounds", 0) or 0)
    return int(total)


def simple_melee_profile(name: str = "Test Choppa", *, skill: str = "4+", strength: str = "4") -> WargearProfile:
    parent_wargear = SimpleNamespace(
        name=name,
        is_melee=lambda: True,
        is_ranged=lambda: False,
        is_pistol=lambda: False,
    )
    return WargearProfile(
        name,
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent_wargear,
    )


def simple_ranged_profile(name: str = "Test Shoota", *, skill: str = "5+", strength: str = "4") -> WargearProfile:
    parent_wargear = SimpleNamespace(
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
        is_pistol=lambda: False,
        is_heavy=lambda: False,
    )
    return WargearProfile(
        name,
        {
            "range": "24",
            "A": "1",
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent_wargear,
    )
