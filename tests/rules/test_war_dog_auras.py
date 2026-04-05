from unittest.mock import patch

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
    def __init__(self, name: str, *, abilities=None, keywords=None):
        self._id = name
        self.possible_abilities = list(abilities or [])
        self._keywords = {str(k).strip().lower() for k in (keywords or []) if str(k).strip()}
        self._army = None
        self.deployed = True

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, kw: str) -> bool:
        return str(kw).strip().lower() in self._keywords

    def is_alive(self) -> bool:
        return True

    def get_attached_unit_root(self):
        return self


class _Model:
    def __init__(self, unit: _Unit):
        self.parent_unit = unit


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
