from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _RectMissionZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)
        self.vertices = [
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        ]

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max

    def contains_circular_base(self, x: float, y: float, radius: float) -> bool:
        return (
            self.x_min <= float(x) - float(radius)
            and float(x) + float(radius) <= self.x_max
            and self.y_min <= float(y) - float(radius)
            and float(y) + float(radius) <= self.y_max
        )


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        cost: int = 100,
        faction_name: str | None = None,
    ) -> None:
        slug = str(name or "unit").lower().replace(" ", "_").replace("'", "")
        self.id = f"mock_{slug}"
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        faction_kw = [str(value or "").upper() for value in list(self.faction_keywords or [])]
        if faction_name is None:
            faction_name = "Orks" if "ORKS" in faction_kw else "Enemy"
        self.faction_data = {"name": faction_name}
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "2",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    cost: int = 100,
    faction_name: str | None = None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            cost=cost,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float, spacing: float = 1.5) -> None:
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * float(spacing), float(y), 0.0, 0.0)


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment_type=detachment)
    ork_army.faction_id = "ORK"
    ork_army.points_limit = 2000
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    enemy_army.points_limit = 2000

    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.attacker_index = 0
    game.defender_index = 1

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    game.map.units = list(ork_units or []) + [unit for unit in list(enemy_units or []) if getattr(unit, "deployed", False)]
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army


def _configure_deployment_zones(game: Game, *, player: Player, enemy_player: Player) -> None:
    width = float(getattr(game.battlefield, "width", 60.0) or 60.0)
    height = float(getattr(game.battlefield, "height", 44.0) or 44.0)
    own_zone = _RectMissionZone(0.0, min(24.0, width / 2.0), 0.0, height)
    enemy_zone = _RectMissionZone(max(width - 24.0, width / 2.0), width, 0.0, height)
    game.deployment_zones = {
        player.id: {"mission_zones": [own_zone]},
        enemy_player.id: {"mission_zones": [enemy_zone]},
    }


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, detachment: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="ORK",
        detachment=detachment,
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(request, "player_id", "") or "") != str(player_id):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability_name", "") or "") != str(ability_name):
            continue
        return request
    return None


def _find_redeploy_option_id(request, *, target_unit: Unit, action: str) -> str:
    target_id = str(get_entity_id(target_unit) or "")
    action_norm = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") != target_id:
            continue
        if str(payload.get("redeploy_action", "") or "").strip().lower() != action_norm:
            continue
        return str(getattr(option, "option_id", "") or "")
    return ""


def test_orks_redeploy_enhancement_descriptors_and_runtime_specs_registered():
    expected = {
        "000010712005": ("Razgit's Magik Map", "redeploy_units", ("ORKS", "INFANTRY")),
        "000009795004": ("Mork's Kunnin'", "redeploy_units", ("ORKS",)),
    }
    for enhancement_id, (name, effect, filters) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect
        assert tuple((getattr(descriptor, "effect_params", {}) or {}).get("redeploy_filters", ()) or ()) == filters

    razgit_army = Army("Orks", detachment_type="Freebooter Krew")
    razgit_army.faction_id = "ORK"
    razgit_bearer = _make_unit(
        "Freebooter Boss",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    razgit_army.add_unit(razgit_bearer)
    _apply_enhancement(
        razgit_bearer,
        enhancement_id="000010712005",
        enhancement_name="Razgit's Magik Map",
        detachment="Freebooter Krew",
    )
    has_redeploy, count, can_place_in_reserves = razgit_bearer.has_redeploy()
    assert has_redeploy is True
    assert int(count) == 3
    assert can_place_in_reserves is True
    razgit_cache = dict(getattr(razgit_bearer, "_ability_cache", {}) or {})
    assert list(razgit_cache.get("redeploy_filters", []) or []) == ["ORKS", "INFANTRY"]
    assert bool(razgit_cache.get("redeploy_strategic_reserves_ignore_current_unit_count_limit", False))

    mork_army = Army("Orks", detachment_type="Taktikal Brigade")
    mork_army.faction_id = "ORK"
    mork_bearer = _make_unit(
        "Taktikal Boss",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    mork_army.add_unit(mork_bearer)
    _apply_enhancement(
        mork_bearer,
        enhancement_id="000009795004",
        enhancement_name="Mork's Kunnin'",
        detachment="Taktikal Brigade",
    )
    has_redeploy, count, can_place_in_reserves = mork_bearer.has_redeploy()
    assert has_redeploy is True
    assert int(count) == 3
    assert can_place_in_reserves is True
    mork_cache = dict(getattr(mork_bearer, "_ability_cache", {}) or {})
    assert list(mork_cache.get("redeploy_filters", []) or []) == ["ORKS"]
    assert bool(mork_cache.get("redeploy_strategic_reserves_ignore_current_unit_count_limit", False))


def test_validate_redeploy_to_strategic_reserves_can_ignore_current_unit_cap_for_selected_roots():
    reserve_one = _make_unit("Reserve One", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=100)
    reserve_two = _make_unit("Reserve Two", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=100)
    target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=100)
    deployed = _make_unit("Deployed", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=100)
    army = Army("Orks", detachment_type="Freebooter Krew")
    army.faction_id = "ORK"
    army.points_limit = 2000
    for unit in (reserve_one, reserve_two, target, deployed):
        army.add_unit(unit)

    reserve_one.reserve_status = "strategic_reserves"
    reserve_two.reserve_status = "strategic_reserves"

    invalid = army.validate_redeploy_to_strategic_reserves(target)
    assert bool(invalid.get("valid", False)) is False
    assert any("Too many units in reserves" in str(error) for error in list(invalid.get("errors", []) or []))

    ignored = army.validate_redeploy_to_strategic_reserves(
        target,
        ignore_unit_cap_root_ids={str(get_entity_id(target) or "")},
    )
    assert bool(ignored.get("valid", False)) is True
    assert list(ignored.get("ignored_unit_cap_root_ids", []) or []) == [str(get_entity_id(target) or "")]


def test_razgits_magik_map_filters_infantry_orders_targets_and_scopes_strategic_reserves_exception():
    bearer = _make_unit("Razgit", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"], cost=50)
    infantry_a = _make_unit("Boyz Alpha", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], cost=50)
    infantry_b = _make_unit("Boyz Beta", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], cost=50)
    infantry_c = _make_unit("Boyz Gamma", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], cost=50)
    infantry_d = _make_unit("Boyz Delta", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"], cost=50)
    trukk = _make_unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"], cost=50)
    reserve_units = [
        _make_unit(f"Reserve {index}", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=50)
        for index in range(1, 6)
    ]
    dummy_enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"], faction_name="Enemy")

    for x_pos, unit in enumerate([bearer, infantry_a, infantry_b, infantry_c, infantry_d, trukk], start=1):
        _set_unit_location(unit, x=float(x_pos) * 3.0, y=10.0)
    for unit in reserve_units:
        unit.reserve_status = "strategic_reserves"
        unit.deployed = False

    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[bearer, infantry_a, infantry_b, infantry_c, infantry_d, trukk] + reserve_units,
        enemy_units=[dummy_enemy],
    )
    _apply_enhancement(
        bearer,
        enhancement_id="000010712005",
        enhancement_name="Razgit's Magik Map",
        detachment="Freebooter Krew",
    )

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, player_id=ork_player.id, ability_name="Razgit's Magik Map")
    assert request is not None

    battlefield_target_ids = [
        str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for option in list(getattr(request, "options", []) or [])
        if str((dict(getattr(option, "payload", {}) or {}).get("redeploy_action", "") or "").lower()) == "battlefield"
    ]
    expected_ids = sorted(
        [
            str(get_entity_id(bearer) or ""),
            str(get_entity_id(infantry_a) or ""),
            str(get_entity_id(infantry_b) or ""),
            str(get_entity_id(infantry_c) or ""),
            str(get_entity_id(infantry_d) or ""),
        ]
    )
    assert battlefield_target_ids == expected_ids
    assert str(get_entity_id(trukk) or "") not in battlefield_target_ids

    for selected in (infantry_a, infantry_b, infantry_c):
        option_id = _find_redeploy_option_id(request, target_unit=selected, action="strategic_reserves")
        assert option_id
        result = resolve_decision_command(game, request, option_id, player_id=ork_player.id)
        assert bool(getattr(result, "ok", False))
        request = _find_redeploy_request(game, player_id=ork_player.id, ability_name="Razgit's Magik Map")

    assert request is None
    for selected in (infantry_a, infantry_b, infantry_c):
        assert selected.is_in_strategic_reserves()
        assert selected not in list(getattr(game.map, "units", []) or [])
    assert infantry_d.reserve_status == "deployed"
    assert infantry_d in list(getattr(game.map, "units", []) or [])

    after_validation = ork_army.validate_reserves_decisions(ork_army.get_current_reserves_decisions())
    assert bool(after_validation.get("valid", False)) is False
    assert any("Too many units in reserves" in str(error) for error in list(after_validation.get("errors", []) or []))


def test_morks_kunnin_redeploy_to_strategic_reserves_propagates_transport_group():
    bearer = _make_unit("Taktikal Boss", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"])
    transport = _make_unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    passenger = _make_unit("Boyz Mob", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    leader = _make_unit("Warboss", keywords=["INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
    other_unit = _make_unit("Lootas", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    dummy_enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"], faction_name="Enemy")

    _set_unit_location(bearer, x=4.0, y=10.0)
    _set_unit_location(transport, x=10.0, y=10.0)
    _set_unit_location(other_unit, x=16.0, y=10.0)
    passenger.embarked_in = transport
    leader.attached_to = passenger
    leader.embarked_in = transport
    passenger.attached_leaders = [leader]
    transport.transport_passengers = [passenger]

    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[bearer, transport, passenger, leader, other_unit],
        enemy_units=[dummy_enemy],
    )
    _apply_enhancement(
        bearer,
        enhancement_id="000009795004",
        enhancement_name="Mork's Kunnin'",
        detachment="Taktikal Brigade",
    )

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, player_id=ork_player.id, ability_name="Mork's Kunnin'")
    assert request is not None
    target_ids = {
        str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for option in list(getattr(request, "options", []) or [])
        if str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    assert str(get_entity_id(transport) or "") in target_ids
    assert str(get_entity_id(passenger) or "") not in target_ids
    assert str(get_entity_id(leader) or "") not in target_ids

    option_id = _find_redeploy_option_id(request, target_unit=transport, action="strategic_reserves")
    assert option_id
    result = resolve_decision_command(game, request, option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False))

    assert transport.is_in_strategic_reserves()
    assert passenger.is_in_strategic_reserves()
    assert leader.is_in_strategic_reserves()
    assert transport not in list(getattr(game.map, "units", []) or [])
    assert passenger not in list(getattr(game.map, "units", []) or [])
    assert leader not in list(getattr(game.map, "units", []) or [])
    assert passenger.embarked_in is transport
    assert leader.attached_to is passenger


def test_razgits_magik_map_battlefield_redeploy_rejects_illegal_deployment_position():
    bearer = _make_unit("Razgit", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"])
    infantry = _make_unit("Boyz Mob", keywords=["INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    dummy_enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"], faction_name="Enemy")
    _set_unit_location(bearer, x=4.0, y=10.0)
    _set_unit_location(infantry, x=10.0, y=10.0)

    game, ork_player, enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[bearer, infantry],
        enemy_units=[dummy_enemy],
    )
    _configure_deployment_zones(game, player=ork_player, enemy_player=enemy_player)
    _apply_enhancement(
        bearer,
        enhancement_id="000010712005",
        enhancement_name="Razgit's Magik Map",
        detachment="Freebooter Krew",
    )

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, player_id=ork_player.id, ability_name="Razgit's Magik Map")
    assert request is not None

    option_id = _find_redeploy_option_id(request, target_unit=infantry, action="battlefield")
    assert option_id
    result = resolve_decision_command(game, request, option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False))

    pending = list(game.decision_queue.list() or [])
    move_request = next(
        request_obj
        for request_obj in pending
        if str(getattr(request_obj, "decision_type", "") or "") == DECISION_MOVE_UNIT
    )
    confirm_option_id = str(getattr(move_request.options[0], "option_id", "") or "")
    invalid_positions = [
        {
            "model_id": str(get_entity_id(model) or ""),
            "position": [45.0, 10.0, 0.0],
            "facing": 0.0,
        }
        for model in list(getattr(infantry, "models", []) or [])
    ]
    invalid_move = resolve_decision_command(
        game,
        move_request,
        confirm_option_id,
        result_payload={"model_positions": invalid_positions},
        player_id=ork_player.id,
    )
    assert bool(getattr(invalid_move, "ok", False)) is False
