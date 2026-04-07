from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        wounds: int = 4,
        model_count: int = 1,
        attached_to=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    wounds: int = 4,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            model_count=model_count,
            attached_to=attached_to,
        )
    )


def _build_army(detachment: str = "Warrior Bioform Onslaught") -> Army:
    army = Army.with_detachment("Tyranids", detachment)
    army.faction_id = "TYR"
    return army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="TYR",
        detachment="Warrior Bioform Onslaught",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _invalidate_unit_cache(unit: Unit) -> None:
    invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
    if callable(invalidate_cache):
        invalidate_cache()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    if bearer_id:
        for model in list(getattr(unit, "models", []) or []):
            ids = {
                str(get_entity_id(model) or "").strip(),
                str(getattr(model, "id", getattr(model, "_id", "")) or "").strip(),
            }
            if bearer_id in ids:
                return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def test_warrior_bioform_enhancement_descriptors_are_registered():
    expected = {
        "000009737002": ("Synaptic Tyrant", "attachment_override"),
        "000009737003": ("Ocular Adaptation", "hit_roll_bonus"),
        "000009737004": ("Sensory Assimilation", "target_hit_roll_penalty"),
        "000009737005": ("Elevated Might", "charge_after_advance"),
    }

    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id, name=name)
        assert descriptor is not None
        assert descriptor.name == name
        assert str(descriptor.effect) == effect


def test_synaptic_tyrant_grants_tyranid_warriors_attachment_override():
    army = _build_army()
    leader = _make_unit(
        "Neurotyrant",
        "neurotyrant-ds",
        keywords=["TYRANIDS", "CHARACTER", "NEUROTYRANT", "SYNAPSE"],
        attached_to=["neurogaunts-ds"],
    )
    warriors = _make_unit(
        "Tyranid Warriors with Ranged Bio-weapons",
        "warriors-ranged-ds",
        keywords=["TYRANIDS", "INFANTRY"],
    )
    other = _make_unit(
        "Termagants",
        "termagants-ds",
        keywords=["TYRANIDS", "INFANTRY"],
    )
    army.add_unit(warriors)
    army.add_unit(other)
    army.add_unit(leader)

    assert leader.can_attach_to(warriors) is False

    _apply_enhancement(leader, enhancement_id="000009737002", enhancement_name="Synaptic Tyrant")

    allowed_names = list(getattr(leader, "can_be_attached_to_names", []) or [])
    assert "Tyranid Warriors with Ranged Bio-weapons" in allowed_names
    assert "Tyranid Warriors with Melee Bio-weapons" in allowed_names
    assert leader.can_attach_to(warriors) is True
    assert leader.can_attach_to(other) is False

    leader.attach_to_unit(warriors)
    assert leader.attached_to is warriors
    assert leader in list(getattr(warriors, "attached_leaders", []) or [])


def test_ocular_adaptation_grants_hit_bonus_to_bearer_unit_and_ends_when_bearer_dies():
    army = _build_army()
    prime = _make_unit(
        "Winged Tyranid Prime",
        "winged-prime-ds",
        keywords=["TYRANIDS", "CHARACTER", "INFANTRY", "WINGED TYRANID PRIME"],
        attached_to=["gargoyles-ds"],
    )
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        "warriors-melee-ds",
        keywords=["TYRANIDS", "INFANTRY"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-ds",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(prime)
    army.add_unit(warriors)
    army.add_unit(enemy)

    _apply_enhancement(prime, enhancement_id="000009737003", enhancement_name="Ocular Adaptation")

    solo_mods = prime.get_unit_hit_reroll_modifiers("melee", target=enemy, attacker_model=prime.models[0])
    assert int(solo_mods.get("hit", 0) or 0) == 1
    assert any("Ocular Adaptation" in str(reason or "") for reason in list(solo_mods.get("hit_reasons", ()) or ()))

    _attach_leader(warriors, prime)

    attached_mods = warriors.get_unit_hit_reroll_modifiers("melee", target=enemy, attacker_model=warriors.models[0])
    assert int(attached_mods.get("hit", 0) or 0) == 1
    assert any(
        "Ocular Adaptation" in str(reason or "") for reason in list(attached_mods.get("hit_reasons", ()) or ())
    )

    bearer = _bearer_model(prime)
    bearer.wounds = 0
    _invalidate_unit_cache(prime)
    _invalidate_unit_cache(warriors)

    expired_mods = warriors.get_unit_hit_reroll_modifiers("melee", target=enemy, attacker_model=warriors.models[0])
    assert int(expired_mods.get("hit", 0) or 0) == 0


def test_sensory_assimilation_applies_target_hit_penalty_and_ends_when_bearer_dies():
    army = _build_army()
    prime = _make_unit(
        "Winged Tyranid Prime",
        "winged-prime-sensory-ds",
        keywords=["TYRANIDS", "CHARACTER", "INFANTRY", "WINGED TYRANID PRIME"],
        attached_to=["gargoyles-ds"],
    )
    warriors = _make_unit(
        "Tyranid Warriors with Ranged Bio-weapons",
        "warriors-ranged-sensory-ds",
        keywords=["TYRANIDS", "INFANTRY"],
    )
    army.add_unit(prime)
    army.add_unit(warriors)

    _apply_enhancement(prime, enhancement_id="000009737004", enhancement_name="Sensory Assimilation")

    solo_penalty, solo_reasons = prime.get_target_hit_roll_penalty("ranged")
    assert int(solo_penalty) == 1
    assert any("Sensory Assimilation" in str(reason or "") for reason in list(solo_reasons or ()))

    _attach_leader(warriors, prime)

    attached_penalty, attached_reasons = warriors.get_target_hit_roll_penalty("melee")
    assert int(attached_penalty) == 1
    assert any("Sensory Assimilation" in str(reason or "") for reason in list(attached_reasons or ()))

    bearer = _bearer_model(prime)
    bearer.wounds = 0
    _invalidate_unit_cache(prime)
    _invalidate_unit_cache(warriors)

    expired_penalty, expired_reasons = warriors.get_target_hit_roll_penalty("ranged")
    assert int(expired_penalty) == 0
    assert tuple(expired_reasons or ()) == ()


def test_elevated_might_allows_charge_after_advance_for_bearer_unit_until_bearer_dies():
    army = _build_army()
    prime = _make_unit(
        "Winged Tyranid Prime",
        "winged-prime-elevated-ds",
        keywords=["TYRANIDS", "CHARACTER", "INFANTRY", "WINGED TYRANID PRIME"],
        attached_to=["gargoyles-ds"],
    )
    warriors = _make_unit(
        "Tyranid Warriors with Melee Bio-weapons",
        "warriors-melee-elevated-ds",
        keywords=["TYRANIDS", "INFANTRY"],
    )
    army.add_unit(prime)
    army.add_unit(warriors)

    _apply_enhancement(prime, enhancement_id="000009737005", enhancement_name="Elevated Might")

    assert prime.can_charge_after_advance() is True

    _attach_leader(warriors, prime)

    assert warriors.can_charge_after_advance() is True

    bearer = _bearer_model(prime)
    bearer.wounds = 0
    _invalidate_unit_cache(prime)
    _invalidate_unit_cache(warriors)

    assert warriors.can_charge_after_advance() is False
