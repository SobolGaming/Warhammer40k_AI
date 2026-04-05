from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import (
    NurglesGiftManager,
    PLAGUE_RATTLEJOINT,
    PLAGUE_SCABROUS,
    PLAGUE_SKULLSQUIRM,
)
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
        abilities=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        faction_tokens = {str(k).upper() for k in list(faction_keywords or [])}
        self.faction_data = {"name": "Death Guard" if "DEATH GUARD" in faction_tokens else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability in list(abilities or []):
            if isinstance(ability, dict):
                self.datasheets_abilities.append(ability)
            else:
                text = str(ability or "")
                self.datasheets_abilities.append(
                    {
                        "name": text,
                        "description": text,
                        "type": "",
                        "parameter": "",
                    }
                )
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
    abilities=None,
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            abilities=abilities,
        ),
        quantity=int(quantity),
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army("Death Guard", "Champions of Contagion")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_player.command_points = 10
    enemy_player.command_points = 10
    dg_army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.can_be_attached_to_names = [bodyguard.name]
    leader.attach_to_unit(bodyguard)


def _make_attached_death_guard_unit(game: Game, army: Army) -> tuple[Unit, Unit]:
    bodyguard = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
        wounds="4",
        toughness="5",
    )
    leader = _make_unit(
        "Lord of Contagion",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
        wounds="5",
        toughness="5",
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _deploy_unit(game, leader, 10.0, 10.0)
    _attach_leader(bodyguard, leader)
    return bodyguard, leader


def test_blessings_of_filth_grants_critical_hits_on_five_plus_to_attached_unit():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    attached_unit, _leader = _make_attached_death_guard_unit(game, dg_army)
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 16.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("BLESSINGS OF FILTH", unit=attached_unit, phase_name="Shooting phase")

    hit_mods = attached_unit.get_unit_hit_reroll_modifiers("ranged", target=enemy, attacker_model=attached_unit.models[0])
    assert int(hit_mods.get("crit_hit_threshold") or 0) == 5
    assert any("BLESSINGS OF FILTH" in str(reason or "").upper() for reason in list(hit_mods.get("crit_hit_reasons") or []))


def test_malignance_magnified_only_rerolls_vs_targets_below_starting_strength():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    attached_unit, _leader = _make_attached_death_guard_unit(game, dg_army)
    wounded_target = _make_unit(
        "Wounded Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    healthy_target = _make_unit(
        "Healthy Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    enemy_army.add_unit(wounded_target)
    enemy_army.add_unit(healthy_target)
    _deploy_unit(game, wounded_target, 16.0, 10.0)
    _deploy_unit(game, healthy_target, 18.0, 10.0)
    wounded_target.models[0].wounds = 2

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("MALIGNANCE MAGNIFIED", unit=attached_unit, phase_name="Shooting phase")

    hit_mods_wounded = attached_unit.get_unit_hit_reroll_modifiers("ranged", target=wounded_target, attacker_model=attached_unit.models[0])
    wound_mods_wounded = attached_unit.get_unit_wound_reroll_modifiers("ranged", target=wounded_target)
    assert bool(hit_mods_wounded.get("reroll_hit_full"))
    assert bool(wound_mods_wounded.get("reroll_wound_full"))

    hit_mods_healthy = attached_unit.get_unit_hit_reroll_modifiers("ranged", target=healthy_target, attacker_model=attached_unit.models[0])
    wound_mods_healthy = attached_unit.get_unit_wound_reroll_modifiers("ranged", target=healthy_target)
    assert not bool(hit_mods_healthy.get("reroll_hit_full"))
    assert not bool(wound_mods_healthy.get("reroll_wound_full"))


def test_grotesque_fortitude_queues_reaction_and_adds_two_toughness():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    attached_unit, leader = _make_attached_death_guard_unit(game, dg_army)
    attacker = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
        toughness="4",
    )
    enemy_army.add_unit(attacker)
    _deploy_unit(game, attacker, 16.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Shooting phase"
    dg_player.stratagems._on_shooting_targets_selected(attacking_unit=attacker, target_units=[attached_unit])
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "GROTESQUE FORTITUDE" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "GROTESQUE FORTITUDE",
        unit=attached_unit,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert int(attached_unit.toughness) == 7
    assert int(leader.toughness) == 7


def test_rabid_infusion_requires_two_character_models_and_grants_fight_first():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    bodyguard = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    invalid_unit = _make_unit(
        "Lone Champion",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    first_leader = _make_unit(
        "Lord of Contagion",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    second_leader = _make_unit(
        "Biologus Putrifier",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    bodyguard.possible_abilities = [
        {
            "name": "Bodyguard",
            "description": "If this unit has a Starting Strength of 10, you can attach up to 2 Leader units to it instead of one.",
        }
    ]
    bodyguard.starting_model_count = 10
    dg_army.add_unit(bodyguard)
    dg_army.add_unit(first_leader)
    dg_army.add_unit(second_leader)
    dg_army.add_unit(invalid_unit)
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _deploy_unit(game, first_leader, 10.0, 10.0)
    _deploy_unit(game, second_leader, 10.0, 10.0)
    _deploy_unit(game, invalid_unit, 14.0, 10.0)
    _attach_leader(bodyguard, first_leader)
    _attach_leader(bodyguard, second_leader)

    game.turn = 1
    _set_phase(game, "FIGHT_PHASE", 0)
    assert dg_player.stratagems.use("RABID INFUSION", unit=bodyguard, phase_name="Fight phase")
    assert bool(bodyguard.has_fight_first())
    assert not dg_player.stratagems.use("RABID INFUSION", unit=invalid_unit, phase_name="Fight phase")


def test_mobile_vector_attaches_to_nearby_unattached_bodyguard():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    mobile_character = _make_unit(
        "Malignant Plaguecaster",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    bodyguard = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(mobile_character)
    dg_army.add_unit(bodyguard)
    _deploy_unit(game, mobile_character, 10.0, 10.0)
    _deploy_unit(game, bodyguard, 11.0, 10.0)
    mobile_character.can_be_attached_to = [bodyguard.get_datasheet_id()]
    mobile_character.can_be_attached_to_names = [bodyguard.name]

    game.turn = 1
    _set_phase(game, "MOVEMENT_PHASE", 0)
    assert dg_player.stratagems.use(
        "MOBILE VECTOR",
        unit=mobile_character,
        bodyguard_unit=bodyguard,
        phase_name="Movement phase",
    )
    assert mobile_character.attached_to is bodyguard
    assert mobile_character in list(getattr(bodyguard, "attached_leaders", []) or [])


def test_mobile_vector_rejects_bodyguard_that_is_already_led():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    mobile_character = _make_unit(
        "Malignant Plaguecaster",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    bodyguard = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    existing_leader = _make_unit(
        "Lord of Contagion",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(mobile_character)
    dg_army.add_unit(bodyguard)
    dg_army.add_unit(existing_leader)
    _deploy_unit(game, mobile_character, 10.0, 10.0)
    _deploy_unit(game, bodyguard, 11.0, 10.0)
    _deploy_unit(game, existing_leader, 11.0, 10.0)
    _attach_leader(bodyguard, existing_leader)
    mobile_character.can_be_attached_to = [bodyguard.get_datasheet_id()]
    mobile_character.can_be_attached_to_names = [bodyguard.name]

    game.turn = 1
    _set_phase(game, "MOVEMENT_PHASE", 0)
    assert not dg_player.stratagems.use(
        "MOBILE VECTOR",
        unit=mobile_character,
        bodyguard_unit=bodyguard,
        phase_name="Movement phase",
    )
    assert getattr(mobile_character, "attached_to", None) is None


def test_deaths_heads_applies_all_plague_effects_without_afflicting_target():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    source = _make_unit(
        "Biologus Putrifier",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
        toughness="5",
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    source._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use(
        "DEATH'S HEADS",
        unit=source,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )

    keys = set(NurglesGiftManager.get_afflicted_plague_keys_for_unit(enemy, game=game, game_map=game.map))
    assert PLAGUE_SKULLSQUIRM.key in keys
    assert PLAGUE_RATTLEJOINT.key in keys
    assert PLAGUE_SCABROUS.key in keys
    assert NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map) is None
    assert bool(source._target_is_afflicted(enemy, source_unit=source)) is False


def test_champions_of_contagion_stratagems_have_tool_descriptors():
    expected = {
        "000010132002": ("Blessings of Filth", "critical_hits_on_5plus"),
        "000010132003": ("Malignance Magnified", "reroll_hits_and_wounds_vs_target_below_starting_strength"),
        "000010132004": ("Grotesque Fortitude", "defensive_toughness_bonus"),
        "000010132005": ("Rabid Infusion", "grant_fights_first"),
        "000010132006": ("Mobile Vector", "attach_as_leader"),
        "000010132007": ("Death's Heads", "apply_all_plagues_without_afflicted"),
    }

    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())

        assert by_id is not None
        assert by_name is not None
        assert by_id == by_name
        assert by_id.name == name
        assert by_id.effect == effect
