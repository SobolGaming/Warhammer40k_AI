from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
        save: int = 3,
    ) -> None:
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
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
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
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _mock_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, current_player_index: int = 0):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = int(current_player_index)
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != decision_type:
            continue
        if ability is None:
            return req
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == ability:
            return req
    return None


def test_land_raider_crusader_legacy_of_jerulas_marks_enemy_for_disembarked_reroll_ones_until_end_of_turn():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game(current_player_index=0)
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    crusader = _actual_unit("Land Raider Crusader", datasheet_id="000004139")
    passenger = _mock_unit(
        "Passenger Squad",
        keywords=["ADEPTUS ASTARTES", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=5,
    )
    enemy = _mock_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)

    sm_army.add_unit(crusader)
    sm_army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _deploy(crusader, 0.0, 0.0, spacing=0.0)
    _deploy(passenger, 3.0, 0.0)
    _deploy(enemy, 10.0, 0.0, spacing=0.0)
    _register_units(game, crusader, passenger, enemy)

    passenger.round_state.disembarked_from_transport_id = str(get_entity_id(crusader) or "")

    game._on_unit_shooting_resolved_post_shoot_disembark_hit_reroll(
        attacker_unit=crusader,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {crusader.models[0]}},
    )
    game._on_unit_shooting_resolved_post_shoot_disembark_wound_reroll(
        attacker_unit=crusader,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {crusader.models[0]}},
    )

    hit_req = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_disembark_hit_reroll")
    wound_req = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_disembark_wound_reroll")
    assert hit_req is not None
    assert wound_req is not None

    enemy_id = str(get_entity_id(enemy) or "")
    hit_option = next(
        opt for opt in list(hit_req.options or []) if str((opt.payload or {}).get("target_unit_id", "") or "") == enemy_id
    )
    wound_option = next(
        opt for opt in list(wound_req.options or []) if str((opt.payload or {}).get("target_unit_id", "") or "") == enemy_id
    )
    hit_result = resolve_decision_command(game, hit_req, hit_option.option_id, player_id=sm_player.id)
    wound_result = resolve_decision_command(game, wound_req, wound_option.option_id, player_id=sm_player.id)
    assert bool(getattr(hit_result, "ok", False)) is True
    assert bool(getattr(wound_result, "ok", False)) is True

    game.phase = BattleRoundPhases.FIGHT_PHASE
    passenger_model = passenger.models[0]

    hit_mods = passenger.get_model_hit_reroll_modifiers(passenger_model, attack_type="melee", target=enemy)
    wound_mods = passenger.get_unit_wound_reroll_modifiers("melee", target=enemy, attacker_model=passenger_model)

    assert 1 in tuple(hit_mods.get("reroll_hit_values", ()) or ())
    assert 1 in tuple(wound_mods.get("reroll_wound_values", ()) or ())
    hit_reasons = " ".join(str(value) for value in list(hit_mods.get("reroll_hit_reasons", ()) or []))
    wound_reasons = " ".join(str(value) for value in list(wound_mods.get("reroll_wound_reasons", ()) or []))
    assert "Legacy of Jerulas" in hit_reasons
    assert "Legacy of Jerulas" in wound_reasons


def test_land_speeder_vengeance_storm_of_vengeance_queues_reactive_shooting_after_nearby_friendly_unit_destroyed():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game(current_player_index=1)
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    vengeance = _actual_unit("Land Speeder Vengeance", datasheet_id="000000242")
    friendly = _mock_unit(
        "Friendly Squad",
        keywords=["ADEPTUS ASTARTES", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=3,
    )
    enemy_attacker = _mock_unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)
    bolter = Wargear(
        {
            "name": "Test Bolter",
            "type": "ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    enemy_gun = Wargear(
        {
            "name": "Enemy Gun",
            "type": "ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    vengeance.models[0].wargear.append(bolter)
    enemy_attacker.models[0].wargear.append(enemy_gun)

    sm_army.add_unit(vengeance)
    sm_army.add_unit(friendly)
    enemy_army.add_unit(enemy_attacker)
    _deploy(vengeance, 0.0, 0.0, spacing=0.0)
    _deploy(friendly, 4.0, 0.0, spacing=0.0)
    _deploy(enemy_attacker, 12.0, 0.0, spacing=0.0)
    _register_units(game, vengeance, friendly, enemy_attacker)

    game._on_unit_destroyed_storm_of_vengeance(
        unit=friendly,
        last_model=friendly.models[0],
        destroyed_by_unit=enemy_attacker,
        game_map=game.map,
    )
    game._on_unit_shooting_resolved_storm_of_vengeance(attacker_unit=enemy_attacker)

    req = _find_request(game, DECISION_DECLARE_SHOTS)
    assert req is not None
    ctx = dict(getattr(req, "context", {}) or {})
    assert bool(ctx.get("storm_of_vengeance_flow", False)) is True
    assert str(ctx.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")
    assert str(ctx.get("storm_of_vengeance_unit_id", "") or "") == str(get_entity_id(vengeance) or "")
    assert str(ctx.get("storm_of_vengeance_enemy_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")


def test_lemartes_guardian_of_the_lost_reduces_allocated_damage_while_leading():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game(current_player_index=0)
    game.phase = BattleRoundPhases.FIGHT_PHASE

    lemartes = _actual_unit("Lemartes", datasheet_id="000000164")
    bodyguard = _mock_unit(
        "Bodyguard",
        keywords=["ADEPTUS ASTARTES", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=5,
    )
    enemy_attacker = _mock_unit("Enemy Bruiser", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)
    crusher = Wargear(
        {
            "name": "Crusher",
            "type": "melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-1",
            "D": "3",
            "description": "",
        }
    )
    enemy_attacker.models[0].wargear.append(crusher)

    lemartes.attached_to = bodyguard
    bodyguard.attached_leaders = [lemartes]

    sm_army.add_unit(lemartes)
    sm_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy_attacker)
    _deploy(lemartes, 0.0, 0.0, spacing=0.0)
    _deploy(bodyguard, 0.0, 0.5, spacing=0.0)
    _deploy(enemy_attacker, 1.0, 0.0, spacing=0.0)
    _register_units(game, lemartes, bodyguard, enemy_attacker)

    damage = crusher.profiles["default"]._damage_target_with_tracking(
        bodyguard.models[0],
        enemy_attacker.models[0],
        {"mortal_wound": False},
    )

    assert int(damage.get("damage_applied", 0) or 0) == 2
    effects = " ".join(str(value) for value in list(damage.get("special_effects", []) or []))
    assert "Guardian of the Lost" in effects
