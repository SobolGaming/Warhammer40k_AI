from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability


class _Wargear:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self._melee = melee
        self._ranged = ranged

    def is_melee(self) -> bool:
        return self._melee

    def is_ranged(self) -> bool:
        return self._ranged


class _WeaponProfile:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self.parent_wargear = _Wargear(melee=melee, ranged=ranged)


class _Unit:
    def __init__(self, name: str, *, abilities=None, keywords=None, model_count: int = 1):
        self._id = name
        self.name = name
        self.possible_abilities = list(abilities or [])
        self._keywords = {str(k).strip().lower() for k in (keywords or []) if str(k).strip()}
        self.faction_keywords = [str(k).strip() for k in (keywords or []) if str(k).strip()]
        self._army = None
        self.deployed = True
        self.special_rules = {}
        self.models = [
            _Model(self, model_id=f"{name}_model_{idx + 1}", keywords=self._keywords)
            for idx in range(int(model_count))
        ]

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army

    def has_any_keyword(self, kw: str) -> bool:
        return str(kw).strip().lower() in self._keywords

    def is_alive(self) -> bool:
        return True

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)


class _Model:
    def __init__(self, unit: _Unit, *, model_id: str | None = None, keywords=None):
        self.parent_unit = unit
        self._id = str(model_id or f"{unit._id}_model")
        self._keywords = {str(k).strip().lower() for k in (keywords or []) if str(k).strip()}

    def has_any_keyword(self, kw: str) -> bool:
        return str(kw).strip().lower() in self._keywords

    def is_alive(self) -> bool:
        return True


class _Map:
    def __init__(self, *, friendly_units, enemy_units, distances=None):
        self._friendly_units = list(friendly_units)
        self._enemy_units = list(enemy_units)
        self._distances = distances or {}

    def get_friendly_units(self, unit):
        return list(self._friendly_units)

    def get_enemy_units(self, unit):
        return list(self._enemy_units)

    def get_distance_between_units(self, unit_a, unit_b):
        if (unit_a, unit_b) in self._distances:
            return self._distances[(unit_a, unit_b)]
        if (unit_b, unit_a) in self._distances:
            return self._distances[(unit_b, unit_a)]
        return 0.0


def _create_chaos_knights_army(*units, detachment_type: str = "Helhunt Lance"):
    army = Army.with_detachment("Chaos Knights", detachment_type=detachment_type)
    army.faction_id = "QT"
    army.units = list(units)
    for unit in units:
        unit.set_parent_army(army)
    return army


def test_war_dog_ranged_reroll_hit_ones_aura():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    aura = Ability(
        name="Taskmaster (Aura)",
        faction_id="",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "each time that WAR DOG model makes a ranged attack, re-roll a Hit roll of 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    attacker = _Unit("attacker", keywords=["WAR DOG"])
    source = _Unit("source", abilities=[aura])
    target = _Unit("target")
    weapon_profile = _WeaponProfile(ranged=True)
    game_map = _Map(friendly_units=[attacker, source], enemy_units=[target])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=game_map)

    assert mods.reroll_hit_ones is True


def test_war_dog_melee_reroll_hit_ones_aura():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    aura = Ability(
        name="Frenzied Rampage (Aura)",
        faction_id="",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "each time that WAR DOG model makes a melee attack, re-roll a Hit roll of 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    attacker = _Unit("attacker", keywords=["WAR DOG"])
    source = _Unit("source", abilities=[aura])
    target = _Unit("target")
    weapon_profile = _WeaponProfile(melee=True)
    game_map = _Map(friendly_units=[attacker, source], enemy_units=[target])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=game_map)

    assert mods.reroll_hit_ones is True


def test_war_dog_leadership_oc_aura():
    from warhammer40k_ai.utility.aura_effects import get_aura_leadership_bonus, get_aura_objective_control_bonus

    aura = Ability(
        name="Dread Dominion (Aura)",
        faction_id="",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "improve that WAR DOG model's Leadership and Objective Control characteristics by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    receiver = _Unit("receiver", keywords=["WAR DOG"])
    source = _Unit("source", abilities=[aura])
    game_map = _Map(friendly_units=[receiver, source], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        ld_bonus = get_aura_leadership_bonus(receiver, game_map=game_map)
        oc_bonus = get_aura_objective_control_bonus(receiver, game_map=game_map)

    assert ld_bonus == -1
    assert oc_bonus == 1


def test_war_dog_closest_enemy_ap_aura():
    from warhammer40k_ai.utility.aura_effects import get_aura_ap_bonus

    aura = Ability(
        name="Close-range Killers (Aura)",
        faction_id="",
        description=(
            "While a friendly War Dog model is within 9\" of this model, each time that "
            "WAR DOG model makes an attack that targets the closest enemy unit, improve the Armour "
            "Penetration characteristic of that attack by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    attacker_unit = _Unit("attacker", keywords=["WAR DOG"])
    attacker_model = _Model(attacker_unit)
    source = _Unit("source", abilities=[aura])
    target = _Unit("target")
    other_enemy = _Unit("other")

    distances = {
        (attacker_unit, target): 4.0,
        (attacker_unit, other_enemy): 9.0,
    }
    game_map = _Map(friendly_units=[attacker_unit, source], enemy_units=[target, other_enemy], distances=distances)
    weapon_profile = _WeaponProfile(ranged=True)

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        ap_bonus, _reasons = get_aura_ap_bonus(attacker_model, weapon_profile, target, game_map=game_map)

    assert ap_bonus == 1


def test_helhunt_masters_of_pack_requires_two_war_dog_models():
    aura = Ability(
        name="Taskmaster (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "each time that WAR DOG model makes a ranged attack, re-roll a Hit roll of 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("desecrator", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    first_war_dog = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, first_war_dog)

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        assert source.get_parent_army().chaos_knights_detachments.helhunt_masters_of_pack_applies(
            target_unit=source,
            source_unit=source,
            aura_range=9.0,
            ability=aura,
        ) is False

    second_war_dog = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, first_war_dog, second_war_dog)

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        assert source.get_parent_army().chaos_knights_detachments.helhunt_masters_of_pack_applies(
            target_unit=source,
            source_unit=source,
            aura_range=9.0,
            ability=aura,
        ) is True


def test_helhunt_taskmaster_self_applies_to_titanic_unit():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    aura = Ability(
        name="Taskmaster (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "each time that WAR DOG model makes a ranged attack, re-roll a Hit roll of 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("desecrator", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    war_dog_1 = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    war_dog_2 = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, war_dog_1, war_dog_2)
    target = _Unit("target")
    weapon_profile = _WeaponProfile(ranged=True)
    game_map = _Map(friendly_units=[source, war_dog_1, war_dog_2], enemy_units=[target])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(source, target, weapon_profile, game_map=game_map)

    assert mods.reroll_hit_ones is True


def test_helhunt_dread_dominion_self_applies_to_titanic_unit():
    from warhammer40k_ai.utility.aura_effects import get_aura_leadership_bonus, get_aura_objective_control_bonus

    aura = Ability(
        name="Dread Dominion (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, "
            "improve that WAR DOG model's Leadership and Objective Control characteristics by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("despoiler", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    war_dog_1 = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    war_dog_2 = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, war_dog_1, war_dog_2)
    game_map = _Map(friendly_units=[source, war_dog_1, war_dog_2], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        ld_bonus = get_aura_leadership_bonus(source, game_map=game_map)
        oc_bonus = get_aura_objective_control_bonus(source, game_map=game_map)

    assert ld_bonus == -1
    assert oc_bonus == 1


def test_helhunt_infernal_aegis_self_applies_to_titanic_unit():
    from warhammer40k_ai.utility.aura_effects import get_aura_benefit_of_cover

    aura = Ability(
        name="Infernal Aegis (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 6\" of this model, "
            "that WAR DOG model has the Benefit of Cover."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("tyrant", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    war_dog_1 = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    war_dog_2 = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, war_dog_1, war_dog_2)
    game_map = _Map(friendly_units=[source, war_dog_1, war_dog_2], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        has_cover, reasons = get_aura_benefit_of_cover(source, game_map=game_map)

    assert has_cover is True
    assert any("Infernal Aegis" in reason for reason in reasons)


def test_helhunt_close_range_killers_self_applies_to_titanic_unit():
    from warhammer40k_ai.utility.aura_effects import get_aura_ap_bonus

    aura = Ability(
        name="Close-range Killers (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog model is within 9\" of this model, each time that "
            "WAR DOG model makes an attack that targets the closest enemy unit, improve the Armour "
            "Penetration characteristic of that attack by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("ruinator", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    war_dog_1 = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    war_dog_2 = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, war_dog_1, war_dog_2)
    attacker_model = source.models[0]
    target = _Unit("target")
    other_enemy = _Unit("other_enemy")
    weapon_profile = _WeaponProfile(ranged=True)
    distances = {
        (source, target): 4.0,
        (source, other_enemy): 9.0,
    }
    game_map = _Map(
        friendly_units=[source, war_dog_1, war_dog_2],
        enemy_units=[target, other_enemy],
        distances=distances,
    )

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        ap_bonus, _reasons = get_aura_ap_bonus(attacker_model, weapon_profile, target, game_map=game_map)

    assert ap_bonus == 1


def test_helhunt_weapon_keyword_auras_self_apply_to_titanic_unit():
    from warhammer40k_ai.utility.aura_effects import get_aura_weapon_keyword_bonuses

    aura = Ability(
        name="Pack Hunters (Aura)",
        faction_id="QT",
        description=(
            "While a friendly War Dog unit is within 9\" of this model, "
            "ranged weapons equipped by models in that unit have the [ASSAULT] ability."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )

    source = _Unit("helverin_alpha", abilities=[aura], keywords=["CHAOS KNIGHTS", "TITANIC"])
    war_dog_1 = _Unit("war_dog_1", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    war_dog_2 = _Unit("war_dog_2", keywords=["CHAOS KNIGHTS", "WAR DOG"])
    _create_chaos_knights_army(source, war_dog_1, war_dog_2)
    weapon_profile = _WeaponProfile(ranged=True)
    game_map = _Map(friendly_units=[source, war_dog_1, war_dog_2], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        bonuses = get_aura_weapon_keyword_bonuses(source, weapon_profile, game_map=game_map)

    assert any(rule["keyword"] == "ASSAULT" and rule["attack_type"] == "ranged" for rule in bonuses)
