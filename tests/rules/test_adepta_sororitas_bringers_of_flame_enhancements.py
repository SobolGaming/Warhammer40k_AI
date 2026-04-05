from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
        attached_to=None,
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adepta Sororitas",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 4,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sororitas_army = Army("Adepta Sororitas", "Bringers of Flame")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sororitas_player = Player("Sororitas", control=PlayerControl.REMOTE, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sororitas_army, enemy_army, sororitas_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
        refresh = getattr(unit, "_refresh_bearer_unit_common_modifiers", None)
        if callable(refresh):
            refresh()


def _detach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = []
    leader.attached_to = None
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
        refresh = getattr(unit, "_refresh_bearer_unit_common_modifiers", None)
        if callable(refresh):
            refresh()


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AS",
        detachment="Bringers of Flame",
        detachment_id="bringers-of-flame",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_profile(*, is_melee: bool, attacks: str = "1", strength: str = "4", description: str = ""):
    data = {
        "name": "Test Weapon",
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": str(attacks),
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": str(description or ""),
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


def test_bringers_of_flame_enhancement_descriptors_registered():
    expected = {
        "000009033002": ("Righteous Rage", "discard_miracle_dice_for_bearer_melee_attacks_strength_bonus"),
        "000009033003": ("Manual of Saint Griselda", "discard_up_to_two_miracle_dice_add_sum_capped_die"),
        "000009033004": ("Fire and Fury", "torrent_attacks_bonus_and_other_ranged_sustained_hits"),
        "000009033005": ("Iron Surplice of Saint Istalela", "bearer_save_set_and_fnp"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_righteous_rage_applies_bearer_melee_attacks_and_strength_until_end_of_phase():
    game, sororitas_army, enemy_army, sororitas_player = _build_game()
    source = _make_unit(
        "Canoness",
        keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"],
        attached_to=["INFANTRY_BODYGUARD"],
    )
    enemy = _make_unit("Enemy Elite", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=6)
    sororitas_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000009033002",
        name="Righteous Rage",
        description=(
            "ADEPTA SORORITAS model only. Each time the bearer is selected to fight, you can first discard up to 3 "
            "Miracle dice. For each Miracle dice just discarded, until the end of the phase, add 1 to the Attacks "
            "and Strength characteristics of the bearer's melee weapons."
        ),
    )

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0, 1]}
    sororitas_army.acts_of_faith.miracle_dice = [1, 2, 6, 5]

    sororitas_army.acts_of_faith.on_fight_unit_selected(source, game=game, selecting_player=sororitas_player)
    assert list(sororitas_army.acts_of_faith.miracle_dice) == [6, 5]
    assert int(source.special_rules.get("enhancement_righteous_rage_bonus", 0) or 0) == 2

    bearer = source.models[0]
    melee_profile = _make_profile(is_melee=True, attacks="1", strength="4")
    boosted_count = melee_profile._resolve_attack_count(
        enemy,
        bearer,
        _attack_result(melee_profile, bearer, enemy),
        publish_roll_event=False,
    )
    assert int(boosted_count.num_attacks) == 3

    boosted_wound = melee_profile._wound_target_with_tracking(
        enemy,
        bearer,
        {"distance_to_target": 1.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(boosted_wound.get("wound", False))
    assert any("Righteous Rage" in str(v) for v in list(boosted_wound.get("modifiers", []) or []))

    game.phase = BattleRoundPhases.COMMAND_PHASE
    expired_count = melee_profile._resolve_attack_count(
        enemy,
        bearer,
        _attack_result(melee_profile, bearer, enemy),
        publish_roll_event=False,
    )
    assert int(expired_count.num_attacks) == 1


def test_manual_of_saint_griselda_discards_miracle_dice_and_adds_capped_sum_die():
    game, sororitas_army, _enemy_army, sororitas_player = _build_game()
    source = _make_unit(
        "Palatine",
        keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"],
    )
    sororitas_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000009033003",
        name="Manual of Saint Griselda",
        description=(
            "ADEPTA SORORITAS model only. At the start of your Command phase, you can discard up to 2 Miracle dice. "
            "Then, add 1 Miracle dice to your Miracle Dice pool showing a value equal to the sum of the two Miracle "
            "dice you just discarded (to a maximum of 6)."
        ),
    )

    game.phase = BattleRoundPhases.COMMAND_PHASE
    sororitas_army.acts_of_faith.miracle_dice = [2, 5, 6]
    game.map.miracle_dice_pool_reroll_provider = lambda **_kwargs: {"indices": [0, 1]}

    sororitas_army.acts_of_faith.on_command_phase_start(game=game, player=sororitas_player)
    assert list(sororitas_army.acts_of_faith.miracle_dice) == [6, 6]


def test_fire_and_fury_applies_torrent_attacks_and_non_torrent_sustained_hits_while_leading():
    game, sororitas_army, enemy_army, _sororitas_player = _build_game()
    leader = _make_unit(
        "Canoness",
        keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"],
        attached_to=["INFANTRY_BODYGUARD"],
    )
    bodyguard = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sororitas_army.add_unit(leader)
    sororitas_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000009033004",
        name="Fire and Fury",
        description=(
            "ADEPTA SORORITAS model only. While the bearer is leading a unit, add 1 to the Attacks characteristic of "
            "Torrent weapons equipped by models in that unit, and all other ranged weapons equipped by models in that "
            "unit have the [SUSTAINED HITS 1] ability."
        ),
    )

    attacker = bodyguard.models[0]
    torrent_profile = _make_profile(is_melee=False, attacks="1", description="torrent")
    non_torrent_profile = _make_profile(is_melee=False, attacks="1", description="")

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    buffed_torrent_count = torrent_profile._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(torrent_profile, attacker, enemy),
        publish_roll_event=False,
    )
    assert int(buffed_torrent_count.num_attacks) == 2

    buffed_attack_instance: dict = {}
    buffed_hit = non_torrent_profile._hit_target_with_tracking(
        enemy,
        attacker,
        buffed_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(buffed_hit.get("hit", False))
    assert int(buffed_attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Sustained Hits" in str(effect) for effect in list(buffed_hit.get("special_effects", []) or []))

    _detach_leader(bodyguard, leader)
    plain_torrent_count = torrent_profile._resolve_attack_count(
        enemy,
        attacker,
        _attack_result(torrent_profile, attacker, enemy),
        publish_roll_event=False,
    )
    assert int(plain_torrent_count.num_attacks) == 1

    plain_attack_instance: dict = {}
    non_torrent_profile._hit_target_with_tracking(
        enemy,
        attacker,
        plain_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert "sustained_hit" not in plain_attack_instance


def test_iron_surplice_sets_bearer_save_and_fnp_for_bearer_only():
    game, sororitas_army, _enemy_army, _sororitas_player = _build_game()
    source = _make_unit(
        "Canoness",
        keywords=["CHARACTER", "INFANTRY", "ADEPTA SORORITAS"],
    )
    extra = _add_extra_model(source, name="Battle Sister")
    sororitas_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000009033005",
        name="Iron Surplice of Saint Istalela",
        description="CANONESS or PALATINE model only. The bearer has a Save characteristic of 2+ and the Feel No Pain 5+ ability.",
    )

    bearer_id = str(source.special_rules.get("enhancement_iron_surplice_bearer_model_id", "") or "")
    assert bearer_id
    bearer = next(model for model in list(source.models or []) if str(get_entity_id(model) or "") == bearer_id)
    assert bearer is not extra

    save_bearer, save_source = source.get_model_save_characteristic_override(bearer)
    save_other, _ = source.get_model_save_characteristic_override(extra)
    assert int(save_bearer or 0) == 2
    assert "Iron Surplice" in str(save_source or "")
    assert save_other is None

    fnp_bearer = list(source.has_feel_no_pain(target_model=bearer) or [])
    fnp_other = list(source.has_feel_no_pain(target_model=extra) or [])
    assert any(int(value or 0) == 5 for value, _condition in fnp_bearer)
    assert all(int(value or 0) != 5 for value, _condition in fnp_other)

    entries = list(source.special_rules.get("enhancement_bearer_fnp_entries", []) or [])
    iron_entries = [entry for entry in entries if str(entry.get("tag", "") or "") == "enhancement_fnp_000009033005"]
    assert len(iron_entries) == 1
    assert str(iron_entries[0].get("source_model_id", "") or "") == bearer_id
