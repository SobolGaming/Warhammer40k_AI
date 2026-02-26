from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager, AttackSequence
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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
        movement: int = 6,
        toughness: int = 4,
        save: int = 3,
        wounds: int = 4,
        inv_sv: int = 7,
    ):
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
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": str(inv_sv),
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
    movement: int = 6,
    toughness: int = 4,
    save: int = 3,
    wounds: int = 4,
    inv_sv: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            save=save,
            wounds=wounds,
            inv_sv=inv_sv,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Haloscreed Battle Clade")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
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
        detachment="Haloscreed Battle Clade",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _find_request(game: Game, ability_key: str):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == str(ability_key or "")
    )


def _choose_units(game: Game, request, *, player_id: str, unit_ids: list[str]) -> None:
    wanted = tuple(sorted(str(v or "").strip() for v in list(unit_ids or []) if str(v or "").strip()))
    option = next(
        opt
        for opt in list(request.options or [])
        if tuple(
            sorted(
                str(v or "").strip()
                for v in list((opt.payload or {}).get("selected_unit_ids", []) or [])
                if str(v or "").strip()
            )
        )
        == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _choose_override(game: Game, request, *, player_id: str, choice_key: str) -> None:
    wanted = str(choice_key or "").strip().upper()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


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


def _ranged_profile(*, range_value: int = 24, description: str = "") -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": str(range_value),
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=parent,
    )


def _melee_profile(*, attacks: str = "1", damage: str = "1", strength: str = "8", ap: str = "-2") -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_haloscreed_enhancement_descriptors_registered():
    expected = {
        "000009745002": (
            "Transoracular Dyad Wafers",
            "grant_halo_override_to_bearer_attached_kastelan_unit_and_exclude_from_noospheric_selection",
        ),
        "000009745003": (
            "Cognitive Reinforcement",
            "treat_conqueror_and_protector_imperatives_as_active_for_bearer_unit",
        ),
        "000009745004": (
            "Sanctified Ordnance",
            "add_ranged_range_and_hazardous_reroll_for_bearer_unit",
        ),
        "000009745005": (
            "Inloaded Lethality",
            "add_melee_attacks_and_damage_to_bearer_melee_weapons",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_transoracular_dyad_wafers_excludes_unit_from_noospheric_selection_and_gains_override():
    game, admech_army, _enemy_army, admech_player, _enemy_player = _build_game()
    datasmith = _make_unit(
        "Cybernetica Datasmith",
        keywords=["CHARACTER", "INFANTRY", "CYBERNETICA DATASMITH"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    kastelans = _make_unit(
        "Kastelan Robots",
        keywords=["KASTELAN ROBOTS", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(datasmith)
    admech_army.add_unit(kastelans)
    admech_army.add_unit(skitarii)
    _attach_leader(kastelans, datasmith)
    _set_unit_position(kastelans, 10.0, 10.0)
    _set_unit_position(skitarii, 20.0, 10.0)
    game.map.units = [datasmith, kastelans, skitarii]
    game.rebuild_entity_registry()

    _apply_enhancement(datasmith, enhancement_id="000009745002", enhancement_name="Transoracular Dyad Wafers")

    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request = _find_request(game, "noospheric_transference_units")
    candidate_ids = {
        str(v or "").strip() for v in list((units_request.context or {}).get("candidate_unit_ids", []) or []) if str(v or "").strip()
    }
    kastelan_root = kastelans.get_attached_unit_root()
    kastelan_root_id = str(get_entity_id(kastelan_root) or "")
    assert kastelan_root_id
    assert kastelan_root_id not in candidate_ids

    _choose_units(
        game,
        units_request,
        player_id=admech_player.id,
        unit_ids=[str(get_entity_id(skitarii.get_attached_unit_root()) or "")],
    )
    override_request = _find_request(game, "noospheric_transference_override")
    _choose_override(
        game,
        override_request,
        player_id=admech_player.id,
        choice_key="ELECTROMOTIVE_ENERGISATION",
    )

    assert mgr.haloscreed_transoracular_halo_override_applies(kastelans) is True
    assert kastelans.get_effective_model_characteristic(kastelans.models[0], "movement") == 8


def test_cognitive_reinforcement_enables_both_imperatives_for_bearer_unit():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
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
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 10.0, 10.0)
    _set_unit_position(enemy, 18.0, 10.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000009745003", enhancement_name="Cognitive Reinforcement")
    doctrina_mgr = admech_army.doctrina_imperatives
    assert doctrina_mgr.select_imperative("PROTECTOR", battle_round=1) is True
    game.turn = 1

    assert doctrina_mgr.protector_heavy_applies(bodyguard, game=game) is True
    assert doctrina_mgr.conqueror_assault_applies(bodyguard, game=game) is True
    with patch.object(doctrina_mgr, "_unit_in_battleline_network", return_value=True):
        assert doctrina_mgr.conqueror_ap_bonus_applies(bodyguard, game=game, game_map=game.map) is True
        assert doctrina_mgr.protector_melee_hit_penalty_applies(bodyguard, game=game, game_map=game.map) is True

    ranged_profile = _ranged_profile()
    melee_profile = _melee_profile()
    ranged_hit = ranged_profile._hit_target_with_tracking(
        enemy,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    melee_hit = melee_profile._hit_target_with_tracking(
        enemy,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Protector Imperative" in str(reason or "") for reason in list(ranged_hit.get("special_effects", []) or []))
    assert any("Conqueror Imperative" in str(reason or "") for reason in list(melee_hit.get("special_effects", []) or []))
    assert int(ranged_hit.get("final_needed", 0) or 0) <= 2
    assert int(melee_hit.get("final_needed", 0) or 0) <= 2


def test_sanctified_ordnance_adds_range_and_hazardous_reroll_rule():
    game, admech_army, enemy_army, admech_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000009745004", enhancement_name="Sanctified Ordnance")

    profile = _ranged_profile(range_value=24, description="Hazardous")
    assert int(profile._effective_range_max(bodyguard.models[0])) == 30

    captured_spec = {}

    def _capture_request_dice_roll(*, player_id, spec, prompt=None):
        captured_spec["player_id"] = player_id
        captured_spec["spec"] = dict(spec or {})
        return SimpleNamespace(context={"roll_id": 1})

    game.request_dice_roll = _capture_request_dice_roll

    attacker_model = bodyguard.models[0]
    attacker_model_id = str(getattr(attacker_model, "id", "") or "")
    resolution = AttackResolutionManager()
    resolution._resolve_profile = lambda _game, _wargear_id, _profile_name: profile
    resolution._resolve_unit = lambda _game, unit_id: bodyguard if str(unit_id) == "attacker" else enemy
    resolution._resolve_model = lambda _game, model_id: attacker_model if str(model_id) == attacker_model_id else None

    seq = AttackSequence(
        sequence_id=1,
        attacker_unit_id="attacker",
        target_unit_id="target",
        wargear_id="wargear",
        profile_name="Profile",
        model_ids=[attacker_model_id],
    )
    queued = resolution._request_hazardous_roll(game, seq)
    assert queued is True
    assert str(captured_spec.get("player_id") or "") == str(admech_player.id)
    reroll_rules = list((captured_spec.get("spec", {}) or {}).get("reroll_rules", []) or [])
    sanctified_rule = next(
        rule
        for rule in reroll_rules
        if str(rule.get("action_id", "") or "") == "haloscreed_sanctified_ordnance_hazardous_reroll"
    )
    assert int(sanctified_rule.get("max_select", 0) or 0) == 1


def test_inloaded_lethality_applies_only_to_bearer_melee_weapons():
    game, admech_army, enemy_army, _admech_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        save=7,
        wounds=40,
        inv_sv=7,
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000009745005", enhancement_name="Inloaded Lethality")
    mgr = admech_army.adeptus_mechanicus_detachments
    profile = _melee_profile(attacks="1", damage="1", strength="10", ap="-5")

    bearer_a, bearer_d, _source = mgr.haloscreed_inloaded_lethality_melee_bonuses(leader.models[0], weapon_profile=profile)
    other_a, other_d, _source_other = mgr.haloscreed_inloaded_lethality_melee_bonuses(
        bodyguard.models[0],
        weapon_profile=profile,
    )
    assert int(bearer_a) == 3
    assert int(bearer_d) == 1
    assert int(other_a) == 0
    assert int(other_d) == 0

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        bearer_result = profile.attack(enemy, leader.models[0], game_map=game.map)
        other_result = profile.attack(enemy, bodyguard.models[0], game_map=game.map)
    assert int(bearer_result.attacks_rolled or 0) == 4
    assert int(other_result.attacks_rolled or 0) == 1
    assert any(
        "Inloaded Lethality +1D" in str(effect or "")
        for dmg in list(bearer_result.damage_results or [])
        for effect in list((dmg or {}).get("special_effects", []) or [])
    )
    assert not any(
        "Inloaded Lethality +1D" in str(effect or "")
        for dmg in list(other_result.damage_results or [])
        for effect in list((dmg or {}).get("special_effects", []) or [])
    )
