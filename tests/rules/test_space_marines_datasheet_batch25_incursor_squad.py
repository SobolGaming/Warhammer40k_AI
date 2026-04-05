from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


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
        crit_hit_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
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
                "W": "2",
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _actual_unit(name: str, *, datasheet_id: str | None = None) -> Unit:
    kwargs = {"faction_id": "SM"}
    if datasheet_id is not None:
        kwargs["datasheet_id"] = datasheet_id
    unit = Unit(_WAHA.get_datasheet(name, **kwargs))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _find_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability_key):
            return request
    return None


def test_incursor_squad_multi_spectrum_array_marks_target_for_adeptus_astartes_hit_bonus():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    incursors = _actual_unit("Incursor Squad", datasheet_id="000001159")
    shooter = _mock_unit("Shooter", faction_keywords=["ADEPTUS ASTARTES"])
    target = _mock_unit("Marked Target")
    other_target = _mock_unit("Other Target")

    shooter_model = _make_model("Shooter", shooter)
    shooter.models = [shooter_model]
    target.models = [_make_model("Target Model", target)]
    other_target.models = [_make_model("Other Target Model", other_target)]

    sm_army.units = [incursors, shooter]
    enemy_army.units = [target, other_target]
    for unit in [incursors, shooter]:
        unit.set_parent_army(sm_army)
    for unit in [target, other_target]:
        unit.set_parent_army(enemy_army)
    game.rebuild_entity_registry()

    specs = incursors.unit_post_shoot_keyword_hit_bonus_specs()
    assert len(specs) == 1
    assert str(specs[0].get("keyword", "") or "").upper() == "ADEPTUS ASTARTES"
    assert int(specs[0].get("bonus", 0) or 0) == 1

    game._on_unit_shooting_resolved_post_shoot_keyword_hit_bonus(
        attacker_unit=incursors,
        hits_by_target={target: 1, other_target: 0},
    )

    request = _find_request(game, "post_shoot_keyword_hit_bonus")
    assert request is not None
    resolve_decision_command(game, request, request.options[0].option_id, player_id=sm_player.id)

    profile = Wargear(
        {
            "name": "Bolt carbine",
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]

    marked_hit = profile._hit_target_with_tracking(target, shooter_model, {"_aura_attack_mods": _aura_stub()})
    other_hit = profile._hit_target_with_tracking(other_target, shooter_model, {"_aura_attack_mods": _aura_stub()})

    assert any("Multi-spectrum Array" in str(mod or "") for mod in list(marked_hit.get("modifiers", []) or []))
    assert not any("Multi-spectrum Array" in str(mod or "") for mod in list(other_hit.get("modifiers", []) or []))
