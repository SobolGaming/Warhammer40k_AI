from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Adeptus Custodes",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "5",
        wounds: str = "4",
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
                "M": "6",
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Adeptus Custodes",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    toughness: str = "5",
    wounds: str = "4",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _make_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army("Adeptus Custodes", "Null Maiden Vigil")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("AC", control=PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, custodes_player, enemy_player


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="AC",
        detachment="Null Maiden Vigil",
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _enhancement_bearer_model(unit: Unit):
    sr = getattr(unit, "special_rules", {}) or {}
    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            return model
    return unit.models[0] if list(getattr(unit, "models", []) or []) else None


def _reset_model_wounds(model) -> None:
    model._wounds = int(getattr(model, "_base_wounds", 0) or 0)


def _melee_profile(*, attacks: int = 2, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        {
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": str(int(strength)),
            "AP": "-1",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


def _attack_result_stub(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=str(getattr(attacker, "name", "Attacker") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "Target") or "Target"),
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


def test_null_maiden_vigil_enhancement_descriptors_registered() -> None:
    voidsheen = get_enhancement_tool_descriptor(enhancement_id="000008926002")
    assert voidsheen is not None
    assert voidsheen.name == "Enhanced Voidsheen Cloak"
    assert voidsheen.effect == "reduce_allocated_damage_or_set_to_one_vs_psyker_or_battleshocked_attacker"

    huntress = get_enhancement_tool_descriptor(enhancement_id="000008926003")
    assert huntress is not None
    assert huntress.name == "Huntress' Eye"
    assert huntress.effect == "select_enemy_unit_within_range_to_take_battleshock_test"

    oblivion = get_enhancement_tool_descriptor(enhancement_id="000008926004")
    assert oblivion is not None
    assert oblivion.name == "Oblivion Knight"
    assert oblivion.effect == "add_hit_bonus_for_bearer_led_unit_and_wound_bonus_vs_psyker"

    raptor = get_enhancement_tool_descriptor(enhancement_id="000008926005")
    assert raptor is not None
    assert raptor.name == "Raptor Blade"
    assert raptor.effect == "bearer_melee_asd_bonus_with_conditional_extra_vs_battleshocked_psyker_in_engagement"


def test_huntress_eye_command_phase_request_and_battleshock_application() -> None:
    game, custodes_player, enemy_player = _make_game()
    bearer_unit = _make_unit(
        "Knight-Centura",
        "ac-huntress-bearer",
        keywords=["CHARACTER", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_in = _make_unit(
        "Enemy In Range",
        "enemy-huntress-in",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_out = _make_unit(
        "Enemy Out Of Range",
        "enemy-huntress-out",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy_in)
    enemy_player.army.add_unit(enemy_out)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(enemy_in, 10.0, 0.0)
    _deploy_unit(enemy_out, 20.0, 0.0)
    game.map.units = [bearer_unit, enemy_in, enemy_out]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000008926003", name="Huntress' Eye")

    calls: list[tuple[str, int]] = []
    enemy_in.take_battle_shock_test = lambda turn: calls.append(("in", int(turn)))
    enemy_out.take_battle_shock_test = lambda turn: calls.append(("out", int(turn)))

    mgr = custodes_player.army.adeptus_custodes_detachments
    game.turn = 2
    mgr.on_command_phase_start(game=game, player=custodes_player)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "huntress_eye"
    ]
    assert len(requests) == 1
    request = requests[0]

    option_target_ids = {
        str((opt.payload or {}).get("target_unit_id", "") or "")
        for opt in list(request.options or [])
    }
    assert str(get_entity_id(enemy_in) or "") in option_target_ids
    assert str(get_entity_id(enemy_out) or "") not in option_target_ids

    selected = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_in) or "")
    )
    result = resolve_decision_command(game, request, selected.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False))
    assert calls == [("in", 2)]


def test_oblivion_knight_requires_leading_and_grants_hit_plus_wound_vs_psyker() -> None:
    game, custodes_player, enemy_player = _make_game()
    bodyguard = _make_unit(
        "Vigilators",
        "ac-oblivion-bodyguard",
        keywords=["INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    leader = _make_unit(
        "Knight-Centura",
        "ac-oblivion-leader",
        keywords=["CHARACTER", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    unattached = _make_unit(
        "Knight-Centura Solo",
        "ac-oblivion-solo",
        keywords=["CHARACTER", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-oblivion-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    enemy_non_psyker = _make_unit(
        "Enemy Non Psyker",
        "enemy-oblivion-non-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(bodyguard)
    custodes_player.army.add_unit(leader)
    custodes_player.army.add_unit(unattached)
    enemy_player.army.add_unit(enemy_psyker)
    enemy_player.army.add_unit(enemy_non_psyker)
    leader.attach_to_unit(bodyguard)
    _deploy_unit(bodyguard, 0.0, 0.0)
    _deploy_unit(leader, 0.0, 0.0)
    _deploy_unit(unattached, 2.0, 0.0)
    _deploy_unit(enemy_psyker, 4.0, 0.0)
    _deploy_unit(enemy_non_psyker, 6.0, 0.0)
    game.map.units = [bodyguard, leader, unattached, enemy_psyker, enemy_non_psyker]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008926004", name="Oblivion Knight")
    _apply_enhancement(unattached, enhancement_id="000008926004", name="Oblivion Knight")

    hit_mods = bodyguard.get_unit_hit_reroll_modifiers(
        "melee",
        target=enemy_non_psyker,
        attacker_model=bodyguard.models[0],
    )
    assert int(hit_mods.get("hit", 0) or 0) == 1
    assert any("Oblivion Knight" in str(reason or "") for reason in list(hit_mods.get("hit_reasons", ()) or ()))

    wound_vs_psyker = bodyguard.get_unit_wound_reroll_modifiers("melee", target=enemy_psyker)
    assert int(wound_vs_psyker.get("wound", 0) or 0) == 1
    assert any(
        "Oblivion Knight" in str(reason or "")
        for reason in list(wound_vs_psyker.get("wound_reasons", ()) or ())
    )

    wound_vs_non_psyker = bodyguard.get_unit_wound_reroll_modifiers("melee", target=enemy_non_psyker)
    assert int(wound_vs_non_psyker.get("wound", 0) or 0) == 0

    solo_hit_mods = unattached.get_unit_hit_reroll_modifiers(
        "melee",
        target=enemy_non_psyker,
        attacker_model=unattached.models[0],
    )
    assert int(solo_hit_mods.get("hit", 0) or 0) == 0

    solo_wound_mods = unattached.get_unit_wound_reroll_modifiers("melee", target=enemy_psyker)
    assert int(solo_wound_mods.get("wound", 0) or 0) == 0


def test_raptor_blade_applies_bearer_only_base_and_conditional_melee_bonuses() -> None:
    game, custodes_player, enemy_player = _make_game()
    bearer_unit = _make_unit(
        "Knight-Centura",
        "ac-raptor-bearer",
        model_count=2,
        keywords=["CHARACTER", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_non_psyker = _make_unit(
        "Enemy Non Psyker",
        "enemy-raptor-non-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
        wounds="10",
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-raptor-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
        toughness="5",
        wounds="10",
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(enemy_non_psyker)
    enemy_player.army.add_unit(enemy_psyker)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(enemy_non_psyker, 2.0, 0.0)
    _deploy_unit(enemy_psyker, 20.0, 0.0)
    game.map.units = [bearer_unit, enemy_non_psyker, enemy_psyker]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000008926005", name="Raptor Blade")
    bearer = _enhancement_bearer_model(bearer_unit)
    assert bearer is not None
    non_bearer = next(model for model in bearer_unit.models if model is not bearer)

    profile = _melee_profile(attacks=2, strength=4, damage=1)

    bearer_result = _attack_result_stub(profile, bearer, enemy_non_psyker)
    bearer_attacks = profile._resolve_attack_count(
        enemy_non_psyker,
        bearer,
        bearer_result,
        publish_roll_event=False,
    )
    non_bearer_result = _attack_result_stub(profile, non_bearer, enemy_non_psyker)
    non_bearer_attacks = profile._resolve_attack_count(
        enemy_non_psyker,
        non_bearer,
        non_bearer_result,
        publish_roll_event=False,
    )
    assert int(getattr(bearer_attacks, "num_attacks", 0) or 0) == 3
    assert int(getattr(non_bearer_attacks, "num_attacks", 0) or 0) == 2

    bearer_wound = profile._wound_target_with_tracking(
        enemy_non_psyker,
        bearer,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    non_bearer_wound = profile._wound_target_with_tracking(
        enemy_non_psyker,
        non_bearer,
        {"damage_characteristic": 1},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(bearer_wound.get("wound", False))
    assert bool(non_bearer_wound.get("wound", False)) is False

    enemy_target_model = enemy_non_psyker.models[0]
    _reset_model_wounds(enemy_target_model)
    bearer_damage = profile._damage_target_with_tracking(
        enemy_target_model,
        bearer,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    _reset_model_wounds(enemy_target_model)
    non_bearer_damage = profile._damage_target_with_tracking(
        enemy_target_model,
        non_bearer,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(bearer_damage.get("damage_applied", 0) or 0) == 2
    assert int(non_bearer_damage.get("damage_applied", 0) or 0) == 1

    _deploy_unit(enemy_psyker, 0.0, 0.0)
    enemy_psyker.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    conditional_result = _attack_result_stub(profile, bearer, enemy_psyker)
    conditional_attacks = profile._resolve_attack_count(
        enemy_psyker,
        bearer,
        conditional_result,
        publish_roll_event=False,
    )
    assert int(getattr(conditional_attacks, "num_attacks", 0) or 0) == 4

    conditional_wound = profile._wound_target_with_tracking(
        enemy_psyker,
        bearer,
        {"damage_characteristic": 1},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(conditional_wound.get("wound", False))

    enemy_psyker_model = enemy_psyker.models[0]
    _reset_model_wounds(enemy_psyker_model)
    conditional_damage = profile._damage_target_with_tracking(
        enemy_psyker_model,
        bearer,
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(conditional_damage.get("damage_applied", 0) or 0) == 3


def test_enhanced_voidsheen_cloak_applies_bearer_only_damage_rules() -> None:
    game, custodes_player, enemy_player = _make_game()
    bearer_unit = _make_unit(
        "Knight-Centura",
        "ac-voidsheen-bearer",
        model_count=2,
        keywords=["CHARACTER", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
        wounds="8",
    )
    attacker_non_psyker = _make_unit(
        "Enemy Warrior",
        "enemy-voidsheen-non-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    attacker_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-voidsheen-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    attacker_shocked = _make_unit(
        "Enemy Shocked",
        "enemy-voidsheen-shocked",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(bearer_unit)
    enemy_player.army.add_unit(attacker_non_psyker)
    enemy_player.army.add_unit(attacker_psyker)
    enemy_player.army.add_unit(attacker_shocked)
    _deploy_unit(bearer_unit, 0.0, 0.0)
    _deploy_unit(attacker_non_psyker, 2.0, 0.0)
    _deploy_unit(attacker_psyker, 2.0, 2.0)
    _deploy_unit(attacker_shocked, 2.0, 4.0)
    game.map.units = [bearer_unit, attacker_non_psyker, attacker_psyker, attacker_shocked]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000008926002", name="Enhanced Voidsheen Cloak")
    bearer = _enhancement_bearer_model(bearer_unit)
    assert bearer is not None
    non_bearer = next(model for model in bearer_unit.models if model is not bearer)
    profile = _melee_profile(attacks=2, strength=4, damage=3)

    _reset_model_wounds(bearer)
    normal_damage = profile._damage_target_with_tracking(
        bearer,
        attacker_non_psyker.models[0],
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(normal_damage.get("damage_applied", 0) or 0) == 2

    _reset_model_wounds(bearer)
    psyker_damage = profile._damage_target_with_tracking(
        bearer,
        attacker_psyker.models[0],
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(psyker_damage.get("damage_applied", 0) or 0) == 1

    attacker_shocked.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    _reset_model_wounds(bearer)
    shocked_damage = profile._damage_target_with_tracking(
        bearer,
        attacker_shocked.models[0],
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(shocked_damage.get("damage_applied", 0) or 0) == 1

    _reset_model_wounds(non_bearer)
    non_bearer_damage = profile._damage_target_with_tracking(
        non_bearer,
        attacker_non_psyker.models[0],
        {"mortal_wound": False},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert int(non_bearer_damage.get("damage_applied", 0) or 0) == 3
