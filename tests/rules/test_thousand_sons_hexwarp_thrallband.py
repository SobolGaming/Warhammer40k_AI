from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager, AttackSequence
from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "4",
                "W": "3",
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
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _make_profile(*, psychic: bool, attacks: str = "1", hazardous: bool = False) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    keywords = []
    if psychic:
        keywords.append("Psychic")
    if hazardous:
        keywords.append("Hazardous")
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": ", ".join(keywords),
        },
        parent_wargear=parent,
    )


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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TS",
        detachment="Hexwarp Thrallband",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _make_attack_result(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=getattr(attacker, "name", "Attacker"),
        target_unit_name=getattr(target_unit, "name", "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _build_flow_game(
    *,
    army: Army,
    enemy_army: Army,
    nml_controlled: int,
    nml_total: int = 2,
    enemy_controlled: int = 0,
    enemy_total: int = 0,
):
    player = SimpleNamespace(id="P1", name="P1", game=None, get_army=lambda: army)
    enemy = SimpleNamespace(id="P2", name="P2", game=None, get_army=lambda: enemy_army)
    army.player = player
    enemy_army.player = enemy

    objectives = []

    def _make_objective(x: float, y: float, controller):
        location = SimpleNamespace(
            x=float(x),
            y=float(y),
            removed=False,
            controlling_player=controller,
            update_control=lambda _game: None,
        )
        return SimpleNamespace(location=location)

    for i in range(int(nml_total)):
        controller = player if i < int(nml_controlled) else enemy
        objectives.append(_make_objective(15.0 + float(i), 10.0, controller))
    for i in range(int(enemy_total)):
        controller = player if i < int(enemy_controlled) else enemy
        objectives.append(_make_objective(25.0 + float(i), 10.0, controller))

    def _in_deployment_zone(x: float, _y: float, player_id: str) -> bool:
        x_val = float(x)
        if str(player_id) == str(player.id):
            return x_val <= 10.0
        if str(player_id) == str(enemy.id):
            return x_val >= 20.0
        return False

    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        players=[player, enemy],
        map=SimpleNamespace(objectives=objectives),
        get_current_player=lambda: player,
        is_position_in_deployment_zone=_in_deployment_zone,
        is_position_wholly_in_deployment_zone=lambda x, y, _base, pid: _in_deployment_zone(x, y, pid),
    )
    player.game = game
    enemy.game = game
    return game, enemy, objectives


def test_hexwarp_flow_of_magic_adds_wound_when_wholly_within_snapshot_zone():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    attacker_unit.models[0].set_location(15.0, 10.0, 0.0, 0.0)

    game, enemy_player, objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )

    army.thousand_sons_detachments.on_phase_start(game=game)
    for objective in objectives:
        objective.location.controlling_player = enemy_player

    profile = _make_profile(psychic=True)
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound["wound"] is True
    assert any("Flow of Magic" in str(entry) for entry in wound.get("modifiers", []))
    assert not bool(attack_instance.get("hexwarp_flow_reroll_wound_ones", False))


def test_hexwarp_flow_of_magic_rerolls_wound_roll_of_one_outside_flow(monkeypatch):
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    attacker_unit.models[0].set_location(15.0, 10.0, 0.0, 0.0)

    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=0,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _d: 4)

    profile = _make_profile(psychic=True)
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert int(wound.get("reroll", 0) or 0) == 4
    assert wound["wound"] is True
    assert bool(attack_instance.get("hexwarp_flow_reroll_wound_ones", False))
    assert any("Flow of Magic" in str(entry) for entry in wound.get("special_effects", []))


def test_hexwarp_flow_of_magic_does_not_apply_to_non_psychic_attacks():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(attacker_unit)

    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    non_psychic_profile = _make_profile(psychic=False)
    bonus, reroll_ones, source = army.thousand_sons_detachments.hexwarp_flow_of_magic_psychic_wound_modifiers(
        attacker_unit.models[0],
        non_psychic_profile,
        game=game,
    )

    assert int(bonus) == 0
    assert bool(reroll_ones) is False
    assert source == ""


def test_hexwarp_arcane_might_gives_plus_one_strength_outside_flow_to_bearer_unit_models():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    leader = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY", "CHARACTER"],
        faction_keywords=["THOUSAND SONS"],
    )
    bodyguard = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(leader)
    army.add_unit(bodyguard)
    _attach_leader(bodyguard, leader)
    _apply_enhancement(leader, enhancement_id="000009741002", enhancement_name="Arcane Might")

    leader.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    bodyguard.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=0,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    bonus, source = army.thousand_sons_detachments.hexwarp_arcane_might_strength_bonus(
        bodyguard.models[0],
        _make_profile(psychic=True),
        game=game,
    )

    assert int(bonus or 0) == 1
    assert source == "Arcane Might"


def test_hexwarp_arcane_might_gives_plus_two_strength_when_bearer_unit_wholly_within_flow():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    leader = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY", "CHARACTER"],
        faction_keywords=["THOUSAND SONS"],
    )
    bodyguard = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(leader)
    army.add_unit(bodyguard)
    _attach_leader(bodyguard, leader)
    _apply_enhancement(leader, enhancement_id="000009741002", enhancement_name="Arcane Might")

    leader.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    bodyguard.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    bonus, source = army.thousand_sons_detachments.hexwarp_arcane_might_strength_bonus(
        bodyguard.models[0],
        _make_profile(psychic=True),
        game=game,
    )

    assert int(bonus or 0) == 2
    assert source == "Arcane Might"


def test_hexwarp_empowered_manifestation_extends_ritual_range_when_wholly_within_flow():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(caster)
    enemy_army.add_unit(target)
    _apply_enhancement(caster, enhancement_id="000009741003", enhancement_name="Empowered Manifestation")

    caster.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    assert float(army.cabal_of_sorcerers._ritual_range_for_model(caster.models[0])) == 30.0


def test_hexwarp_empowered_manifestation_adds_hazardous_reroll_rule():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(caster)
    _apply_enhancement(caster, enhancement_id="000009741003", enhancement_name="Empowered Manifestation")
    caster.models[0].set_location(15.0, 10.0, 0.0, 0.0)

    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    profile = _make_profile(psychic=True, hazardous=True)
    attacker_model = caster.models[0]
    attacker_model_id = str(getattr(attacker_model, "id", "") or "")
    captured_spec = {}

    def _capture_request_dice_roll(*, player_id, spec, prompt=None):
        captured_spec["player_id"] = player_id
        captured_spec["spec"] = dict(spec or {})
        return SimpleNamespace(context={"roll_id": 1})

    game.request_dice_roll = _capture_request_dice_roll
    game.is_authoritative = True

    resolution = AttackResolutionManager()
    resolution._resolve_profile = lambda _game, _wargear_id, _profile_name: profile
    resolution._resolve_unit = lambda _game, unit_id: caster if str(unit_id) == "attacker" else None
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
    reroll_rules = list((captured_spec.get("spec", {}) or {}).get("reroll_rules", []) or [])
    empowered_rule = next(
        rule
        for rule in reroll_rules
        if str(rule.get("action_id", "") or "") == "hexwarp_empowered_manifestation_hazardous_reroll"
    )
    assert int(empowered_rule.get("max_select", 0) or 0) == 1


def test_hexwarp_empyric_onslaught_adds_three_attacks_to_bearer_ranged_psychic_weapon():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(caster)
    enemy_army.add_unit(target)
    _apply_enhancement(caster, enhancement_id="000009741004", enhancement_name="Empyric Onslaught")

    caster.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    profile = _make_profile(psychic=True, attacks="1")
    attack_result = _make_attack_result(profile, caster.models[0], target)
    attacks = profile._resolve_attack_count(
        target,
        caster.models[0],
        attack_result,
        publish_roll_event=False,
    )

    assert int(attacks.num_attacks or 0) == 4
    assert any("Empyric Onslaught" in str(entry or "") for entry in list(attack_result.attacks_special_modifiers or []))


def test_hexwarp_noctilith_mantle_treats_unit_as_wholly_within_flow_outside_zone():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(caster)
    _apply_enhancement(caster, enhancement_id="000009741005", enhancement_name="Noctilith Mantle")

    caster.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=0,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    bonus, reroll_ones, source = army.thousand_sons_detachments.hexwarp_flow_of_magic_psychic_wound_modifiers(
        caster.models[0],
        _make_profile(psychic=True),
        game=game,
    )

    assert int(bonus or 0) == 1
    assert bool(reroll_ones) is False
    assert source == "Flow of Magic"


def test_hexwarp_noctilith_mantle_prevents_models_in_unit_from_using_rituals():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(caster)
    enemy_army.add_unit(target)
    _apply_enhancement(caster, enhancement_id="000009741005", enhancement_name="Noctilith Mantle")

    caster.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    target.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=0,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    mgr = army.cabal_of_sorcerers
    result = mgr.attempt_ritual(
        game,
        caster_model=caster.models[0],
        ritual_key=RITUAL_DESTINYS_RUIN.key,
        target_unit=target,
        rolls=[6, 6],
        channel_decision=False,
    )

    assert not bool(result.get("success"))
    assert "cannot use rituals" in str(result.get("reason", "")).lower()
