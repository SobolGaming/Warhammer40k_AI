from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        move: int = 6,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "The Lost Brethren")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _make_profile(*, is_melee: bool, skill: str = "3+", strength: str = "5", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_wargear(name: str = "Chainsword") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _ranged_wargear(name: str = "Bolt Pistol") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "12",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _destroy_unit(unit: Unit, game_map) -> object:
    model = unit.models[0]
    model.wounds = 0
    model.die(game_map=game_map)
    return model


def test_lost_brethren_stratagem_descriptors_registered():
    expected = {
        "000009187004": ("Final Retribution", "fight_on_death_after_attacks"),
        "000009187005": ("Furious Onslaught", "pile_in_distance_override"),
        "000009187002": ("Glorious Sacrifice", "sticky_objective"),
        "000009187006": ("Lost to Rage", "melee_weapon_bonus_and_conditional_hazardous"),
        "000009187007": ("Wrathful Rampage", "charge_after_advance_and_conditional_shoot_after_advance"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_lost_brethren_phase_start_reactions_queue_fight_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    full_strength = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    bloodied = _make_unit(
        "Death Company Intercessors",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bloodied.models[0].wounds = 3

    sm_army.add_unit(full_strength)
    sm_army.add_unit(bloodied)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, full_strength, 10.0, 10.0)
    _deploy_unit(game, bloodied, 13.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sm_player.stratagems) == {"FURIOUS ONSLAUGHT", "LOST TO RAGE"}


def test_final_retribution_reaction_sets_dynamic_fight_on_death_threshold():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        wounds=4,
    )
    chaplain = _make_unit(
        "Death Company Chaplain",
        keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=4,
    )
    sm_army.add_unit(death_company)
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, chaplain, 30.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[death_company])
    pending = _pending_by_name(sm_player.stratagems, "FINAL RETRIBUTION")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "FINAL RETRIBUTION",
        unit=death_company,
        attacking_unit=enemy,
        target_units=[death_company],
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    model = death_company.models[0]
    rule = death_company.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4

    chaplain.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    rule_with_support = death_company.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(rule_with_support, dict)
    assert int(rule_with_support.get("threshold", 0) or 0) == 3

    death_company.round_state.fought_this_phase = False
    death_company._last_destroyed_by_weapon_profile = _make_profile(is_melee=True, strength="6", damage="2")
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
        model._wounds = 0
        death_company._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(death_company, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models


def test_furious_onslaught_sets_random_pile_in_distance_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(death_company)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "FURIOUS ONSLAUGHT") is not None

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=2):
        ok = sm_player.stratagems.use(
            "FURIOUS ONSLAUGHT",
            unit=death_company,
            phase_name="Fight phase",
            dequeue=True,
        )
    assert ok is True
    sr = dict(getattr(death_company, "special_rules", {}) or {})
    assert float(sr.get("bearer_unit_pile_in_distance_override", 0.0) or 0.0) == 5.0

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    cleared = dict(getattr(death_company, "special_rules", {}) or {})
    assert "bearer_unit_pile_in_distance_override" not in cleared


def test_furious_onslaught_becomes_six_inches_with_chaplain_support():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    chaplain = _make_unit(
        "Chaplain",
        keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(death_company)
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, chaplain, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use(
        "FURIOUS ONSLAUGHT",
        unit=death_company,
        phase_name="Fight phase",
    )
    assert ok is True
    sr = dict(getattr(death_company, "special_rules", {}) or {})
    assert float(sr.get("bearer_unit_pile_in_distance_override", 0.0) or 0.0) == 6.0


def test_glorious_sacrifice_queues_on_destroyed_unit_and_makes_objective_sticky():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(death_company)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    assert objective.location.sticky_controller is None
    _destroy_unit(death_company, game.map)
    pending = _pending_by_name(sm_player.stratagems, "GLORIOUS SACRIFICE")
    assert pending is not None
    assert objective in list(pending.get("objective_candidates", []) or [])

    ok = sm_player.stratagems.use(
        "GLORIOUS SACRIFICE",
        unit=death_company,
        objective=objective,
        dequeue=True,
    )
    assert ok is True
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_lost_to_rage_applies_melee_bonuses_and_hazardous_without_chaplain():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    death_company.models[0].wounds = 3
    death_company.models[0].wargear = [_melee_wargear("Chainsword"), _ranged_wargear("Bolt Pistol")]
    sm_army.add_unit(death_company)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use(
        "LOST TO RAGE",
        unit=death_company,
        phase_name="Fight phase",
    )
    assert ok is True

    model = death_company.models[0]
    attacks_bonus, _ = model.get_temporary_weapon_attacks_bonus("Chainsword")
    strength_bonus, _ = model.get_temporary_weapon_strength_bonus("Chainsword")
    ap_bonus, _ = model.get_temporary_weapon_ap_bonus("Chainsword")
    keywords = model.get_temporary_weapon_keyword_bonuses("Chainsword")
    assert attacks_bonus == 1
    assert strength_bonus == 1
    assert ap_bonus == 1
    assert any(str(entry.get("keyword", "") or "").upper() == "HAZARDOUS" for entry in keywords)


def test_lost_to_rage_skips_hazardous_with_chaplain_support():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    chaplain = _make_unit(
        "Chaplain",
        keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    death_company.models[0].wounds = 3
    death_company.models[0].wargear = [_melee_wargear("Chainsword")]
    sm_army.add_unit(death_company)
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, chaplain, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use(
        "LOST TO RAGE",
        unit=death_company,
        phase_name="Fight phase",
    )
    assert ok is True
    keywords = death_company.models[0].get_temporary_weapon_keyword_bonuses("Chainsword")
    assert not any(str(entry.get("keyword", "") or "").upper() == "HAZARDOUS" for entry in keywords)


def test_wrathful_rampage_queues_after_advance_and_grants_charge_only_without_support():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(death_company)
    _deploy_unit(game, death_company, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    death_company.round_state.advanced_this_round = True
    game.event_system.publish("unit_move_ended", unit=death_company, action="advance")
    pending = _pending_by_name(sm_player.stratagems, "WRATHFUL RAMPAGE")
    assert pending is not None

    assert death_company.has_advance_and_charge() is False
    assert death_company.has_advance_and_shoot() is False

    ok = sm_player.stratagems.use(
        "WRATHFUL RAMPAGE",
        unit=death_company,
        action="advance",
        dequeue=True,
    )
    assert ok is True
    assert death_company.has_advance_and_charge() is True
    assert death_company.has_advance_and_shoot() is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert death_company.has_advance_and_charge() is False


def test_wrathful_rampage_grants_shoot_and_charge_after_advance_with_support():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    death_company = _make_unit(
        "Death Company Marines",
        keywords=["INFANTRY", "DEATH COMPANY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    chaplain = _make_unit(
        "Chaplain",
        keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(death_company)
    sm_army.add_unit(chaplain)
    _deploy_unit(game, death_company, 10.0, 10.0)
    _deploy_unit(game, chaplain, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    death_company.round_state.advanced_this_round = True

    ok = sm_player.stratagems.use(
        "WRATHFUL RAMPAGE",
        unit=death_company,
        action="advance",
        phase_name="Movement phase",
    )
    assert ok is True
    assert death_company.has_advance_and_charge() is True
    assert death_company.has_advance_and_shoot() is True
