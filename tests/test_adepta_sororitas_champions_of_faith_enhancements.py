from __future__ import annotations

import copy

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 4,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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


def _create_unit(
    name: str,
    *,
    faction_name: str = "Adepta Sororitas",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sororitas_army = Army("Adepta Sororitas", "Champions of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    sororitas_player = Player("Sororitas", control=PlayerControl.REMOTE, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sororitas_army, enemy_army, sororitas_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AS",
        detachment="Champions of Faith",
        detachment_id="champions-of-faith",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_profile(*, is_melee: bool, attacks: str = "1", strength: str = "4", damage: str = "1"):
    data = {
        "name": "Test Weapon",
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": str(attacks),
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": str(damage),
        "description": "",
    }
    return Wargear(data).profiles["default"]


def _attack_result(profile, attacker, target_unit) -> AttackResult:
    return AttackResult(
        weapon_name=str(getattr(profile, "name", "") or "Weapon"),
        attacker_name=str(getattr(attacker, "name", "") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "")),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _add_extra_model(unit: Unit, *, name: str = "Extra Model") -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=4,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.set_parent_unit(unit)
    unit.models.append(model)
    return model


class _ArrivingUnit:
    def __init__(self, army):
        self._army = army
        self.models = [
            Model(
                name="Arriving",
                movement=6,
                toughness=4,
                save=4,
                wounds=2,
                leadership=7,
                objective_control=1,
                model_base=Base(BaseType.CIRCULAR, 1.0),
            )
        ]

    def get_parent_army(self):
        return self._army

    def is_in_strategic_reserves(self):
        return False

    def has_deep_strike(self):
        return True

    def calculate_model_positions(self, x, y, _game_map, **_kwargs):
        return [(x, y, 0.0, 0.0)]

    def _create_potential_base(self, x, y, z, facing, model):
        base = copy.deepcopy(model.model_base)
        base.set_position(x, y, z)
        base.set_facing(facing)
        return base


def test_champions_of_faith_enhancement_descriptors_registered():
    expected = {
        "000009831002": ("Triptych of Judgement", "bearer_unit_ignore_hit_and_skill_modifiers"),
        "000009831003": ("Mark of Devotion", "bearer_melee_attacks_bonus_with_righteous_upgrade"),
        "000009831004": (
            "Eyes of the Oracle",
            "bearer_weapons_precision_and_gain_cp_on_character_model_destroyed_by_bearer_unit",
        ),
        "000009831005": ("Sanctified Amulet", "enemy_reserves_arrival_min_distance_from_bearer"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_triptych_of_judgement_grants_unit_ignore_modifiers_while_bearer_alive():
    game, sororitas_army, enemy_army, _player = _build_game()
    source = _create_unit("Canoness", keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"])
    attacker_extra = _add_extra_model(source, name="Battle Sister")
    enemy = _create_unit("Enemy Squad", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]

    _apply_enhancement(
        source,
        enhancement_id="000009831002",
        name="Triptych of Judgement",
        description=(
            "ADEPTA SORORITAS model only. Each time a model in the bearer's unit makes an attack, you can ignore any or all "
            "modifiers to that attack's Ballistic Skill or Weapon Skill characteristics and/or any or all modifiers to the Hit roll."
        ),
    )

    profile = _make_profile(is_melee=True)
    rule = profile._ignore_hit_modifier_rule(attacker_extra)
    assert rule is not None
    assert set(rule.get("skill_kinds") or set()) == {"ballistic", "weapon"}
    assert bool(rule.get("allow_hit"))

    bearer_id = str(source.special_rules.get("enhancement_triptych_of_judgement_bearer_model_id", "") or "")
    bearer = next(model for model in list(source.models or []) if str(get_entity_id(model) or "") == bearer_id)
    bearer.wounds = 0
    assert profile._ignore_hit_modifier_rule(attacker_extra) is None


def test_mark_of_devotion_applies_bearer_melee_attacks_and_righteous_damage_bonus():
    game, sororitas_army, enemy_army, _player = _build_game()
    source = _create_unit("Palatine", keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"])
    enemy = _create_unit(
        "Enemy Elite",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=20,
    )
    sororitas_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]

    _apply_enhancement(
        source,
        enhancement_id="000009831003",
        name="Mark of Devotion",
        description=(
            "ADEPTA SORORITAS model only. Add 1 to the Attacks characteristic of the bearer's melee weapons. While the "
            "bearer's unit is Righteous, add 2 to the Attacks characteristic and add 1 to the Damage characteristic of the "
            "bearer's melee weapons instead."
        ),
    )

    bearer_id = str(source.special_rules.get("enhancement_mark_of_devotion_bearer_model_id", "") or "")
    bearer = next(model for model in list(source.models or []) if str(get_entity_id(model) or "") == bearer_id)
    profile = _make_profile(is_melee=True, attacks="1", damage="1")

    normal_count = profile._resolve_attack_count(
        enemy,
        bearer,
        _attack_result(profile, bearer, enemy),
        publish_roll_event=False,
    )
    assert int(normal_count.num_attacks) == 2

    normal_damage = profile._damage_target_with_tracking(
        enemy.models[0],
        bearer,
        {"distance_to_target": 1.0},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert not any("Mark of Devotion +1D" in str(effect) for effect in list(normal_damage.get("special_effects", []) or []))

    source.special_rules["champions_of_faith_righteous_active"] = True
    righteous_count = profile._resolve_attack_count(
        enemy,
        bearer,
        _attack_result(profile, bearer, enemy),
        publish_roll_event=False,
    )
    assert int(righteous_count.num_attacks) == 3

    enemy.models[0].wounds = 20
    righteous_damage = profile._damage_target_with_tracking(
        enemy.models[0],
        bearer,
        {"distance_to_target": 1.0},
        game_map=game.map,
        roll_value=1,
        allow_rerolls=False,
    )
    assert any("Mark of Devotion +1D" in str(effect) for effect in list(righteous_damage.get("special_effects", []) or []))


def test_eyes_of_the_oracle_grants_precision_and_cp_on_character_model_destroyed_only_while_bearer_alive():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    source = _create_unit("Canoness", keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"])
    extra_model = _add_extra_model(source, name="Battle Sister")
    enemy_character = _create_unit(
        "Enemy Character",
        faction_name="Enemy",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_non_character = _create_unit(
        "Enemy Trooper",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sororitas_army.add_unit(source)
    enemy_army.add_unit(enemy_character)
    enemy_army.add_unit(enemy_non_character)
    game.map.units = [source, enemy_character, enemy_non_character]

    _apply_enhancement(
        source,
        enhancement_id="000009831004",
        name="Eyes of the Oracle",
        description=(
            "ADEPTA SORORITAS model only. The bearer's weapons have the [PRECISION] ability. Each time the bearer's unit "
            "destroys an enemy CHARACTER model, you gain 1CP."
        ),
    )

    bearer_id = str(source.special_rules.get("enhancement_eyes_of_the_oracle_bearer_model_id", "") or "")
    bearer = next(model for model in list(source.models or []) if str(get_entity_id(model) or "") == bearer_id)

    ranged_profile = _make_profile(is_melee=False)
    bearer_attack_instance: dict = {}
    hit_result = ranged_profile._hit_target_with_tracking(
        enemy_character,
        bearer,
        bearer_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit", False))
    assert bool(bearer_attack_instance.get("bonus_precision", False))

    other_attack_instance: dict = {}
    ranged_profile._hit_target_with_tracking(
        enemy_character,
        extra_model,
        other_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(other_attack_instance.get("bonus_precision", False)) is False

    sororitas_player.command_points = 0
    sororitas_player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    game.event_system.publish(
        "model_destroyed",
        attacker_model=extra_model,
        attacker_unit=source,
        target_model=enemy_character.models[0],
        target_unit=enemy_character,
        weapon_profile=ranged_profile,
        game_map=game.map,
    )
    assert int(sororitas_player.command_points) == 1

    sororitas_player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    bearer.wounds = 0
    cp_before_dead_bearer = int(sororitas_player.command_points)
    game.event_system.publish(
        "model_destroyed",
        attacker_model=extra_model,
        attacker_unit=source,
        target_model=enemy_character.models[0],
        target_unit=enemy_character,
        weapon_profile=ranged_profile,
        game_map=game.map,
    )
    assert int(sororitas_player.command_points) == cp_before_dead_bearer

    sororitas_player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    bearer.wounds = 4
    cp_before_non_character = int(sororitas_player.command_points)
    game.event_system.publish(
        "model_destroyed",
        attacker_model=extra_model,
        attacker_unit=source,
        target_model=enemy_non_character.models[0],
        target_unit=enemy_non_character,
        weapon_profile=ranged_profile,
        game_map=game.map,
    )
    assert int(sororitas_player.command_points) == cp_before_non_character


def test_sanctified_amulet_blocks_reserves_within_12_of_bearer_only_and_while_alive():
    game, sororitas_army, enemy_army, _player = _build_game()
    source = _create_unit("Palatine", keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"])
    extra_model = _add_extra_model(source, name="Battle Sister")
    sororitas_army.add_unit(source)
    game.map.units = [source]

    _apply_enhancement(
        source,
        enhancement_id="000009831005",
        name="Sanctified Amulet",
        description=(
            "ADEPTA SORORITAS model only. Enemy units that are set up on the battlefield from Reserves cannot be set up "
            "within 12\" of the bearer."
        ),
    )

    bearer_id = str(source.special_rules.get("enhancement_sanctified_amulet_bearer_model_id", "") or "")
    bearer = next(model for model in list(source.models or []) if str(get_entity_id(model) or "") == bearer_id)
    bearer.set_location(10.0, 0.0, 0.0, 0.0)
    extra_model.set_location(40.0, 0.0, 0.0, 0.0)

    arriving = _ArrivingUnit(enemy_army)

    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is False
    assert game.can_place_unit_arriving_from_reserves(arriving, (52.0, 0.0, 0.0)) is True

    bearer.wounds = 0
    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is True
