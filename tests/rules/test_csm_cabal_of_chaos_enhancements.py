from __future__ import annotations

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 2,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
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
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 2,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _make_melee_profile(*, strength: int = 4, ap: int = 0) -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Blade",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _apply_enhancement(unit: Unit, *, enh_id: str, name: str, description: str = "") -> None:
    enh = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="CSM",
        detachment="Cabal of Chaos",
        points=0,
        description=description,
    )
    unit.enhancement = enh
    enh.apply_to_unit(unit)


def _bearer_and_other_models(unit: Unit):
    sr = dict(getattr(unit, "special_rules", {}) or {})
    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
    bearer = None
    other = None
    for model in list(getattr(unit, "models", []) or []):
        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
        if model_id and model_id == bearer_id:
            bearer = model
        else:
            other = model
    return bearer, other


def test_touched_by_the_warp_adds_psyker_to_bearer_model_only():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    unit = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    army.add_unit(unit)

    _apply_enhancement(
        unit,
        enh_id="000010151002",
        name="Touched by the Warp",
        description="HERETIC ASTARTES model only (excluding Khorne models). The bearer gains the Psyker keyword.",
    )

    bearer, other = _bearer_and_other_models(unit)
    assert bearer is not None
    assert bearer.has_keyword("PSYKER")
    assert other is not None
    assert not other.has_keyword("PSYKER")
    assert "PSYKER" in {str(k).upper() for k in (unit.get_effective_keywords() or [])}


def test_eyes_of_zdesh_grants_scouts_6():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    unit = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    army.add_unit(unit)

    _apply_enhancement(
        unit,
        enh_id="000010151003",
        name="Eyes of Z'desh",
        description="HERETIC ASTARTES model only. Models in the bearer's unit have the Scouts 6\" ability.",
    )

    has_scout, distance = unit.has_scout()
    assert has_scout is True
    assert float(distance) == 6.0


def test_mind_blade_grants_lance_to_non_bearer_model_in_unit():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    attacker = _make_unit(
        "Master of Possession",
        keywords=["CHARACTER", "HERETIC ASTARTES", "PSYKER"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
    )
    army.add_unit(attacker)
    enemy_army.add_unit(target)

    _apply_enhancement(
        attacker,
        enh_id="000010151004",
        name="Mind Blade",
        description="Psyker model only. Melee weapons equipped by models in the bearer's unit have the [LANCE] ability.",
    )

    _bearer, other = _bearer_and_other_models(attacker)
    assert other is not None
    attacker.round_state.charged_this_round = True

    profile = _make_melee_profile(strength=4, ap=0)
    attack_instance = {}
    profile._hit_target_with_tracking(
        target,
        other,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert attack_instance.get("bonus_lance") is True

    wound = profile._wound_target_with_tracking(
        target,
        other,
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound["wound"] is True
    assert any("Lance" in str(reason) for reason in list(wound.get("modifiers", [])))


def test_infernal_avatar_buffs_only_bearer_melee_profile():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    unit = _make_unit(
        "Daemon Prince",
        keywords=["CHARACTER", "HERETIC ASTARTES", "DAEMON PRINCE"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )
    army.add_unit(unit)
    enemy_army.add_unit(target)

    _apply_enhancement(
        unit,
        enh_id="000010151005",
        name="Infernal Avatar",
        description=(
            "Heretic Astartes Daemon Prince or Heretic Astartes Daemon Prince with Wings model only. "
            "Improve the Strength characteristic of melee weapons equipped by the bearer by 2, and improve "
            "the Armour Penetration characteristic of those weapons by 1."
        ),
    )

    bearer, other = _bearer_and_other_models(unit)
    assert bearer is not None
    assert other is not None

    profile = _make_melee_profile(strength=4, ap=0)
    assert int(profile.get_effective_ap(bearer, target)) == -1
    assert int(profile.get_effective_ap(other, target)) == 0

    wound_bearer = profile._wound_target_with_tracking(
        target,
        bearer,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_other = profile._wound_target_with_tracking(
        target,
        other,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(wound_bearer["needed"]) == 3
    assert int(wound_other["needed"]) == 5


def test_cabal_enhancement_effects_do_not_apply_outside_cabal_detachment():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Renegade Raiders")
    army.faction_id = "CSM"
    unit = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    army.add_unit(unit)

    _apply_enhancement(
        unit,
        enh_id="000010151002",
        name="Touched by the Warp",
        description="HERETIC ASTARTES model only (excluding Khorne models). The bearer gains the Psyker keyword.",
    )

    assert not bool(unit.special_rules.get("enhancement_touched_by_the_warp"))
    assert all(not model.has_keyword("PSYKER") for model in list(getattr(unit, "models", []) or []))
