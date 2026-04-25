from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        toughness: int = 4,
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
                "M": "6",
                "T": str(int(toughness)),
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
    toughness: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Librarius Conclave")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _choose_discipline(game: Game, sm_army: Army, sm_player: Player, key: str) -> None:
    ok = sm_army.space_marines_detachments.select_librarius_psychic_discipline(
        key,
        battle_round=game.turn,
        player_id=sm_player.id,
    )
    assert ok


def _make_profile(*, is_melee: bool, strength: str = "4", skill: str = "3+", damage: str = "1") -> WargearProfile:
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


def _melee_wargear(name: str = "Force Sword") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_librarius_phase_items_are_not_available_without_bound_candidates():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    librarian.models[0].wargear = [_ranged_wargear(), _melee_wargear("Force Weapon")]
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(librarian)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, librarian, 10.0, 10.0)
    _deploy_unit(game, intercessors, 16.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    def available_items(name: str):
        return [
            item
            for item in sm_player.stratagems.get_phase_stratagem_items()
            if str(item.get("name", "") or "").strip().upper() == name
            and bool(item.get("available", False))
        ]

    def assert_bound_available_item(name: str) -> None:
        items = available_items(name)
        assert items
        assert all(list((item.get("context") or {}).get("candidates") or []) for item in items)

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert_bound_available_item("SENSORY ASSAULT")
    sensory_context = available_items("SENSORY ASSAULT")[0].get("context") or {}
    assert list(sensory_context.get("enemy_candidates") or [])

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert_bound_available_item("ASSAIL")
    assail_context = available_items("ASSAIL")[0].get("context") or {}
    assert list(assail_context.get("enemy_candidates") or [])
    assert_bound_available_item("PRESCIENT PRECISION")

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert_bound_available_item("IRON ARM")


def test_librarius_conclave_stratagem_descriptors_registered():
    expected = {
        "000009791006": ("Assail", "psyker_mortal_wound_burst_with_conditional_telekinesis_bonus"),
        "000009791004": ("Fiery Shield", "defensive_hit_penalty_and_conditional_melee_hazardous_on_targeting"),
        "000009791005": ("Iron Arm", "melee_strength_bonus_and_conditional_biomancy_bonus"),
        "000009791007": ("Prescient Precision", "ranged_lethal_hits_and_conditional_divination_ignores_cover"),
        "000009791002": ("Sensory Assault", "pin_enemy_unit_and_conditional_telepathy_battleshock"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_sensory_assault_queues_pins_and_forces_telepathy_battleshock():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(librarian)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, librarian, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()
    _choose_discipline(game, sm_army, sm_player, "TELEPATHY")

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    pending = _pending_by_name(sm_player.stratagems, "SENSORY ASSAULT")
    assert pending is not None

    enemy.force_battle_shock_test = Mock()
    ok = sm_player.stratagems.use("SENSORY ASSAULT", unit=librarian, enemy_unit=enemy, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    enemy_sr = dict(getattr(enemy, "special_rules", {}) or {})
    assert bool(enemy_sr.get("pinned_active")) is True
    assert int(enemy_sr.get("pinned_move_penalty", 0) or 0) == -2
    assert int(enemy_sr.get("pinned_charge_penalty", 0) or 0) == -2
    enemy.force_battle_shock_test.assert_called_once_with(1, modifier=-1, source="SENSORY ASSAULT")

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    enemy_sr_after = dict(getattr(enemy, "special_rules", {}) or {})
    assert bool(enemy_sr_after.get("pinned_active")) is False


def test_assail_excludes_lone_operative_and_uses_telekinesis_bonus():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    target_enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    lone_enemy = _make_unit(
        "Enemy Lone Operative",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    lone_enemy.has_lone_operative = lambda: True
    sm_army.add_unit(librarian)
    enemy_army.add_unit(target_enemy)
    enemy_army.add_unit(lone_enemy)
    _deploy_unit(game, librarian, 10.0, 10.0)
    _deploy_unit(game, target_enemy, 20.0, 10.0)
    _deploy_unit(game, lone_enemy, 18.0, 12.0)
    game.rebuild_entity_registry()
    _choose_discipline(game, sm_army, sm_player, "TELEKINESIS")

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "ASSAIL")
    assert pending is not None
    enemy_candidates = list(pending.get("enemy_candidates") or [])
    assert target_enemy in enemy_candidates
    assert lone_enemy not in enemy_candidates

    captured = {}

    def _capture_mortals(enemy_unit, mortal_wounds, game_map=None):
        captured["enemy"] = enemy_unit
        captured["mortal_wounds"] = int(mortal_wounds or 0)
        captured["game_map"] = game_map

    librarian._apply_mortal_wounds_to_unit = _capture_mortals
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[3, 3, 4, 2, 1, 6]):
        ok = sm_player.stratagems.use("ASSAIL", unit=librarian, enemy_unit=target_enemy, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert captured["enemy"] is target_enemy
    assert int(captured["mortal_wounds"] or 0) == 4
    assert captured["game_map"] is game.map


def test_prescient_precision_grants_keywords_and_cleans_up_with_divination():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    librarian.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(librarian)
    _deploy_unit(game, librarian, 10.0, 10.0)
    game.rebuild_entity_registry()
    _choose_discipline(game, sm_army, sm_player, "DIVINATION")

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "PRESCIENT PRECISION")
    assert pending is not None

    ok = sm_player.stratagems.use("PRESCIENT PRECISION", unit=librarian, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = librarian.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(librarian.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []


def test_iron_arm_grants_biomancy_strength_bonus_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [_melee_wargear("Astartes Blade")]
    sm_army.add_unit(librarian)
    sm_army.add_unit(intercessors)
    _deploy_unit(game, librarian, 10.0, 10.0)
    _deploy_unit(game, intercessors, 16.0, 10.0)
    game.rebuild_entity_registry()
    _choose_discipline(game, sm_army, sm_player, "BIOMANCY")

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "IRON ARM")
    assert pending is not None

    ok = sm_player.stratagems.use("IRON ARM", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    strength_bonus, reasons = intercessors.models[0].get_temporary_weapon_strength_bonus("Astartes Blade")
    assert int(strength_bonus or 0) == 2
    assert any("IRON ARM" in str(reason).upper() for reason in list(reasons or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.models[0].get_temporary_weapon_strength_bonus("Astartes Blade")[0] == 0


def test_fiery_shield_reaction_applies_hit_penalty_and_pyromancy_hazardous_then_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    librarian = _make_unit(
        "Librarian",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    defender = _make_unit(
        "Bladeguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.models[0].wargear = [_melee_wargear("Enemy Blade")]
    sm_army.add_unit(librarian)
    sm_army.add_unit(defender)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, librarian, 10.0, 10.0)
    _deploy_unit(game, defender, 16.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    _choose_discipline(game, sm_army, sm_player, "PYROMANCY")

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[defender])
    pending = _pending_by_name(sm_player.stratagems, "FIERY SHIELD")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "FIERY SHIELD",
        unit=defender,
        attacking_unit=enemy,
        target_units=[defender],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    hazardous_sources = defender.enemy_melee_weapons_hazardous_while_targeted()
    assert any("FIERY SHIELD" in str(source).upper() for source in list(hazardous_sources or []))

    profile = _make_profile(is_melee=True, skill="3+")
    after_use = profile._hit_target_with_tracking(
        defender,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(after_use.get("hit"))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert defender.enemy_melee_weapons_hazardous_while_targeted() == []

    after_cleanup = profile._hit_target_with_tracking(
        defender,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_cleanup.get("hit"))
