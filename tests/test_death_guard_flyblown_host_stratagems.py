from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
                "Sv": "3",
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

    dg_army = Army("Death Guard", "Flyblown Host")
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


def test_droning_horror_rerolls_hit_ones_generally_and_full_at_half_range():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    shooters = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(shooters)
    enemy_army.add_unit(target)
    _deploy_unit(game, shooters, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("DRONING HORROR", unit=shooters, phase_name="Shooting phase")

    weapon_profile = SimpleNamespace(_effective_range_max=lambda _model: 24)
    far_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=shooters.models[0],
        weapon_profile=weapon_profile,
        closest_dist=18.0,
    )
    near_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=shooters.models[0],
        weapon_profile=weapon_profile,
        closest_dist=12.0,
    )

    assert 1 in tuple(far_mods.get("reroll_hit_values", ()) or ())
    assert not bool(far_mods.get("reroll_hit_full"))
    assert bool(near_mods.get("reroll_hit_full"))


def test_eye_of_the_swarm_grants_pistol_to_non_blast_ranged_weapons_only():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    shooters = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    for model in list(shooters.models or []):
        model.wargear = [
            SimpleNamespace(name="Blight Launcher", keywords=[], is_ranged=lambda: True, is_melee=lambda: False),
            SimpleNamespace(name="Plague Mortar", keywords=["BLAST"], is_ranged=lambda: True, is_melee=lambda: False),
        ]
    dg_army.add_unit(shooters)
    _deploy_unit(game, shooters, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("EYE OF THE SWARM", unit=shooters, phase_name="Shooting phase")

    blight_launcher = list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Blight Launcher") or [])
    plague_mortar = list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Plague Mortar") or [])
    assert {str(entry.get("keyword", "") or "").upper() for entry in blight_launcher} == {"PISTOL"}
    assert plague_mortar == []


def test_nauseating_paroxysms_queues_phase_start_reaction_and_forces_battleshock_at_minus_one():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    infantry = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, enemy, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, "FIGHT_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Fight phase"
    dg_player.stratagems._on_phase_start(player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "NAUSEATING PAROXYSMS" for entry in list(pending or []))

    with patch.object(enemy, "force_battle_shock_test") as force_test:
        assert dg_player.stratagems.use(
            "NAUSEATING PAROXYSMS",
            unit=infantry,
            enemy_unit=enemy,
            phase_name="Fight phase",
            dequeue=True,
        )
    force_test.assert_called_once()
    _, kwargs = force_test.call_args
    assert kwargs["modifier"] == -1
    assert kwargs["source"] == "NAUSEATING PAROXYSMS"


def test_vermin_cloud_grants_six_inch_pile_in_and_consolidate_until_phase_end():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    infantry = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(infantry)
    _deploy_unit(game, infantry, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "FIGHT_PHASE", 0)
    assert dg_player.stratagems.use("VERMIN CLOUD", unit=infantry, phase_name="Fight phase")
    assert float(infantry.get_fight_phase_move_distance_override("pile_in") or 0.0) == 6.0
    assert float(infantry.get_fight_phase_move_distance_override("consolidate") or 0.0) == 6.0

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert infantry.get_fight_phase_move_distance_override("pile_in") is None
    assert infantry.get_fight_phase_move_distance_override("consolidate") is None


def test_enervating_onslaught_queues_charge_end_reaction_and_caps_mortal_wounds_at_six():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    infantry = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
        quantity=7,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="10",
        toughness="5",
    )
    dg_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, enemy, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, "CHARGE_PHASE", 0)
    dg_player.stratagems._on_unit_move_ended(unit=infantry, action="charge")
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "ENERVATING ONSLAUGHT" for entry in list(pending or []))

    with patch("warhammer40k_ai.rules.stratagems_death_guard.dice_module.get_roll", side_effect=[4, 4, 4, 4, 4, 4, 4]):
        assert dg_player.stratagems.use(
            "ENERVATING ONSLAUGHT",
            unit=infantry,
            enemy_unit=enemy,
            action="charge",
            phase_name="Charge phase",
            dequeue=True,
        )

    assert int(enemy.models[0].wounds) == 4


def test_myphitic_invigoration_queues_reaction_and_only_applies_when_strength_exceeds_toughness():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    infantry = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
        toughness="5",
    )
    blight_hauler = _make_unit(
        "Myphitic Blight-hauler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
        toughness="9",
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(infantry)
    dg_army.add_unit(blight_hauler)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, blight_hauler, 15.5, 10.0)
    _deploy_unit(game, attacker, 22.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Shooting phase"
    dg_player.stratagems._on_shooting_targets_selected(attacking_unit=attacker, target_units=[infantry])
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "MYPHITIC INVIGORATION" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "MYPHITIC INVIGORATION",
        unit=infantry,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )

    active_effects = list(
        infantry.iter_active_death_guard_temp_effects(
            effect_type="wound_roll_penalty",
            attack_type="ranged",
            require_target_match=False,
            strength=6,
            target_toughness=int(infantry.toughness),
        )
        or []
    )
    inactive_effects = list(
        infantry.iter_active_death_guard_temp_effects(
            effect_type="wound_roll_penalty",
            attack_type="ranged",
            require_target_match=False,
            strength=5,
            target_toughness=int(infantry.toughness),
        )
        or []
    )
    assert len(active_effects) == 1
    assert inactive_effects == []


def test_flyblown_host_stratagems_have_tool_descriptors():
    expected = {
        "000009730002": ("Nauseating Paroxysms", "force_battleshock_test_at_minus_1"),
        "000009730003": ("Vermin Cloud", "pile_in_and_consolidate_up_to_6"),
        "000009730004": ("Eye of the Swarm", "grant_ranged_pistol_except_blast"),
        "000009730005": ("Droning Horror", "ranged_hit_reroll_ones_or_full_within_half_range"),
        "000009730006": ("Enervating Onslaught", "charge_end_mortal_wounds_against_non_monster_vehicle"),
        "000009730007": ("Myphitic Invigoration", "defensive_wound_penalty_when_strength_exceeds_toughness"),
    }

    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())

        assert by_id is not None
        assert by_name is not None
        assert by_id == by_name
        assert by_id.name == name
        assert by_id.effect == effect
