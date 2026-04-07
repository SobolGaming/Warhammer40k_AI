from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
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
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Skitarii Hunter Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, admech_army, enemy_army, admech_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ADM",
        detachment="Skitarii Hunter Cohort",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _find_choose_quarry_request(game: Game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability_key or ""):
            return req
    return None


def _find_reactive_move_request(game: Game, *, kind: str, source_contains: str = ""):
    wanted_kind = str(kind or "").strip()
    source_filter = str(source_contains or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("reactive_move_kind", "") or "").strip() != wanted_kind:
            continue
        if source_filter and source_filter not in str(ctx.get("reactive_move_source", "") or "").strip().lower():
            continue
        return req
    return None


def test_skitarii_hunter_enhancement_descriptors_registered():
    expected = {
        "000008560002": (
            "Cantic Thrallnet",
            "select_friendly_skitarii_unit_within_range_of_bearer_and_treat_both_doctrina_imperatives_as_active",
        ),
        "000008560003": (
            "Clandestine Infiltrator",
            "grant_infiltrators_and_scouts_to_bearer_and_bearer_led_unit",
        ),
        "000008560004": ("Veiled Hunter", "redeploy_units"),
        "000008560005": ("Battle-sphere Uplink", "post_shoot_reactive_normal_move_no_charge"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_cantic_thrallnet_selects_one_eligible_unit_and_applies_both_imperatives_until_next_battle_round():
    game, admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    marshal = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii_bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii_far = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    non_skitarii = _make_unit(
        "Kataphron Destroyers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    for unit in (marshal, skitarii_bodyguard, skitarii_far, non_skitarii):
        admech_army.add_unit(unit)
    _attach_leader(skitarii_bodyguard, marshal)
    _set_unit_position(skitarii_bodyguard, 0.0, 0.0)
    _set_unit_position(skitarii_far, 20.0, 0.0)
    _set_unit_position(non_skitarii, 6.0, 0.0)
    game.map.units = [marshal, skitarii_bodyguard, skitarii_far, non_skitarii]
    game.rebuild_entity_registry()

    _apply_enhancement(marshal, enhancement_id="000008560002", enhancement_name="Cantic Thrallnet")

    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_battle_round_start(1, game=game)
    request = _find_choose_quarry_request(game, "skitarii_cantic_thrallnet")
    assert request is not None

    candidate_ids = {
        str(v or "").strip()
        for v in list((request.context or {}).get("candidate_unit_ids", []) or [])
        if str(v or "").strip()
    }
    bodyguard_root_id = str(get_entity_id(skitarii_bodyguard.get_attached_unit_root()) or "")
    far_root_id = str(get_entity_id(skitarii_far.get_attached_unit_root()) or "")
    non_skitarii_root_id = str(get_entity_id(non_skitarii.get_attached_unit_root()) or "")
    assert bodyguard_root_id in candidate_ids
    assert far_root_id not in candidate_ids
    assert non_skitarii_root_id not in candidate_ids

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == bodyguard_root_id
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=admech_player.id)
    assert bool(getattr(result, "ok", False))
    assert mgr.skitarii_cantic_thrallnet_applies(skitarii_bodyguard, game=game) is True

    doctrina_mgr = admech_army.doctrina_imperatives
    assert doctrina_mgr.select_imperative("PROTECTOR", battle_round=1) is True
    selected_keys = doctrina_mgr.get_active_imperative_keys_for_unit(skitarii_bodyguard, game=game)
    other_keys = doctrina_mgr.get_active_imperative_keys_for_unit(skitarii_far, game=game)
    assert "PROTECTOR" in selected_keys
    assert "CONQUEROR" in selected_keys
    assert "PROTECTOR" not in other_keys
    assert "CONQUEROR" not in other_keys

    game.turn = 2
    mgr.on_battle_round_start(2, game=game)
    assert mgr.skitarii_cantic_thrallnet_applies(skitarii_bodyguard, game=game) is False


def test_clandestine_infiltrator_grants_infiltrate_and_scouts_to_bearer_and_led_unit():
    game, admech_army, _enemy_army, _admech_player, _enemy_player = _build_game()
    marshal = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(marshal)
    admech_army.add_unit(bodyguard)
    _attach_leader(bodyguard, marshal)
    game.map.units = [marshal, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(marshal, enhancement_id="000008560003", enhancement_name="Clandestine Infiltrator")

    assert bodyguard.has_infiltrate() is True
    has_scout, scout_distance = bodyguard.has_scout()
    assert has_scout is True
    assert int(scout_distance) == 6

    assert marshal.has_infiltrate() is True
    leader_has_scout, leader_scout_distance = marshal.has_scout()
    assert leader_has_scout is True
    assert int(leader_scout_distance) == 6


def test_veiled_hunter_redeploy_filters_to_skitarii_infantry_and_allows_strategic_reserves():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    marshal = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    source_bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii_infantry = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii_mounted = _make_unit(
        "Serberys Raiders",
        keywords=["MOUNTED", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    non_skitarii_infantry = _make_unit(
        "Kataphron Breachers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (marshal, source_bodyguard, skitarii_infantry, skitarii_mounted, non_skitarii_infantry):
        admech_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _attach_leader(source_bodyguard, marshal)
    game.map.units = [marshal, source_bodyguard, skitarii_infantry, skitarii_mounted, non_skitarii_infantry, enemy]
    game.rebuild_entity_registry()
    game.attacker_index = 0
    game.defender_index = 1

    _apply_enhancement(marshal, enhancement_id="000008560004", enhancement_name="Veiled Hunter")
    has_redeploy, count, can_place_in_reserves = marshal.has_redeploy()
    assert has_redeploy is True
    assert int(count) == 3
    assert can_place_in_reserves is True
    assert list((getattr(marshal, "_ability_cache", {}) or {}).get("redeploy_filters", []) or []) == ["SKITARII", "INFANTRY"]

    game.execute_redeploy_units_phase()
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "aeldari_guileful_strategist"
        and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Veiled Hunter"
        and str(getattr(req, "player_id", "") or "") == str(admech_player.id)
    )

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    source_root_id = str(get_entity_id(source_bodyguard.get_attached_unit_root()) or "")
    infantry_root_id = str(get_entity_id(skitarii_infantry.get_attached_unit_root()) or "")
    mounted_root_id = str(get_entity_id(skitarii_mounted.get_attached_unit_root()) or "")
    non_skitarii_root_id = str(get_entity_id(non_skitarii_infantry.get_attached_unit_root()) or "")
    assert source_root_id in target_ids
    assert infantry_root_id in target_ids
    assert mounted_root_id not in target_ids
    assert non_skitarii_root_id not in target_ids

    for target_id in (source_root_id, infantry_root_id):
        actions = {
            str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == target_id
        }
        assert "battlefield" in actions
        assert "strategic_reserves" in actions


def test_battle_sphere_uplink_queues_post_shoot_reactive_move():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    marshal = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(marshal)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, marshal)
    _set_unit_position(bodyguard, 0.0, 0.0)
    _set_unit_position(enemy, 10.0, 0.0)
    game.map.units = [marshal, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(marshal, enhancement_id="000008560005", enhancement_name="Battle-sphere Uplink")

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=bodyguard, hits_by_target={enemy: 1})
    request = _find_reactive_move_request(
        game,
        kind="post_shoot_no_charge",
        source_contains="Battle-sphere Uplink",
    )
    assert request is not None
    assert int((dict(getattr(request, "context", {}) or {})).get("max_distance", 0) or 0) == 6
    assert "Battle-sphere Uplink" in str((dict(getattr(request, "context", {}) or {})).get("reactive_move_source", "") or "")


def test_battle_sphere_uplink_does_not_queue_when_unit_is_engaged():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    marshal = _make_unit(
        "Skitarii Marshal",
        keywords=["CHARACTER", "INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(marshal)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, marshal)
    _set_unit_position(bodyguard, 0.0, 0.0)
    _set_unit_position(enemy, 0.5, 0.0)
    game.map.units = [marshal, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(marshal, enhancement_id="000008560005", enhancement_name="Battle-sphere Uplink")

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=bodyguard, hits_by_target={enemy: 1})
    request = _find_reactive_move_request(
        game,
        kind="post_shoot_no_charge",
        source_contains="Battle-sphere Uplink",
    )
    assert request is None
