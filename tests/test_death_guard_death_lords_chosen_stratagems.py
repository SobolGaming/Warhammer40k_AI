from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        faction_tokens = {str(token).upper() for token in list(faction_keywords or [])}
        self.faction_data = {"name": "Death Guard" if "DEATH GUARD" in faction_tokens else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count))
        model_label = "Test Model" if count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{count} {model_label}"}]
        self.datasheets_models_cost = [{"description": f"{count} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: str = "4",
    toughness: str = "5",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            model_count=quantity,
        ),
        quantity=int(quantity),
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army("Death Guard", "Death Lord's Chosen")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_player.command_points = 10
    enemy_player.command_points = 10
    dg_army.configure_rule_managers(force=True)
    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    dg_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, dg_player, enemy_player, dg_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _add_objective(game: Game, x: float, y: float):
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    objective = Objective(
        name="Signal Pox Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )
    game.map.add_objective(objective)
    return objective


def test_blooming_pestilence_adds_three_to_contagion_range_until_end_of_phase():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Blightlord Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("BLOOMING PESTILENCE", unit=terminators, phase_name="Shooting phase")
    assert float(dg_army.nurgles_gift.get_contagion_range(1, source_unit=terminators, game=game, game_map=game.map)) == 6.0

    _set_phase(game, "FIGHT_PHASE", 0)
    assert float(dg_army.nurgles_gift.get_contagion_range(1, source_unit=terminators, game=game, game_map=game.map)) == 3.0


def test_grim_reapers_only_rerolls_melee_hits_against_non_monster_non_vehicle_targets():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Deathshroud Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
    )
    infantry_target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    vehicle_target = _make_unit(
        "Enemy Tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        toughness="9",
    )
    dg_army.add_unit(terminators)
    enemy_army.add_unit(infantry_target)
    enemy_army.add_unit(vehicle_target)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, infantry_target, 11.0, 10.0)
    _deploy_unit(game, vehicle_target, 12.0, 10.0)

    game.turn = 1
    _set_phase(game, "FIGHT_PHASE", 0)
    assert dg_player.stratagems.use("GRIM REAPERS", unit=terminators, phase_name="Fight phase")

    infantry_mods = terminators.get_unit_hit_reroll_modifiers("melee", target=infantry_target, attacker_model=terminators.models[0])
    vehicle_mods = terminators.get_unit_hit_reroll_modifiers("melee", target=vehicle_target, attacker_model=terminators.models[0])
    assert bool(infantry_mods.get("reroll_hit_full"))
    assert not bool(vehicle_mods.get("reroll_hit_full"))


def test_mortarions_teachings_grants_assault_and_heavy_to_ranged_weapons():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Blightlord Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
    )
    for model in list(terminators.models or []):
        model.wargear = [
            SimpleNamespace(
                name="Combi-bolter",
                is_ranged=lambda: True,
                is_melee=lambda: False,
            )
        ]
    dg_army.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("MORTARION'S TEACHINGS", unit=terminators, phase_name="Shooting phase")

    keyword_rules = list(terminators.models[0].get_temporary_weapon_keyword_bonuses("Combi-bolter") or [])
    keywords = {str(entry.get("keyword", "") or "").upper() for entry in keyword_rules}
    assert "ASSAULT" in keywords
    assert "HEAVY" in keywords


def test_sickening_impact_queues_charge_end_reaction_and_caps_mortal_wounds_at_six():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Blightlord Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
        quantity=7,
    )
    enemy = _make_unit(
        "Enemy Monster",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
        wounds="10",
        toughness="10",
    )
    dg_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, "CHARGE_PHASE", 0)
    dg_player.stratagems._on_unit_move_ended(unit=terminators, action="charge")
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "SICKENING IMPACT" for entry in list(pending or []))

    with patch("warhammer40k_ai.rules.stratagems_death_guard.dice_module.get_roll", side_effect=[2, 2, 2, 2, 2, 2, 2]):
        assert dg_player.stratagems.use(
            "SICKENING IMPACT",
            unit=terminators,
            enemy_unit=enemy,
            action="charge",
            phase_name="Charge phase",
            dequeue=True,
        )

    assert int(enemy.models[0].wounds) == 4


def test_signal_pox_afflicts_enemy_units_within_selected_objective_until_next_turn():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    lord = _make_unit(
        "Lord of Virulence",
        keywords=["INFANTRY", "CHARACTER", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    objective = _add_objective(game, 35.0, 10.0)
    dg_army.add_unit(lord)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, lord, 10.0, 10.0)
    _deploy_unit(game, enemy, 35.0, 10.0)

    game.turn = 1
    _set_phase(game, "COMMAND_PHASE", 0)
    assert dg_player.stratagems.use("SIGNAL POX", unit=lord, objective=objective, phase_name="Command phase")

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map)
    assert afflicted is not None
    assert afflicted.key == PLAGUE_RATTLEJOINT.key
    assert int(enemy.toughness) == 4

    game.turn = 2
    game.event_system.publish("phase_start", player=dg_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    assert NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map) is None


def test_undying_spite_queues_reaction_and_grants_fight_on_death_on_four_plus():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Deathshroud Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["DEATH GUARD"],
    )
    attacker = _make_unit(
        "Enemy Assault Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(terminators)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)

    game.turn = 1
    _set_phase(game, "FIGHT_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Fight phase"
    dg_player.stratagems._on_fight_targets_selected(attacking_unit=attacker, target_units=[terminators])
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "UNDYING SPITE" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "UNDYING SPITE",
        unit=terminators,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )

    rule = terminators.get_melee_fight_on_death_after_attacks_rule()
    assert rule is not None
    assert int(rule.get("threshold") or 0) == 4
    assert "UNDYING SPITE" in str(rule.get("source", "") or "").upper()


def test_death_lords_chosen_stratagems_have_tool_descriptors():
    expected = {
        "000010144002": ("Blooming Pestilence", "contagion_range_bonus"),
        "000010144003": ("Grim Reapers", "melee_hit_rerolls_against_non_monster_vehicle"),
        "000010144004": ("Undying Spite", "fight_on_death_on_4_plus"),
        "000010144005": ("Signal Pox", "objective_marker_afflicts_enemy_units"),
        "000010144006": ("Mortarion's Teachings", "grant_ranged_assault_and_heavy"),
        "000010144007": ("Sickening Impact", "charge_end_mortal_wounds"),
    }

    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())

        assert by_id is not None
        assert by_name is not None
        assert by_id == by_name
        assert by_id.name == name
        assert by_id.effect == effect
