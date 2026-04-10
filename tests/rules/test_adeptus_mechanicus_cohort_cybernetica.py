from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.doctrina_imperatives import CONQUEROR_IMPERATIVE, PROTECTOR_IMPERATIVE
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 3,
        leadership: int = 7,
        objective_control: int = 1,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Adeptus Mechanicus":
                faction_keywords = ["ADEPTUS MECHANICUS"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "60mm",
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
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 3,
    leadership: int = 7,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    game.deployment_zones = {
        p1.id: {"mission_zones": [_RectZone(0.0, 20.0, 0.0, 20.0)]},
        p2.id: {"mission_zones": [_RectZone(80.0, 100.0, 0.0, 20.0)]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)

    p1.command_points = 10
    p2.command_points = 10
    admech_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, admech_army, enemy_army, p1, p2


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (idx * 0.05), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        existing = list(getattr(game.map, "units", []) or [])
        if unit not in existing:
            existing.append(unit)
            game.map.units = existing


def _phase_start(game: Game, acting_player: Player, phase_name: str) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = list(game.players).index(acting_player)
    game.event_system.publish("phase_start", player=acting_player, phase=phase)


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective") -> Objective:
    loc = ObjectivePoint(float(x), float(y))
    objective = Objective(name, ObjectiveCategory.PRIMARY, 0, "", lambda _g: False, location=loc)
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _basic_ranged_weapon(
    *,
    name: str = "Phosphor Blaster",
    range_inches: str = "48",
    skill: str = "4+",
    strength: str = "4",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": str(range_inches),
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_cyber_psalm_programming_grants_legio_cybernetica_move_and_oc():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_unit = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_unit)

    model = legio_unit.models[0]
    assert legio_unit.get_effective_model_characteristic(model, "movement") == 8
    assert legio_unit.get_effective_model_characteristic(model, "objective_control") == 2


def test_cyber_psalm_programming_does_not_apply_to_non_legio_units():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(skitarii)

    model = skitarii.models[0]
    assert skitarii.get_effective_model_characteristic(model, "movement") == 6
    assert skitarii.get_effective_model_characteristic(model, "objective_control") == 1


def test_cyber_psalm_programming_oc_bonus_is_disabled_while_battle_shocked():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_unit = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_unit)
    model = legio_unit.models[0]

    mgr = army.adeptus_mechanicus_detachments
    assert mgr is not None
    bonus, source = mgr.cyber_psalm_programming_objective_control_bonus(model, unit=legio_unit)
    assert bonus == 1
    assert source == "Cyber-Psalm Programming"

    legio_unit.status_effects = [BattleShockEffect(current_turn=1)]
    bonus_bs, _source_bs = mgr.cyber_psalm_programming_objective_control_bonus(model, unit=legio_unit)
    assert bonus_bs == 0
    assert legio_unit.get_effective_model_characteristic(model, "movement") == 8


def test_cyber_psalm_programming_uses_attached_root_for_leader_models():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Cohort Cybernetica")
    army.faction_id = "ADM"
    legio_bodyguard = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    tech_priest = _make_unit(
        "Tech-priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army.add_unit(legio_bodyguard)
    army.add_unit(tech_priest)
    _attach_leader(legio_bodyguard, tech_priest)

    leader_model = tech_priest.models[0]
    assert tech_priest.get_effective_model_characteristic(leader_model, "movement") == 8
    assert tech_priest.get_effective_model_characteristic(leader_model, "objective_control") == 2


def test_cohort_cybernetica_stratagem_descriptors_registered():
    expected = {
        "000008573002": ("Motive Imperative", "move_and_advance_charge_bonus"),
        "000008573003": ("Auto-divinatory Targeting", "ranged_bs_three_plus_ignores_cover_with_objective_target_lock"),
        "000008573004": ("Machine Spirit Resurgent", "full_hit_reroll_with_conditional_full_wound_reroll_when_below_half_strength"),
        "000008573005": ("Machine Superiority", "ignore_characteristic_and_roll_modifiers_except_saves"),
        "000008573006": ("Transcendent Cogitation", "grant_both_doctrina_imperatives"),
        "000008573007": ("Benevolence of the Omnissiah", "feel_no_pain_with_mortal_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.stratagem_id == stratagem_id


def test_auto_divinatory_targeting_applies_keywords_restricts_targets_and_stacks_with_transcendent_cogitation():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    kastelans = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=8,
        toughness=10,
        wounds=10,
        objective_control=3,
    )
    nearby_enemy = _make_unit(
        "Enemy Squad Near Node",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Enemy Squad Far Away",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(kastelans)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(far_enemy)

    weapon = _basic_ranged_weapon(skill="4+", range_inches="48")
    kastelans.models[0].wargear = [weapon]
    profile = weapon.profiles["default"]

    _place_unit(game, kastelans, 10.0, 10.0)
    _place_unit(game, nearby_enemy, 21.0, 10.0)
    _place_unit(game, far_enemy, 35.0, 10.0)
    objective = _add_objective(game, 20.0, 10.0, name="Data Node")
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    assert p1.stratagems.use(
        "AUTO-DIVINATORY TARGETING",
        unit=kastelans,
        objective_id=str(get_entity_id(objective) or ""),
        phase_name="Command phase",
    )
    assert p1.stratagems.use(
        "TRANSCENDENT COGITATION",
        unit=kastelans,
        phase_name="Command phase",
    )
    assert int(p1.command_points or 0) == 8

    _phase_start(game, p1, "SHOOTING_PHASE")
    model = kastelans.models[0]
    bonuses = kastelans.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=model,
        weapon_profile=profile,
        target=nearby_enemy,
    )
    assert bool(bonuses.get("ignores_cover"))

    valid = kastelans._validate_shooting_declaration(profile, nearby_enemy, [model], game.map)
    assert valid["valid"] is True

    invalid = kastelans._validate_shooting_declaration(profile, far_enemy, [model], game.map)
    assert invalid["valid"] is False
    assert "Auto-divinatory Targeting" in invalid["reason"]

    active_keys = admech_army.doctrina_imperatives.get_active_imperative_keys_for_unit(kastelans, game=game)
    assert active_keys == {PROTECTOR_IMPERATIVE.key, CONQUEROR_IMPERATIVE.key}

    hit_result = profile._hit_target_with_tracking(
        nearby_enemy,
        model,
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    expired_keys = admech_army.doctrina_imperatives.get_active_imperative_keys_for_unit(kastelans, game=game)
    assert expired_keys == set()
    assert kastelans._adeptus_mechanicus_auto_divinatory_target_restriction_reason(far_enemy, game=game) == ""
    expired_bonuses = kastelans.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=model,
        weapon_profile=profile,
        target=nearby_enemy,
    )
    assert not bool(expired_bonuses.get("ignores_cover"))


def test_benevolence_of_the_omnissiah_grants_fnp_and_expires_next_command_phase():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=8,
        toughness=10,
        wounds=10,
        objective_control=3,
    )
    admech_army.add_unit(vehicle)
    _place_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    assert p1.stratagems.use(
        "BENEVOLENCE OF THE OMNISSIAH",
        unit=vehicle,
        phase_name="Command phase",
    )

    model = vehicle.models[0]
    fnp_abilities = vehicle.has_feel_no_pain(target_model=model)
    assert (6, None) in fnp_abilities
    assert (5, "against mortal wounds") in fnp_abilities

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    assert vehicle.has_feel_no_pain(target_model=model) == []


def test_machine_spirit_resurgent_requires_damage_and_grants_hit_then_conditional_wound_rerolls():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    vehicle = _make_unit(
        "Skorpius Disintegrator",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=8,
        toughness=10,
        wounds=10,
        objective_control=3,
    )
    enemy = _make_unit(
        "Enemy Vehicle",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        toughness=10,
        wounds=12,
    )
    admech_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _place_unit(game, vehicle, 10.0, 10.0)
    _place_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    start_cp = int(p1.command_points or 0)
    assert not p1.stratagems.use(
        "MACHINE SPIRIT RESURGENT",
        unit=vehicle,
        phase_name="Command phase",
    )
    assert int(p1.command_points or 0) == start_cp

    model = vehicle.models[0]
    model.wounds = 9
    assert p1.stratagems.use(
        "MACHINE SPIRIT RESURGENT",
        unit=vehicle,
        phase_name="Command phase",
    )

    hit_mods = vehicle.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=enemy)
    wound_mods = vehicle.get_model_wound_reroll_modifiers(model, attack_type="ranged", target=enemy)
    assert bool(hit_mods.get("reroll_hit_full"))
    assert not bool(wound_mods.get("reroll_wound_full"))

    model.wounds = 4
    wound_mods = vehicle.get_model_wound_reroll_modifiers(model, attack_type="ranged", target=enemy)
    assert bool(wound_mods.get("reroll_wound_full"))

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    expired_hit_mods = vehicle.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=enemy)
    assert not bool(expired_hit_mods.get("reroll_hit_full"))


def test_machine_superiority_ignores_negative_non_save_modifiers_allows_fall_back_shooting_and_expires():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    vehicle = _make_unit(
        "Kastelan Robots",
        keywords=["LEGIO CYBERNETICA", "VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=8,
        toughness=10,
        wounds=10,
        leadership=7,
        objective_control=3,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
    )
    admech_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)

    weapon = _basic_ranged_weapon(skill="3+", range_inches="48", strength="4")
    vehicle.models[0].wargear = [weapon]
    profile = weapon.profiles["default"]

    _place_unit(game, vehicle, 10.0, 10.0)
    _place_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    assert p1.stratagems.use(
        "MACHINE SUPERIORITY",
        unit=vehicle,
        phase_name="Command phase",
    )

    rule = vehicle.get_move_advance_charge_modifier_ignore_rule()
    assert isinstance(rule, dict)
    assert rule.get("default_choice") == "ignore_negative"
    assert "MACHINE SUPERIORITY" in str(rule.get("source", "")).upper()

    vehicle.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:move"))
    vehicle.add_characteristic_modifier("toughness", Modifier(ModifierOp.SUB, 1, source="test:toughness"))
    vehicle.add_characteristic_modifier("leadership", Modifier(ModifierOp.ADD, 1, source="test:leadership"))
    vehicle.add_characteristic_modifier("objective_control", Modifier(ModifierOp.SUB, 1, source="test:oc"))
    vehicle.add_characteristic_modifier("save", Modifier(ModifierOp.ADD, 1, source="test:save"))

    model = vehicle.models[0]
    assert int(vehicle.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 10
    assert int(vehicle.get_effective_model_characteristic(model, "toughness", game_map=game.map) or 0) == 10
    assert int(vehicle.get_effective_model_characteristic(model, "leadership", game_map=game.map) or 0) == 7
    assert int(vehicle.get_effective_model_characteristic(model, "objective_control", game_map=game.map) or 0) == 4
    assert int(vehicle.get_effective_model_characteristic(model, "save", game_map=game.map) or 0) == 4

    attack_instance = {"hit_roll_modifiers": [(-1, "Test penalty")]}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        model,
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True
    assert attack_instance.get("hit_modifier_choice") == CHOICE_IGNORE_NEGATIVE

    attack_instance = {"wound_roll_modifiers": [(-1, "Test penalty")]}
    wound_result = profile._wound_target_with_tracking(
        enemy,
        model,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result.get("wound") is True

    vehicle.round_state.fell_back_this_round = True
    assert vehicle.can_shoot_after_fall_back(profile, model=model) is True

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    vehicle.round_state.fell_back_this_round = True
    assert vehicle.get_move_advance_charge_modifier_ignore_rule() is None
    assert int(vehicle.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 8
    assert vehicle.can_shoot_after_fall_back(profile, model=model) is False


def test_motive_imperative_boosts_move_advance_and_charge_until_next_command_phase():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=8,
        toughness=10,
        wounds=10,
        objective_control=3,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _place_unit(game, vehicle, 10.0, 10.0)
    _place_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    assert p1.stratagems.use(
        "MOTIVE IMPERATIVE",
        unit=vehicle,
        phase_name="Command phase",
    )

    model = vehicle.models[0]
    assert int(vehicle.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 11
    assert any(int(bonus or 0) == 1 for bonus, _source in vehicle._collect_advance_roll_modifiers())
    assert any(int(bonus or 0) == 1 for bonus, _source in vehicle.get_charge_roll_target_strength_modifiers([enemy]))

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    assert int(vehicle.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 8
    assert not any(int(bonus or 0) == 1 for bonus, _source in vehicle._collect_advance_roll_modifiers())


def test_transcendent_cogitation_grants_both_imperatives_without_native_doctrina_and_expires():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    vehicle = _make_unit(
        "Skorpius Disintegrator",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        movement=10,
        toughness=10,
        wounds=10,
        objective_control=3,
    )
    admech_army.add_unit(vehicle)
    _place_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    _phase_start(game, p1, "COMMAND_PHASE")
    mgr = admech_army.doctrina_imperatives
    assert mgr.get_active_imperative_keys_for_unit(vehicle, game=game) == set()

    assert p1.stratagems.use(
        "TRANSCENDENT COGITATION",
        unit=vehicle,
        phase_name="Command phase",
    )
    assert mgr.get_active_imperative_keys_for_unit(vehicle, game=game) == {
        PROTECTOR_IMPERATIVE.key,
        CONQUEROR_IMPERATIVE.key,
    }

    game.turn = 2
    _phase_start(game, p1, "COMMAND_PHASE")
    assert mgr.get_active_imperative_keys_for_unit(vehicle, game=game) == set()
