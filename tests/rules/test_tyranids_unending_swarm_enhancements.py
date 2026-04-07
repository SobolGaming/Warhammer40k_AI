from __future__ import annotations

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry, _validate_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 4,
        model_count: int = 1,
        movement: int = 8,
        save: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
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
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 4,
    model_count: int = 1,
    movement: int = 8,
    save: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            model_count=model_count,
            movement=movement,
            save=save,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Unending Swarm")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="TYR",
        detachment="Unending Swarm",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_profile(*, ap: int = 0, melee: bool = False) -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Bio-weapon",
            "is_melee": staticmethod(lambda: bool(melee)),
            "is_ranged": staticmethod(lambda: not bool(melee)),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    assert game.map.place_unit(unit), f"Failed to place {getattr(unit, 'name', 'Unit')}"


def _bearer_and_other_models(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = None
    other = None
    for model in list(getattr(unit, "models", []) or []):
        model_ids = {
            str(get_entity_id(model) or "").strip(),
            str(getattr(model, "id", getattr(model, "_id", "")) or "").strip(),
        }
        if bearer_id and bearer_id in model_ids:
            bearer = model
        elif other is None:
            other = model
    return bearer, other


def _find_request(game: Game, *, battle_round: int):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "naturalised_camouflage":
            continue
        if int(context.get("battle_round", 0) or 0) != int(battle_round):
            continue
        return request
    raise AssertionError("Naturalised Camouflage request was not queued.")


def _option_with_selected_ids(request, unit_ids):
    expected = sorted(str(v or "").strip() for v in list(unit_ids or []) if str(v or "").strip())
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        selected = sorted(
            str(v or "").strip()
            for v in list(payload.get("selected_unit_ids", []) or [])
            if str(v or "").strip()
        )
        if selected == expected:
            return option
    raise AssertionError(f"Selection {expected} not found.")


def test_unending_swarm_enhancement_descriptors_exist():
    expected = {
        "000008408002": ("Relentless Hunger", "bearer_unit_movement_bonus"),
        "000008408003": (
            "Naturalised Camouflage",
            "select_friendly_endless_multitude_units_for_ranged_benefit_of_cover",
        ),
        "000008408004": ("Piercing Talons", "bearer_unit_critical_wound_ap_bonus"),
        "000008408005": ("Adrenalised Onslaught", "bearer_unit_pile_in_and_consolidate_distance_bonus"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_relentless_hunger_adds_two_to_bearers_unit_movement_while_bearer_lives():
    game, tyr_army, _enemy_army, _tyr_player, _enemy_player = _build_game()
    source = _make_unit(
        "Warrior Alpha",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        model_count=2,
        movement=8,
    )
    tyr_army.add_unit(source)
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008408002", name="Relentless Hunger")
    bearer, other = _bearer_and_other_models(source)
    assert bearer is not None
    assert other is not None

    assert int(source.get_effective_model_characteristic(bearer, "movement") or 0) == 10
    assert int(source.get_effective_model_characteristic(other, "movement") or 0) == 10

    bearer.wounds = 0

    assert int(source.get_effective_model_characteristic(other, "movement") or 0) == 8


def test_piercing_talons_improves_ap_on_critical_wounds_for_models_in_bearers_unit():
    game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
    source = _make_unit(
        "Warrior Alpha",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        save=4,
    )
    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008408004", name="Piercing Talons")
    bearer, other = _bearer_and_other_models(source)
    assert bearer is not None
    assert other is not None

    profile = _make_profile(ap=0, melee=False)
    crit_save = profile._save_with_tracking(
        target.models[0],
        {
            "attacker_model": other,
            "attacker_unit": source,
            "target_unit": target,
            "crit_wound": True,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(crit_save.get("ap_modifier", 0) or 0) == -1
    assert any("Piercing Talons" in str(effect) for effect in list(crit_save.get("special_effects", []) or []))

    normal_save = profile._save_with_tracking(
        target.models[0],
        {
            "attacker_model": other,
            "attacker_unit": source,
            "target_unit": target,
            "crit_wound": False,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(normal_save.get("ap_modifier", 0) or 0) == 0

    bearer.wounds = 0

    after_death = profile._save_with_tracking(
        target.models[0],
        {
            "attacker_model": other,
            "attacker_unit": source,
            "target_unit": target,
            "crit_wound": True,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(after_death.get("ap_modifier", 0) or 0) == 0


def test_adrenalised_onslaught_extends_pile_in_and_consolidate_while_bearer_lives():
    game, tyr_army, _enemy_army, _tyr_player, _enemy_player = _build_game()
    source = _make_unit(
        "Warrior Alpha",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        model_count=2,
    )
    tyr_army.add_unit(source)
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008408005", name="Adrenalised Onslaught")
    bearer, _other = _bearer_and_other_models(source)
    assert bearer is not None

    assert float(source.get_fight_phase_move_distance_override("pile_in") or 0.0) == 6.0
    assert float(source.get_fight_phase_move_distance_override("consolidate") or 0.0) == 6.0

    bearer.wounds = 0

    assert source.get_fight_phase_move_distance_override("pile_in") is None
    assert source.get_fight_phase_move_distance_override("consolidate") is None


def test_naturalised_camouflage_queues_battle_round_one_selection_for_nearby_endless_multitude_units():
    game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tervigon",
        keywords=["TYRANIDS", "MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    near_a = _make_unit("Termagants A", keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"], faction_keywords=["TYRANIDS"])
    near_b = _make_unit("Termagants B", keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"], faction_keywords=["TYRANIDS"])
    near_c = _make_unit("Hormagaunts A", keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"], faction_keywords=["TYRANIDS"])
    near_d = _make_unit("Hormagaunts B", keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"], faction_keywords=["TYRANIDS"])
    far_endless = _make_unit(
        "Far Termagants",
        keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
    )
    non_endless = _make_unit("Genestealers", keywords=["TYRANIDS", "INFANTRY"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (source, near_a, near_b, near_c, near_d, far_endless, non_endless):
        tyr_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _apply_enhancement(source, enhancement_id="000008408003", name="Naturalised Camouflage")

    _place_unit(game, source, 20.0, 20.0)
    _place_unit(game, near_a, 26.0, 20.0)
    _place_unit(game, near_b, 20.0, 28.0)
    _place_unit(game, near_c, 14.0, 20.0)
    _place_unit(game, near_d, 20.0, 12.0)
    _place_unit(game, far_endless, 42.0, 20.0)
    _place_unit(game, non_endless, 26.0, 26.0)
    _place_unit(game, enemy, 50.0, 20.0)
    game.rebuild_entity_registry()

    tyr_army.tyranids_detachments.on_battle_round_start(1, game=game)

    request = _find_request(game, battle_round=1)
    assert str(getattr(request, "player_id", "") or "") == str(tyr_player.id)
    assert str((request.context or {}).get("ability", "") or "") == "naturalised_camouflage"
    assert len(list(getattr(request, "options", []) or [])) == 15

    candidate_ids = {str(v or "") for v in list((request.context or {}).get("candidate_unit_ids", []) or [])}
    assert candidate_ids == {
        str(get_entity_id(near_a) or ""),
        str(get_entity_id(near_b) or ""),
        str(get_entity_id(near_c) or ""),
        str(get_entity_id(near_d) or ""),
    }

    selected_sets = {
        tuple(
            sorted(
                str(v or "").strip()
                for v in list((dict(getattr(option, "payload", {}) or {}).get("selected_unit_ids") or []))
                if str(v or "").strip()
            )
        )
        for option in list(getattr(request, "options", []) or [])
    }
    assert (
        tuple(
            sorted(
                [
                    str(get_entity_id(near_a) or ""),
                    str(get_entity_id(near_b) or ""),
                    str(get_entity_id(near_c) or ""),
                ]
            )
        )
        in selected_sets
    )
    assert (str(get_entity_id(far_endless) or ""),) not in selected_sets
    assert (str(get_entity_id(non_endless) or ""),) not in selected_sets


def test_naturalised_camouflage_selected_units_gain_ranged_cover_until_end_of_round():
    game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
    source = _make_unit(
        "Tervigon",
        keywords=["TYRANIDS", "MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    selected_a = _make_unit(
        "Termagants A",
        keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
        save=4,
    )
    selected_b = _make_unit(
        "Hormagaunts A",
        keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
        save=4,
    )
    unselected = _make_unit(
        "Termagants B",
        keywords=["TYRANIDS", "INFANTRY", "ENDLESS MULTITUDE"],
        faction_keywords=["TYRANIDS"],
        save=4,
    )
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (source, selected_a, selected_b, unselected):
        tyr_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _apply_enhancement(source, enhancement_id="000008408003", name="Naturalised Camouflage")

    _place_unit(game, source, 20.0, 20.0)
    _place_unit(game, selected_a, 26.0, 20.0)
    _place_unit(game, selected_b, 20.0, 28.0)
    _place_unit(game, unselected, 14.0, 20.0)
    _place_unit(game, enemy, 50.0, 20.0)
    game.rebuild_entity_registry()

    tyr_army.tyranids_detachments.on_battle_round_start(1, game=game)
    request = _find_request(game, battle_round=1)
    option = _option_with_selected_ids(
        request,
        [str(get_entity_id(selected_a) or ""), str(get_entity_id(selected_b) or "")],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
    )

    assert _validate_choose_quarry(game, request, result) == ()
    _apply_choose_quarry(game, request, result)

    source_id = str(get_entity_id(source) or "")
    selected_entries = list(selected_a.special_rules.get("bearer_unit_benefit_of_cover", []) or [])
    assert any(
        isinstance(entry, dict)
        and str(entry.get("enhancement_key", "") or "").strip().lower() == "naturalised_camouflage"
        and str(entry.get("source_unit_id", "") or "").strip() == source_id
        for entry in selected_entries
    )
    assert not any(
        isinstance(entry, dict)
        and str(entry.get("enhancement_key", "") or "").strip().lower() == "naturalised_camouflage"
        for entry in list(unselected.special_rules.get("bearer_unit_benefit_of_cover", []) or [])
    )

    ranged_profile = _make_profile(ap=0, melee=False)
    melee_profile = _make_profile(ap=0, melee=True)

    selected_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": selected_a,
        "mortal_wound": False,
    }
    selected_ranged = ranged_profile._save_with_tracking(
        selected_a.models[0],
        selected_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(selected_attack.get("benefit_of_cover", False))
    assert selected_ranged["saved"] is True

    unselected_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": unselected,
        "mortal_wound": False,
    }
    unselected_ranged = ranged_profile._save_with_tracking(
        unselected.models[0],
        unselected_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(unselected_attack.get("benefit_of_cover", False))
    assert unselected_ranged["saved"] is False

    melee_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": selected_a,
        "mortal_wound": False,
    }
    melee_result = melee_profile._save_with_tracking(
        selected_a.models[0],
        melee_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(melee_attack.get("benefit_of_cover", False))
    assert melee_result["saved"] is False

    tyr_army.tyranids_detachments.on_battle_round_start(2, game=game)

    cleared_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": selected_a,
        "mortal_wound": False,
    }
    cleared_result = ranged_profile._save_with_tracking(
        selected_a.models[0],
        cleared_attack,
        ap=0,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(cleared_attack.get("benefit_of_cover", False))
    assert cleared_result["saved"] is False
    assert not any(
        isinstance(entry, dict)
        and str(entry.get("enhancement_key", "") or "").strip().lower() == "naturalised_camouflage"
        for entry in list(selected_a.special_rules.get("bearer_unit_benefit_of_cover", []) or [])
    )
    assert not any(
        str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "naturalised_camouflage"
        and int((getattr(req, "context", {}) or {}).get("battle_round", 0) or 0) == 2
        for req in list(game.decision_queue.list() or [])
    )
