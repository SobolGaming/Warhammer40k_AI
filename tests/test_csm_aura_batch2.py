from unittest.mock import patch

from warhammer40k_ai.units.ability import Ability


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


class _Unit:
    def __init__(self, name: str, *, abilities=None, keywords=None):
        self._id = name
        self.possible_abilities = list(abilities or [])
        self._keywords = {_norm(k) for k in (keywords or []) if _norm(k)}
        self.keywords = [str(k) for k in (keywords or []) if str(k)]
        self.faction_keywords = [str(k) for k in (keywords or []) if str(k)]
        self._army = None
        self.deployed = True

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, keyword: str) -> bool:
        key = _norm(keyword)
        if not key:
            return False
        if key in self._keywords:
            return True
        tokens = set()
        for item in self._keywords:
            tokens.update(item.split())
        if key in tokens:
            return True
        parts = [p for p in key.split() if p]
        if parts and all(p in tokens for p in parts):
            return True
        return False

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def get_effective_keywords(self):
        return list(self.keywords)

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords)

    def is_alive(self) -> bool:
        return True

    def get_attached_unit_root(self):
        return self


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


class _Map:
    def __init__(self, *, friendly_units, enemy_units):
        self._friendly_units = list(friendly_units)
        self._enemy_units = list(enemy_units)

    def get_friendly_units(self, _unit):
        return list(self._friendly_units)

    def get_enemy_units(self, _unit):
        return list(self._enemy_units)


def test_paragon_of_hatred_aura_grants_full_hit_reroll():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    aura = Ability(
        name="Paragon of Hatred (Aura)",
        faction_id="",
        description=(
            "While a friendly HERETIC ASTARTES unit is within 6\" (excluding DAMNED units) of this model, "
            "each time a model in that unit makes an attack, you can re-roll the Hit roll."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    attacker = _Unit("attacker", keywords=["HERETIC ASTARTES"])
    source = _Unit("abaddon", abilities=[aura])
    target = _Unit("target")
    profile = _WeaponProfile(ranged=True)
    game_map = _Map(friendly_units=[attacker, source], enemy_units=[target])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        mods = get_aura_attack_modifiers(attacker, target, profile, game_map=game_map)

    assert mods.reroll_hit_full is True


def test_dark_blessing_aura_grants_benefit_of_cover():
    from warhammer40k_ai.utility.aura_effects import get_aura_benefit_of_cover

    aura = Ability(
        name="Dark Blessing (Aura)",
        faction_id="",
        description=(
            "While a friendly Heretic Astartes Infantry unit is within 6\" of this model, "
            "each time a ranged attack is allocated to a model in that unit, "
            "that model has the Benefit of Cover against that attack."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    receiver = _Unit("receiver", keywords=["HERETIC ASTARTES", "INFANTRY"])
    source = _Unit("daemon_prince", abilities=[aura])
    game_map = _Map(friendly_units=[receiver, source], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        has_cover, _reasons = get_aura_benefit_of_cover(receiver, game_map=game_map)

    assert has_cover is True


def test_lord_of_traitor_legions_aura_grants_reroll_source():
    from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_reroll_sources

    aura = Ability(
        name="Lord of the Traitor Legions (Aura)",
        faction_id="",
        description=(
            "While a friendly HERETIC ASTARTES unit (excluding DAMNED units) is within 6\" of this model, "
            "you can re-roll Leadership and Battle-shock tests taken for that unit."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    receiver = _Unit("receiver", keywords=["HERETIC ASTARTES"])
    source = _Unit("abaddon", abilities=[aura])
    game_map = _Map(friendly_units=[receiver, source], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        sources = get_aura_battleshock_test_reroll_sources(receiver, game_map=game_map)

    assert "Lord of the Traitor Legions (Aura)" in sources


def test_icon_of_despair_aura_worsens_enemy_leadership_characteristic():
    from warhammer40k_ai.utility.aura_effects import get_enemy_aura_leadership_characteristic_penalty

    aura = Ability(
        name="Icon of Despair (Aura)",
        faction_id="",
        description=(
            "While an enemy unit is within 6\" of the bearer, worsen the Leadership characteristic of models in that unit by 1."
        ),
        type="Wargear",
        parameter="",
        legend=None,
    )
    target = _Unit("target", keywords=["INFANTRY"])
    enemy_source = _Unit("plague_marine", abilities=[aura])
    game_map = _Map(friendly_units=[], enemy_units=[enemy_source])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        penalty = get_enemy_aura_leadership_characteristic_penalty(target, game_map=game_map)

    assert penalty == 1


def test_malevolent_locus_aura_improves_friendly_leadership():
    from warhammer40k_ai.utility.aura_effects import get_aura_leadership_bonus

    aura = Ability(
        name="Malevolent Locus (Aura)",
        faction_id="",
        description=(
            "While a friendly HERETIC ASTARTES model is wholly within 9\" of this FORTIFICATION, "
            "improve that unit's Leadership characteristic by 1."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    receiver = _Unit("receiver", keywords=["HERETIC ASTARTES"])
    source = _Unit("crown", abilities=[aura])
    game_map = _Map(friendly_units=[receiver, source], enemy_units=[])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        bonus = get_aura_leadership_bonus(receiver, game_map=game_map)

    assert bonus == -1


def test_mind_breaking_mutations_oc_penalty_excludes_vehicles():
    from warhammer40k_ai.utility.aura_effects import get_enemy_aura_move_oc_penalties

    aura = Ability(
        name="Mind-breaking Mutations (Aura)",
        faction_id="",
        description=(
            "While an enemy unit (excluding VEHICLE units) is within 3\" of this unit, "
            "subtract 1 from the Objective Control characteristic of models in that enemy unit."
        ),
        type="Datasheet",
        parameter="",
        legend=None,
    )
    enemy_source = _Unit("spawn", abilities=[aura])
    infantry_target = _Unit("infantry", keywords=["INFANTRY"])
    vehicle_target = _Unit("vehicle", keywords=["VEHICLE"])
    infantry_map = _Map(friendly_units=[], enemy_units=[enemy_source])
    vehicle_map = _Map(friendly_units=[], enemy_units=[enemy_source])

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        move_pen_i, oc_pen_i = get_enemy_aura_move_oc_penalties(infantry_target, game_map=infantry_map)
        move_pen_v, oc_pen_v = get_enemy_aura_move_oc_penalties(vehicle_target, game_map=vehicle_map)

    assert move_pen_i == 0
    assert oc_pen_i == -1
    assert move_pen_v == 0
    assert oc_pen_v == 0
