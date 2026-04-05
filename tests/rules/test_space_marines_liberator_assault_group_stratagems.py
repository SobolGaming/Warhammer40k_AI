from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


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

    sm_army = Army("Space Marines", "Liberator Assault Group")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
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
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 1.5), float(y), 0.0, 0.0)
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


def _melee_wargear(name: str = "Power Sword") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "1",
            "description": "",
        }
    )


def test_liberator_assault_group_stratagem_descriptors_registered():
    expected = {
        "000008375006": ("Aggressive Onslaught", "choose_shoot_or_charge_after_advance_or_both_with_battleshock"),
        "000008375005": ("Red Rampage", "choose_lance_or_lethal_hits_or_both_with_battleshock_for_melee_weapons"),
        "000008375007": ("Relentless Assault", "choose_shoot_or_charge_after_fall_back_or_both_with_battleshock"),
        "000008375004": ("Savage Echoes", "choose_strength_or_attacks_or_both_with_battleshock_for_melee_weapons"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_aggressive_onslaught_queues_after_advance_and_grants_selected_permission():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    intercessors.round_state.advanced_this_round = True
    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=intercessors, action="advance")

    pending = _pending_by_name(sm_player.stratagems, "AGGRESSIVE ONSLAUGHT")
    assert pending is not None

    ok = sm_player.stratagems.use("AGGRESSIVE ONSLAUGHT", unit=intercessors, choice="SHOOT", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False)
    assert intercessors.can_shoot_after_advance(profile) is True
    assert intercessors.can_charge_after_advance() is False
    assert bool(intercessors.is_battle_shocked()) is False


def test_relentless_assault_red_thirst_grants_both_permissions_and_battleshock():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    jump_pack_unit = _make_unit(
        "Jump Pack Intercessors",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(jump_pack_unit)
    _deploy_unit(game, jump_pack_unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    jump_pack_unit.round_state.fell_back_this_round = True
    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=jump_pack_unit, action="fall_back")

    pending = _pending_by_name(sm_player.stratagems, "RELENTLESS ASSAULT")
    assert pending is not None

    ok = sm_player.stratagems.use("RELENTLESS ASSAULT", unit=jump_pack_unit, choice="RED_THIRST", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False)
    assert jump_pack_unit.can_shoot_after_fall_back(profile) is True
    assert jump_pack_unit.can_charge_after_fall_back() is True
    assert bool(jump_pack_unit.is_battle_shocked()) is True


def test_red_rampage_queues_and_applies_selected_melee_keyword_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    assault_unit = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    assault_unit.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(assault_unit)
    _deploy_unit(game, assault_unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "RED RAMPAGE")
    assert pending is not None

    ok = sm_player.stratagems.use("RED RAMPAGE", unit=assault_unit, choice="LETHAL_HITS", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = assault_unit.models[0].get_temporary_weapon_keyword_bonuses("Power Sword")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(assault_unit.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or []) == []


def test_savage_echoes_queues_after_enemy_charge_and_applies_red_thirst_weapon_bonuses():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    defenders.models[0].wargear = [_melee_wargear()]
    chargers = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(defenders)
    enemy_army.add_unit(chargers)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, chargers, 12.0, 10.0)
    game.rebuild_entity_registry()

    chargers.round_state.charge_target_ids = {str(get_entity_id(defenders) or "")}
    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=chargers, action="charge")

    pending = _pending_by_name(sm_player.stratagems, "SAVAGE ECHOES")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "SAVAGE ECHOES",
        unit=defenders,
        enemy_unit=chargers,
        choice="RED_THIRST",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    attacks_bonus, attack_reasons = defenders.models[0].get_temporary_weapon_attacks_bonus("Power Sword")
    strength_bonus, strength_reasons = defenders.models[0].get_temporary_weapon_strength_bonus("Power Sword")
    assert int(attacks_bonus or 0) == 1
    assert int(strength_bonus or 0) == 1
    assert any("SAVAGE ECHOES" in str(reason).upper() for reason in list(attack_reasons or []))
    assert any("SAVAGE ECHOES" in str(reason).upper() for reason in list(strength_reasons or []))
    assert bool(defenders.is_battle_shocked()) is True

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert defenders.models[0].get_temporary_weapon_attacks_bonus("Power Sword")[0] == 0
    assert defenders.models[0].get_temporary_weapon_strength_bonus("Power Sword")[0] == 0
