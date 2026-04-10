from __future__ import annotations

from itertools import count
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


_WARGEAR_IDS = count(1)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "2",
                "W": "4",
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
        self.transport = ""


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army.with_detachment("Adeptus Custodes", "Null Maiden Vigil")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    custodes_player = Player("Custodes", control=PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)

    custodes_player.command_points = 5
    enemy_player.command_points = 5
    custodes_army.configure_rule_managers(force=True)
    custodes_player.stratagems.refresh_available()
    game.turn = 1
    game.current_player_index = 0
    return game, custodes_player, enemy_player, custodes_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, phase_name: str, *, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _pending_reaction_by_name(player: Player, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _find_request(game: Game, *, decision_type: str, ability: str):
    ability_norm = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "").strip().lower() == ability_norm:
            return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    want = str(value or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "").strip().upper() == want:
            return option
    return None


def _ranged_wargear(name: str):
    return SimpleNamespace(
        id=f"test-ranged-wargear-{next(_WARGEAR_IDS)}",
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )


def _melee_wargear(name: str):
    return SimpleNamespace(
        id=f"test-melee-wargear-{next(_WARGEAR_IDS)}",
        name=name,
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )


def _ranged_profile(name: str, *, attacks: int = 2, description: str = "") -> WargearProfile:
    parent = SimpleNamespace(name=name, is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        name,
        {
            "range": "24",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description or ""),
        },
        parent_wargear=parent,
    )


def _melee_profile(name: str) -> WargearProfile:
    parent = SimpleNamespace(name=name, is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        name,
        {
            "range": "Melee",
            "A": "3",
            "BS_WS": "2+",
            "S": "5",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_null_maiden_stratagem_descriptors_registered() -> None:
    expected = {
        "000008927004": ("ANATHEMA BLADEMASTERY", "grant_full_melee_hit_rerolls_and_conditional_full_wound_rerolls"),
        "000008927002": ("DESPERATION'S PRICE", "leadership_test_then_battle_shock_with_mortal_wounds_on_failed_test"),
        "000008927005": ("PSY-CHAFF VOLLEY", "mark_enemy_as_prosecuted_for_anathema_ap_bonus_and_conditional_hit_penalty"),
        "000008927007": ("PSYCHIC ABOMINATIONS", "grant_stealth_and_limit_psyker_or_battle_shocked_ranged_targeting_to_12"),
        "000008927006": ("PURGATION SWEEP", "increase_torrent_weapon_attacks_with_larger_bonus_vs_psyker_or_battle_shocked"),
        "000008927003": ("WITCH HUNTERS", "choose_lethal_hits_or_sustained_hits_1_for_unit_weapons_with_psyker_target_lock"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_anathema_blademastery_grants_hit_rerolls_and_conditional_wound_rerolls() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    vigilators = _make_unit(
        "Vigilators",
        "ac-vigilators",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    enemy_normal = _make_unit(
        "Enemy Infantry",
        "enemy-normal",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    vigilators.models[0].wargear = [_melee_wargear("Executioner Greatblade")]
    custodes_army.add_unit(vigilators)
    enemy_army.add_unit(enemy_psyker)
    enemy_army.add_unit(enemy_normal)
    _place_unit(game, vigilators, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 7.0, 5.0)
    _place_unit(game, enemy_normal, 9.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "FIGHT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("ANATHEMA BLADEMASTERY", unit=vigilators, phase_name="Fight phase")
    assert ok is True

    mgr = custodes_army.adeptus_custodes_detachments
    profile = _melee_profile("Executioner Greatblade")
    hit_reroll, hit_source = mgr.null_maiden_anathema_blademastery_hit_reroll(
        vigilators.models[0],
        target_unit=enemy_normal,
        game=game,
        weapon_profile=profile,
    )
    wound_reroll_psyker, wound_source = mgr.null_maiden_anathema_blademastery_wound_reroll(
        vigilators.models[0],
        target_unit=enemy_psyker,
        game=game,
        weapon_profile=profile,
    )
    wound_reroll_normal, _ = mgr.null_maiden_anathema_blademastery_wound_reroll(
        vigilators.models[0],
        target_unit=enemy_normal,
        game=game,
        weapon_profile=profile,
    )
    enemy_normal.apply_status_effect(BattleShockEffect(game.turn))
    wound_reroll_battle_shocked, _ = mgr.null_maiden_anathema_blademastery_wound_reroll(
        vigilators.models[0],
        target_unit=enemy_normal,
        game=game,
        weapon_profile=profile,
    )

    assert hit_reroll is True
    assert hit_source == "ANATHEMA BLADEMASTERY"
    assert wound_reroll_psyker is True
    assert wound_source == "ANATHEMA BLADEMASTERY"
    assert wound_reroll_battle_shocked is True
    assert wound_reroll_normal is False


def test_purgation_sweep_increases_torrent_attacks_with_higher_bonus_into_psykers() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    witchseekers = _make_unit(
        "Witchseekers",
        "ac-witchseekers",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-purgation-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    enemy_normal = _make_unit(
        "Enemy Infantry",
        "enemy-purgation-normal",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    witchseekers.models[0].wargear = [_ranged_wargear("Witchseeker Flamer")]
    custodes_army.add_unit(witchseekers)
    enemy_army.add_unit(enemy_psyker)
    enemy_army.add_unit(enemy_normal)
    _place_unit(game, witchseekers, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 10.0, 5.0)
    _place_unit(game, enemy_normal, 12.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("PURGATION SWEEP", unit=witchseekers, phase_name="Shooting phase")
    assert ok is True

    mgr = custodes_army.adeptus_custodes_detachments
    torrent_profile = _ranged_profile("Witchseeker Flamer", attacks=1, description="Torrent")
    normal_bonus, source = mgr.null_maiden_purgation_sweep_attacks_bonus(
        witchseekers.models[0],
        target_unit=enemy_normal,
        game=game,
        weapon_profile=torrent_profile,
    )
    psyker_bonus, _ = mgr.null_maiden_purgation_sweep_attacks_bonus(
        witchseekers.models[0],
        target_unit=enemy_psyker,
        game=game,
        weapon_profile=torrent_profile,
    )

    assert normal_bonus == 1
    assert psyker_bonus == 2
    assert source == "PURGATION SWEEP"


def test_witch_hunters_queues_choice_applies_keyword_and_locks_targets_to_psykers() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    prosecutors = _make_unit(
        "Prosecutors",
        "ac-prosecutors",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-wh-psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    enemy_normal = _make_unit(
        "Enemy Infantry",
        "enemy-wh-normal",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    prosecutors.models[0].wargear = [_ranged_wargear("Bolter"), _melee_wargear("Executioner Blade")]
    custodes_army.add_unit(prosecutors)
    enemy_army.add_unit(enemy_psyker)
    enemy_army.add_unit(enemy_normal)
    _place_unit(game, prosecutors, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 10.0, 5.0)
    _place_unit(game, enemy_normal, 12.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("WITCH HUNTERS", unit=prosecutors, phase_name="Shooting phase")
    assert ok is True

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="adeptus_custodes_null_maiden_witch_hunters_choice",
    )
    assert request is not None
    option = _find_option_by_payload(request, key="choice_key", value="LETHAL_HITS")
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False)) is True

    ranged_bonuses = list(prosecutors.models[0].get_temporary_weapon_keyword_bonuses("Bolter") or [])
    melee_bonuses = list(prosecutors.models[0].get_temporary_weapon_keyword_bonuses("Executioner Blade") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in ranged_bonuses
    )
    assert melee_bonuses == []
    assert prosecutors._adeptus_custodes_witch_hunters_target_locked_to(enemy_psyker, game=game, attack_type="ranged") is True
    assert prosecutors._adeptus_custodes_witch_hunters_target_locked_to(enemy_normal, game=game, attack_type="ranged") is False

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(prosecutors.models[0].get_temporary_weapon_keyword_bonuses("Bolter") or []) == []


def test_psychic_abominations_reacts_to_targeting_and_blocks_distant_psyker_shooters() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    prosecutors = _make_unit(
        "Prosecutors",
        "ac-psychic-abominations",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker Shooters",
        "enemy-psychic-abominations",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    prosecutors.models[0].wargear = [_ranged_wargear("Bolter")]
    enemy_psyker.models[0].wargear = [_ranged_wargear("Warp Bolter")]
    enemy_psyker.models[0].keywords = ["PSYKER"]
    custodes_army.add_unit(prosecutors)
    enemy_army.add_unit(enemy_psyker)
    _place_unit(game, prosecutors, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 23.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_psyker, target_units=[prosecutors])
    pending = _pending_reaction_by_name(custodes_player, "PSYCHIC ABOMINATIONS")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "PSYCHIC ABOMINATIONS",
        unit=prosecutors,
        attacking_unit=enemy_psyker,
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert prosecutors.has_stealth() is True

    enemy_psyker._has_line_of_sight_to_target = lambda *_args, **_kwargs: True
    ranged_profile = _ranged_profile("Warp Bolter")
    can_shoot_from_far = enemy_psyker._can_model_shoot_weapon_at_target(
        enemy_psyker.models[0],
        ranged_profile,
        prosecutors,
        game.map,
    )
    enemy_psyker.models[0].set_location(12.0, 5.0, 0.0, 0.0)
    can_shoot_from_near = enemy_psyker._can_model_shoot_weapon_at_target(
        enemy_psyker.models[0],
        ranged_profile,
        prosecutors,
        game.map,
    )

    assert can_shoot_from_far is False
    assert can_shoot_from_near is True

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert prosecutors.has_stealth() is False


def test_psy_chaff_volley_marks_enemy_for_ap_bonus_and_hit_penalty() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    prosecutors = _make_unit(
        "Prosecutors",
        "ac-psy-chaff-source",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    witchseekers = _make_unit(
        "Witchseekers",
        "ac-psy-chaff-ally",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-psy-chaff-target",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    prosecutors.models[0].wargear = [_ranged_wargear("Boltgun")]
    witchseekers.models[0].wargear = [_ranged_wargear("Witchseeker Flamer")]
    enemy_psyker.models[0].wargear = [_ranged_wargear("Warp Pistol")]
    custodes_army.add_unit(prosecutors)
    custodes_army.add_unit(witchseekers)
    enemy_army.add_unit(enemy_psyker)
    _place_unit(game, prosecutors, 5.0, 5.0)
    _place_unit(game, witchseekers, 7.0, 5.0)
    _place_unit(game, enemy_psyker, 10.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "SHOOTING_PHASE", current_player_index=0)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=prosecutors, hits_by_target={enemy_psyker: 1})
    pending = _pending_reaction_by_name(custodes_player, "PSY-CHAFF VOLLEY")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "PSY-CHAFF VOLLEY",
        unit=prosecutors,
        enemy_unit=enemy_psyker,
        phase_name="Shooting phase",
        enemy_candidates=list(pending.get("enemy_candidates") or []),
        dequeue=True,
    )
    assert ok is True

    mgr = custodes_army.adeptus_custodes_detachments
    ap_bonus = mgr.null_maiden_psy_chaff_volley_ap_bonus(
        witchseekers.models[0],
        enemy_psyker,
        game=game,
        weapon_profile=_ranged_profile("Witchseeker Flamer"),
    )
    hit_penalty, source = mgr.null_maiden_psy_chaff_volley_hit_penalty(enemy_psyker.models[0], game=game)
    assert ap_bonus == 1
    assert hit_penalty == -1
    assert source == "PSY-CHAFF VOLLEY"

    game.turn = 2
    game.current_player_index = 0
    expired_bonus = mgr.null_maiden_psy_chaff_volley_ap_bonus(
        witchseekers.models[0],
        enemy_psyker,
        game=game,
        weapon_profile=_ranged_profile("Witchseeker Flamer"),
    )
    assert expired_bonus == 0


def test_desperations_price_reacts_to_psychic_attacks_and_applies_mortal_wounds_plus_battle_shock() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    prosecutors = _make_unit(
        "Prosecutors",
        "ac-desperation-source",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Psyker",
        "enemy-desperation-target",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(prosecutors)
    enemy_army.add_unit(enemy_psyker)
    _place_unit(game, prosecutors, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 10.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy_psyker,
        hit_models_by_target_psychic={prosecutors: [prosecutors.models[0]]},
    )
    pending = _pending_reaction_by_name(custodes_player, "DESPERATION'S PRICE")
    assert pending is not None

    calls: list[tuple[Unit, int]] = []
    prosecutors._apply_mortal_wounds_to_unit = lambda target, amount, game_map=None: calls.append((target, int(amount)))
    enemy_psyker.pass_leadership_check = lambda: False

    ok = custodes_player.stratagems.use(
        "DESPERATION'S PRICE",
        unit=prosecutors,
        enemy_unit=enemy_psyker,
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert calls == [(enemy_psyker, 3)]
    assert enemy_psyker.is_battle_shocked() is True


def test_desperations_price_reacts_to_enemy_psychic_ability_resolution() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    prosecutors = _make_unit(
        "Prosecutors",
        "ac-desperation-cabal-source",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = _make_unit(
        "Enemy Sorcerer",
        "enemy-desperation-cabal-target",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(prosecutors)
    enemy_army.add_unit(enemy_psyker)
    _place_unit(game, prosecutors, 5.0, 5.0)
    _place_unit(game, enemy_psyker, 10.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, "COMMAND_PHASE", current_player_index=1)
    game.event_system.publish(
        "cabal_ritual_resolved",
        player=enemy_player,
        caster_unit=enemy_psyker,
        target_unit=prosecutors,
    )

    pending = _pending_reaction_by_name(custodes_player, "DESPERATION'S PRICE")
    assert pending is not None
