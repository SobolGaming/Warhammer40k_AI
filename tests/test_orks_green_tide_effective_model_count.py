from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "2",
    ):
        slug = str(name or "unit").lower().replace(" ", "_")
        self.id = f"mock_{slug}"
        self.name = name
        faction_kw = [str(k).upper() for k in list(faction_keywords or [])]
        self.faction_data = {"name": "Orks" if "ORKS" in faction_kw else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1, wounds: str = "2") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0

    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"failed to place {getattr(unit, 'name', 'Unit')}"


def _set_phase(game: Game, *, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    if not list(getattr(leader, "can_be_attached_to", []) or []):
        leader.can_be_attached_to = ["BOYZ"]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ORK",
        detachment="Green Tide",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _stratagem_name_by_id(player: Player, stratagem_id: str, *, fallback_name: str) -> str:
    target_id = str(stratagem_id or "")
    for stratagem in list(player.stratagems.available or []):
        if str(getattr(stratagem, "id", "") or "") == target_id:
            return str(getattr(stratagem, "name", "") or fallback_name)
    return str(fallback_name or "")


def _make_profile(*, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "2",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _run_save(*, target_model, attacker_model, target_unit, is_ranged: bool, roll_value: int) -> dict:
    profile = _make_profile(is_ranged=is_ranged)
    return profile._save_with_tracking(
        target_model,
        {"attacker_model": attacker_model, "target_unit": target_unit},
        ap=-3,
        roll_value=roll_value,
        allow_rerolls=False,
        log_roll=False,
    )


def test_green_tide_effective_model_count_helper_respects_scope_distance_and_expiry():
    first = _make_unit("Boyz Alpha", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    second = _make_unit("Boyz Beta", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[first, second],
        enemy_units=[enemy],
    )
    _deploy_unit(game, first, 10.0, 10.0)
    _deploy_unit(game, second, 22.0, 10.0)

    first.special_rules = dict(getattr(first, "special_rules", {}) or {})
    first.special_rules["orks_temp_effects"] = [
        {
            "id": "test:effective_floor",
            "source": "test",
            "detachment": "green_tide",
            "effect": "effective_model_count_floor",
            "value": 10,
            "effective_model_count_scopes": ["detachment", "enhancement"],
            "while_within_distance": 6.0,
            "while_within_distance_of_unit_id": str(get_entity_id(second) or ""),
            "expires_mode": "next_command_phase",
            "expires_scope": "owner_command_phase",
            "turn_owner_id": str(ork_player.id),
            "turn": int(game.turn),
        }
    ]

    assert first.orks_effective_model_count_for_evaluation("detachment", game=game, game_map=game.map) == 10
    assert first.orks_effective_model_count_for_evaluation("enhancement", game=game, game_map=game.map) == 10
    assert first.orks_effective_model_count_for_evaluation("stratagem", game=game, game_map=game.map) == 5

    for model in list(second.models or []):
        model.set_location(30.0, 10.0, 0.0, 0.0)
    assert first.orks_effective_model_count_for_evaluation("detachment", game=game, game_map=game.map) == 5

    for model in list(second.models or []):
        model.set_location(14.0, 10.0, 0.0, 0.0)
    ork_army.orks_detachments.clear_orks_next_command_phase_effects(player=ork_player)
    assert first.orks_effective_model_count_for_evaluation("detachment", game=game, game_map=game.map) == 5


def test_raucous_warcaller_applies_to_detachment_and_stratagem_but_not_enhancement():
    boyz = _make_unit("Boyz Mob", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    warboss = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, _ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[boyz, warboss],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _attach_leader(boyz, warboss)
    _apply_enhancement(warboss, enhancement_id="000008881005", enhancement_name="Raucous Warcaller")

    assert boyz.orks_effective_model_count_for_evaluation("detachment", game=game, game_map=game.map) == 10
    assert boyz.orks_effective_model_count_for_evaluation("stratagem", game=game, game_map=game.map) == 10
    assert boyz.orks_effective_model_count_for_evaluation("enhancement", game=game, game_map=game.map) == 6


def test_braggin_rights_applies_effective_ten_and_stops_when_units_leave_range():
    first = _make_unit("Boyz One", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    second = _make_unit("Boyz Two", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[first, second],
        enemy_units=[enemy],
    )
    _deploy_unit(game, first, 10.0, 10.0)
    _deploy_unit(game, second, 22.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008882004", fallback_name="BRAGGIN' RIGHTS")
    assert ork_player.stratagems.use(
        strat_name,
        target_units=[first, second],
        phase_name="Command phase",
    )

    assert first.orks_effectively_counts_as_ten_models("detachment", game=game, game_map=game.map) is True
    assert second.orks_effectively_counts_as_ten_models("enhancement", game=game, game_map=game.map) is True
    assert first.orks_effectively_counts_as_ten_models("stratagem", game=game, game_map=game.map) is True

    for model in list(second.models or []):
        model.set_location(30.0, 10.0, 0.0, 0.0)
    assert first.orks_effectively_counts_as_ten_models("detachment", game=game, game_map=game.map) is False
    assert second.orks_effectively_counts_as_ten_models("enhancement", game=game, game_map=game.map) is False


def test_mob_mentality_uses_synthetic_ten_from_braggin_rights():
    first = _make_unit("Boyz One", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    second = _make_unit("Boyz Two", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=5)
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[first, second],
        enemy_units=[enemy],
    )
    _deploy_unit(game, first, 10.0, 10.0)
    _deploy_unit(game, second, 22.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008882004", fallback_name="BRAGGIN' RIGHTS")
    assert ork_player.stratagems.use(
        strat_name,
        target_units=[first, second],
        phase_name="Command phase",
    )

    save_result = _run_save(
        target_model=first.models[0],
        attacker_model=enemy.models[0],
        target_unit=first,
        is_ranged=True,
        roll_value=5,
    )
    assert save_result.get("save_type") == "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 5
    assert any("Mob Mentality" in str(item) for item in list(save_result.get("special_effects", []) or []))


def test_bloodthirsty_belligerence_charge_reroll_requires_enhancement_effective_ten():
    boyz = _make_unit("Boyz Mob", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=8)
    warboss = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, _ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[boyz, warboss],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _attach_leader(boyz, warboss)
    _apply_enhancement(warboss, enhancement_id="000008881002", enhancement_name="Bloodthirsty Belligerence")

    assert boyz.can_reroll_advance_roll() is True
    assert boyz.can_reroll_charge_roll(game=game) is False

    boyz.special_rules = dict(getattr(boyz, "special_rules", {}) or {})
    boyz.special_rules["orks_temp_effects"] = [
        {
            "id": "test:bloodthirsty:enhancement_floor",
            "source": "test",
            "detachment": "green_tide",
            "effect": "effective_model_count_floor",
            "value": 10,
            "effective_model_count_scopes": ["enhancement"],
        }
    ]
    assert boyz.can_reroll_charge_roll(game=game) is True


def test_ferocious_show_off_strength_bonus_switches_by_enhancement_effective_count():
    boyz = _make_unit("Boyz Mob", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=8)
    warboss = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, _ork_player, _enemy_player, ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[boyz, warboss],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _attach_leader(boyz, warboss)
    _apply_enhancement(warboss, enhancement_id="000008881004", enhancement_name="Ferocious Show Off")

    bonus, source = ork_army.orks_detachments.green_tide_ferocious_show_off_melee_strength_bonus(
        warboss.models[0],
        attack_type="melee",
        game=game,
    )
    assert int(bonus) == 1
    assert str(source) == "Ferocious Show Off"

    boyz.special_rules = dict(getattr(boyz, "special_rules", {}) or {})
    boyz.special_rules["orks_temp_effects"] = [
        {
            "id": "test:ferocious:enhancement_floor",
            "source": "test",
            "detachment": "green_tide",
            "effect": "effective_model_count_floor",
            "value": 10,
            "effective_model_count_scopes": ["enhancement"],
        }
    ]
    bonus, _source = ork_army.orks_detachments.green_tide_ferocious_show_off_melee_strength_bonus(
        warboss.models[0],
        attack_type="melee",
        game=game,
    )
    assert int(bonus) == 3


def test_competitive_streak_uses_effective_model_count_branch():
    def _run_case(*, with_raucous: bool) -> dict:
        boyz = _make_unit("Boyz Mob", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=8)
        leader = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        game, ork_player, _enemy_player, _ork_army = _build_game(
            detachment="Green Tide",
            ork_units=[boyz, leader],
            enemy_units=[enemy],
        )
        _deploy_unit(game, boyz, 10.0, 10.0)
        _attach_leader(boyz, leader)
        if with_raucous:
            _apply_enhancement(leader, enhancement_id="000008881005", enhancement_name="Raucous Warcaller")
        _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

        strat_name = _stratagem_name_by_id(ork_player, "000008882002", fallback_name="COMPETITIVE STREAK")
        assert ork_player.stratagems.use(strat_name, unit=boyz, phase_name="Fight phase")
        return boyz.get_unit_wound_reroll_modifiers(
            "melee",
            target=enemy,
            attacker_model=boyz.models[0],
        )

    without_raucous = _run_case(with_raucous=False)
    assert bool(without_raucous.get("reroll_wound_ones")) is True
    assert bool(without_raucous.get("reroll_wound_full")) is False

    with_raucous = _run_case(with_raucous=True)
    assert bool(with_raucous.get("reroll_wound_full")) is True


def test_tide_of_muscle_uses_effective_model_count_branch():
    def _run_case(*, with_raucous: bool) -> tuple[list[tuple[int, str]], bool]:
        boyz = _make_unit("Boyz Mob", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"], model_count=8)
        leader = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER", "WARBOSS"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        game, ork_player, _enemy_player, _ork_army = _build_game(
            detachment="Green Tide",
            ork_units=[boyz, leader],
            enemy_units=[enemy],
        )
        _deploy_unit(game, boyz, 10.0, 10.0)
        _attach_leader(boyz, leader)
        if with_raucous:
            _apply_enhancement(leader, enhancement_id="000008881005", enhancement_name="Raucous Warcaller")
        _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)

        strat_name = _stratagem_name_by_id(ork_player, "000008882006", fallback_name="TIDE OF MUSCLE")
        assert ork_player.stratagems.use(strat_name, unit=boyz, phase_name="Charge phase")
        return (
            game._collect_charge_modifiers(boyz, target_unit=enemy),
            boyz.can_reroll_charge_roll(target_unit=enemy, game=game),
        )

    base_mods, base_reroll = _run_case(with_raucous=False)
    assert any(int(value) == 1 for value, _source in list(base_mods or []))
    assert base_reroll is False

    enhanced_mods, enhanced_reroll = _run_case(with_raucous=True)
    assert any(int(value) == 1 for value, _source in list(enhanced_mods or []))
    assert enhanced_reroll is True


def test_green_tide_tool_descriptors_registered_for_new_rules():
    expected_stratagems = {
        "000008882004": "BRAGGIN' RIGHTS",
        "000008882002": "COMPETITIVE STREAK",
        "000008882006": "TIDE OF MUSCLE",
    }
    for stratagem_id, name in expected_stratagems.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name

    expected_enhancements = {
        "000008881002": "Bloodthirsty Belligerence",
        "000008881004": "Ferocious Show Off",
        "000008881005": "Raucous Warcaller",
    }
    for enhancement_id, name in expected_enhancements.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
