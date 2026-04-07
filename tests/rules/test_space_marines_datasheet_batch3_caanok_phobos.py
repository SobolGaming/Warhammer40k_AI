from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            model_count=model_count,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.attacker_index = 0
    game.defender_index = 1
    game.current_player_index = 0
    game.current_player_idx = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)


def _find_request(game: Game, *, ability: str, ability_name: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != ability:
            continue
        if ability_name is not None and str(ctx.get("ability_name", "") or "") != ability_name:
            continue
        return req
    return None


def _option_for_unit(request, unit: Unit):
    target_id = str(get_entity_id(unit) or "")
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        selected_unit_id = str(
            payload.get("selected_unit_id", "")
            or payload.get("target_unit_id", "")
            or payload.get("unit_id", "")
            or ""
        )
        if selected_unit_id == target_id:
            return opt
    return None


_COLD_AND_CALCULATING = _ability(
    "Cold and Calculating",
    "Each time a model in this model’s unit makes an attack that targets a MONSTER or VEHICLE unit, that attack has the [LETHAL HITS] ability. Each time a model in this model’s unit makes an attack that targets any other unit, that attack has the [SUSTAINED HITS 1] ability.",
)

_CEREBREX_LOGIC_ENGINE = _ability(
    "Cerebrex Logic Engine",
    'At the start of the Declare Battle Formations step, you can select one Adeptus Astartes Infantry unit from your army. Until the end of the battle, that unit gains the Scouts 6" ability. After both players have deployed their armies, you can select one ADEPTUS ASTARTES unit from your army and redeploy it. When doing so, you can set that unit up in Strategic Reserves if you wish, regardless of how many units are already in Strategic Reserves.',
)

_MASTER_OF_DECEIT = _ability(
    "Master of Deceit",
    "After both players have deployed their armies, if your army includes one or more models with this ability, you can select up to three friendly Adeptus Astartes Infantry units and redeploy all of those units. When doing so, any of those units can be placed into Strategic Reserves, regardless of how many units are already in Strategic Reserves.",
)


def test_cerebrex_logic_engine_queues_declare_selection_and_selected_unit_gains_scouts() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        "sm-bodyguard",
        model_count=5,
        keywords=["INFANTRY"],
    )
    caanok = _make_unit(
        "Caanok Var",
        "000004166",
        abilities=[_CEREBREX_LOGIC_ENGINE],
        keywords=["CHARACTER", "INFANTRY"],
        attached_to=[intercessors.get_datasheet_id()],
    )
    ballistus = _make_unit(
        "Ballistus Dreadnought",
        "sm-vehicle",
        keywords=["VEHICLE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-ds",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (intercessors, caanok, ballistus):
        sm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    for idx, unit in enumerate((intercessors, caanok, ballistus, enemy)):
        _deploy(unit, float(idx * 4), 0.0)
    game.map.units = [intercessors, caanok, ballistus, enemy]
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()

    request = _find_request(game, ability="declare_selected_unit_gain_scouts", ability_name="Cerebrex Logic Engine")
    assert request is not None

    candidate_ids = {
        str(v or "")
        for v in list((request.context or {}).get("candidate_unit_ids", []) or [])
        if str(v or "")
    }
    assert candidate_ids == {
        str(get_entity_id(intercessors) or ""),
        str(get_entity_id(caanok) or ""),
    }
    assert str(getattr(request, "player_id", "") or "") == str(sm_player.id or "")

    option = _option_for_unit(request, intercessors)
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    has_scout, scout_distance = intercessors.has_scout()
    assert bool(has_scout) is True
    assert float(scout_distance or 0.0) == 6.0

    caanok.attach_to_unit(intercessors)
    attached_has_scout, attached_scout_distance = intercessors.has_scout()
    assert bool(attached_has_scout) is True
    assert float(attached_scout_distance or 0.0) == 6.0


def test_cold_and_calculating_grants_target_conditional_attack_keywords() -> None:
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    bodyguard = _make_unit(
        "Intercessor Squad",
        "sm-bodyguard",
        model_count=5,
        keywords=["INFANTRY"],
    )
    caanok = _make_unit(
        "Caanok Var",
        "000004166",
        abilities=[_COLD_AND_CALCULATING],
        keywords=["CHARACTER", "INFANTRY"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    monster = _make_unit(
        "Monster Target",
        "enemy-monster",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
    )
    infantry = _make_unit(
        "Infantry Target",
        "enemy-infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (bodyguard, caanok):
        sm_army.add_unit(unit)
    for unit in (monster, infantry):
        enemy_army.add_unit(unit)
    caanok.attach_to_unit(bodyguard)
    game.map.units = [bodyguard, caanok, monster, infantry]
    game.rebuild_entity_registry()

    monster_bonus = bodyguard.get_attack_keyword_bonuses(
        target=monster,
        attack_type="ranged",
        model=bodyguard.models[0],
    )
    assert bool(monster_bonus.get("lethal_hits", False)) is True
    assert int(monster_bonus.get("sustained_hits_value", 0) or 0) == 0

    infantry_bonus = bodyguard.get_attack_keyword_bonuses(
        target=infantry,
        attack_type="melee",
        model=bodyguard.models[0],
    )
    assert bool(infantry_bonus.get("lethal_hits", False)) is False
    assert int(infantry_bonus.get("sustained_hits_value", 0) or 0) == 1


def test_cerebrex_logic_engine_redeploy_parses_adeptus_astartes_single_unit() -> None:
    caanok = _make_unit(
        "Caanok Var",
        "000004166",
        abilities=[_CEREBREX_LOGIC_ENGINE],
        keywords=["CHARACTER", "INFANTRY"],
    )

    has_redeploy, count, can_place_in_reserves = caanok.has_redeploy()

    assert bool(has_redeploy) is True
    assert int(count) == 1
    assert bool(can_place_in_reserves) is True
    cache = dict(getattr(caanok, "_ability_cache", {}) or {})
    assert list(cache.get("redeploy_filters", []) or []) == ["ADEPTUS ASTARTES"]


def test_master_of_deceit_redeploy_filters_to_adeptus_astartes_infantry_and_is_army_once() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    phobos_a = _make_unit(
        "Captain In Phobos Armour A",
        "000002701",
        abilities=[_MASTER_OF_DECEIT],
        keywords=["CHARACTER", "INFANTRY"],
    )
    phobos_b = _make_unit(
        "Captain In Phobos Armour B",
        "000002701-b",
        abilities=[_MASTER_OF_DECEIT],
        keywords=["CHARACTER", "INFANTRY"],
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        "sm-intercessors",
        model_count=5,
        keywords=["INFANTRY"],
    )
    scouts = _make_unit(
        "Scout Squad",
        "sm-scouts",
        model_count=5,
        keywords=["INFANTRY"],
    )
    dreadnought = _make_unit(
        "Ballistus Dreadnought",
        "sm-dread",
        keywords=["VEHICLE"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-ds",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (phobos_a, phobos_b, intercessors, scouts, dreadnought):
        sm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    for idx, unit in enumerate((phobos_a, phobos_b, intercessors, scouts, dreadnought, enemy)):
        _deploy(unit, float(idx * 4), 0.0)
    game.map.units = [phobos_a, phobos_b, intercessors, scouts, dreadnought, enemy]
    game.rebuild_entity_registry()

    has_redeploy, count, can_place_in_reserves = phobos_a.has_redeploy()
    assert bool(has_redeploy) is True
    assert int(count) == 3
    assert bool(can_place_in_reserves) is True
    cache = dict(getattr(phobos_a, "_ability_cache", {}) or {})
    assert list(cache.get("redeploy_filters", []) or []) == ["ADEPTUS ASTARTES", "INFANTRY"]
    assert bool(cache.get("redeploy_army_once_per_ability", False)) is True

    game.execute_redeploy_units_phase()
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "aeldari_guileful_strategist"
        and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Master of Deceit"
        and str(getattr(req, "player_id", "") or "") == str(sm_player.id)
    ]
    assert len(requests) == 1
    request = requests[0]

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    assert target_ids == {
        str(get_entity_id(phobos_a) or ""),
        str(get_entity_id(phobos_b) or ""),
        str(get_entity_id(intercessors) or ""),
        str(get_entity_id(scouts) or ""),
    }
    assert str(get_entity_id(dreadnought) or "") not in target_ids

    for target_id in list(target_ids):
        actions = {
            str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == target_id
        }
        assert "battlefield" in actions
        assert "strategic_reserves" in actions
