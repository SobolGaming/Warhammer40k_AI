from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


PARASITIC_INFECTION_RULE = (
    "Each time an INFANTRY model is destroyed by an attack made with this model's barbed ovipositor, after this model "
    "has finished making its attacks, you can add one new Ripper Swarms unit to your army consisting of D3 models and "
    "set it up within 3\" of this model. If you do, that RIPPER SWARMS unit can be set up within Engagement Range of "
    "the destroyed model's unit (but not within Engagement Range of any other enemy units)."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        faction_name: str = "Tyranids",
        base_size: str = "32mm",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "4",
                "Sv": "4",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    base_size: str = "32mm",
):
    return Unit(
        _MockDatasheet(
            name,
            model_count=1,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            base_size=base_size,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 1
    game.current_player_index = 0

    tyr_army = Army.with_detachment("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _find_parasitic_pick_point_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "parasitic_infection_spawn":
            continue
        return req
    return None


def _option_by_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


def _barbed_ovipositor_profile():
    return SimpleNamespace(
        name="Barbed Ovipositor",
        parent_wargear=SimpleNamespace(name="Barbed Ovipositor"),
    )


def _wrong_profile():
    return SimpleNamespace(
        name="Clawed Limbs",
        parent_wargear=SimpleNamespace(name="Clawed Limbs"),
    )


def test_model_parasitic_infection_specs_parse():
    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    model = source.models[0]
    specs = source.model_parasitic_infection_specs(model)

    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("source", "") or "") == "Parasitic Infection"
    assert str(spec.get("weapon_name", "") or "") == "barbed ovipositor"
    assert str(spec.get("required_target_keyword", "") or "") == "INFANTRY"
    assert str(spec.get("spawn_unit_name", "") or "") == "Ripper Swarms"
    assert str(spec.get("spawn_model_count_roll", "") or "") == "D3"
    assert int(spec.get("setup_range", 0) or 0) == 3
    assert bool(spec.get("allow_target_engagement", False))
    assert bool(spec.get("disallow_other_enemy_engagement", False))


def test_parasitic_infection_qualifying_kill_queues_pick_point(monkeypatch):
    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.game.get_roll",
        lambda die: 2 if str(die).strip().upper() == "D3" else 1,
    )

    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    source.deployed = True
    target.deployed = True
    source.reserve_status = "deployed"
    target.reserve_status = "deployed"
    source.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    target.models[0].set_location(27.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    assert game.map.place_unit(source)
    assert game.map.place_unit(target)
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=source.models[0],
        attacker_unit=source,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_barbed_ovipositor_profile(),
    )
    game.event_system.publish("unit_shooting_resolved", attacker_unit=source)

    request = _find_parasitic_pick_point_request(game)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("ability", "") or "") == "parasitic_infection_spawn"
    assert str(ctx.get("source_unit_id", "") or "") == str(get_entity_id(source) or "")
    assert str(ctx.get("target_unit_id", "") or "") == str(get_entity_id(target) or "")
    assert int(ctx.get("spawn_model_count", 0) or 0) == 2


def test_parasitic_infection_non_matching_weapon_does_not_queue_request(monkeypatch):
    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.game.get_roll",
        lambda die: 2 if str(die).strip().upper() == "D3" else 1,
    )

    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    source.deployed = True
    target.deployed = True
    source.reserve_status = "deployed"
    target.reserve_status = "deployed"
    source.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    target.models[0].set_location(27.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    assert game.map.place_unit(source)
    assert game.map.place_unit(target)
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=source.models[0],
        attacker_unit=source,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_wrong_profile(),
    )
    game.event_system.publish("unit_shooting_resolved", attacker_unit=source)

    assert _find_parasitic_pick_point_request(game) is None


def test_parasitic_infection_skip_consumes_pending_trigger(monkeypatch):
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.game.get_roll",
        lambda die: 2 if str(die).strip().upper() == "D3" else 1,
    )

    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    source.deployed = True
    target.deployed = True
    source.reserve_status = "deployed"
    target.reserve_status = "deployed"
    source.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    target.models[0].set_location(27.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    assert game.map.place_unit(source)
    assert game.map.place_unit(target)
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=source.models[0],
        attacker_unit=source,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_barbed_ovipositor_profile(),
    )
    game.event_system.publish("unit_shooting_resolved", attacker_unit=source)
    request = _find_parasitic_pick_point_request(game)
    assert request is not None
    skip = _option_by_action(request, "skip")
    assert skip is not None

    resolved = resolve_decision_command(
        game,
        request,
        skip.option_id,
        result_payload={},
        player_id=tyr_player.id,
    )
    assert bool(getattr(resolved, "ok", False))
    assert _find_parasitic_pick_point_request(game) is None
    sr = dict(getattr(source, "special_rules", {}) or {})
    assert not list(sr.get("parasitic_infection_pending_triggers", []) or [])


def test_parasitic_infection_confirm_spawns_ripper_swarms(monkeypatch):
    from warhammer40k_ai.utility.aura_utils import distance_between_models_bases_3d

    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.game.get_roll",
        lambda die: 2 if str(die).strip().upper() == "D3" else 1,
    )

    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    source.deployed = True
    target.deployed = True
    source.reserve_status = "deployed"
    target.reserve_status = "deployed"
    source.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    target.models[0].set_location(27.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    assert game.map.place_unit(source)
    assert game.map.place_unit(target)
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=source.models[0],
        attacker_unit=source,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_barbed_ovipositor_profile(),
    )
    game.event_system.publish("unit_shooting_resolved", attacker_unit=source)
    request = _find_parasitic_pick_point_request(game)
    assert request is not None
    confirm = _option_by_action(request, "confirm")
    assert confirm is not None

    resolved = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={"point": [22.0, 20.0]},
        player_id=tyr_player.id,
    )
    assert bool(getattr(resolved, "ok", False))

    spawned_units = [
        unit
        for unit in list(getattr(tyr_army, "units", []) or [])
        if str(getattr(unit, "name", "") or "").strip().lower() == "ripper swarms"
        and bool(getattr(unit, "spawned_in_battle", False))
    ]
    assert len(spawned_units) == 1
    spawned = spawned_units[0]
    assert spawned in list(getattr(game.map, "units", []) or [])
    assert len(list(getattr(spawned, "models", []) or [])) == 2
    for model in list(getattr(spawned, "models", []) or []):
        assert float(distance_between_models_bases_3d(model, source.models[0])) <= 3.0 + 1e-6

    assert _find_parasitic_pick_point_request(game) is None
    source_sr = dict(getattr(source, "special_rules", {}) or {})
    assert not list(source_sr.get("parasitic_infection_pending_triggers", []) or [])


def test_parasitic_infection_invalid_point_rejected_and_request_remains(monkeypatch):
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    monkeypatch.setattr(
        "warhammer40k_ai.engine.game.get_roll",
        lambda die: 2 if str(die).strip().upper() == "D3" else 1,
    )

    source = _make_unit(
        "Parasite of Mortrex",
        abilities=[
            {
                "name": "Parasitic Infection",
                "description": PARASITIC_INFECTION_RULE,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["CHARACTER", "MONSTER", "FLY"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    blocker = _make_unit(
        "Enemy Blocker",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    source.deployed = True
    target.deployed = True
    blocker.deployed = True
    source.reserve_status = "deployed"
    target.reserve_status = "deployed"
    blocker.reserve_status = "deployed"
    source.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    target.models[0].set_location(27.0, 20.0, 0.0, 0.0)
    blocker.models[0].set_location(24.2, 20.0, 0.0, 0.0)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    enemy_army.add_unit(blocker)
    assert game.map.place_unit(source)
    assert game.map.place_unit(target)
    assert game.map.place_unit(blocker)
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=source.models[0],
        attacker_unit=source,
        target_model=target.models[0],
        target_unit=target,
        weapon_profile=_barbed_ovipositor_profile(),
    )
    game.event_system.publish("unit_shooting_resolved", attacker_unit=source)
    request = _find_parasitic_pick_point_request(game)
    assert request is not None
    confirm = _option_by_action(request, "confirm")
    assert confirm is not None

    invalid = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={"point": [22.0, 20.0]},
        player_id=tyr_player.id,
    )
    assert not bool(getattr(invalid, "ok", False))
    assert any("parasitic infection" in str(err).lower() for err in list(getattr(invalid, "errors", []) or []))
    assert _find_parasitic_pick_point_request(game) is not None

    spawned_units = [
        unit
        for unit in list(getattr(tyr_army, "units", []) or [])
        if str(getattr(unit, "name", "") or "").strip().lower() == "ripper swarms"
        and bool(getattr(unit, "spawned_in_battle", False))
    ]
    assert not spawned_units
