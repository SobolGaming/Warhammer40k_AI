from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        movement: str = "6",
        toughness: str = "4",
        wounds: str = "4",
        abilities: list[dict] | None = None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Orks",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    movement: str = "6",
    toughness: str = "4",
    wounds: str = "4",
    abilities: list[dict] | None = None,
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        faction_name=faction_name,
        model_count=model_count,
        keywords=keywords,
        faction_keywords=faction_keywords,
        attached_to=attached_to,
        movement=movement,
        toughness=toughness,
        wounds=wounds,
        abilities=abilities,
    )
    return Unit(datasheet)


def _make_ork_army(detachment: str) -> Army:
    army = Army("Orks", detachment)
    army.faction_id = "ORK"
    return army


def _apply_enhancement(unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _make_profile(*, name: str, weapon_type: str, strength: str) -> WargearProfile:
    is_ranged = str(weapon_type or "").strip().lower() == "ranged"
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    return WargearProfile(
        profile_name=name,
        wargear_data={
            "range": "24" if is_ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_ork_passive_enhancement_descriptors_registered():
    expected = {
        "000008885005": "Tellyporta",
        "000008868002": "Glory Hog",
        "000008868003": "Proper Killy",
        "000008868004": "Skrag Every Stash!",
        "000008868005": "Surly as a Squiggoth",
        "000008877002": "Gitfinder Googlez",
        "000008877004": "Smoky Gubbinz",
        "000010712003": "Git-spotter Squig",
        "000009795002": "Skwad Leader",
        "000009795003": "Mek Kaptin",
        "000009795005": "Gob Boomer",
    }
    for enhancement_id, expected_name in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == expected_name


def test_tellyporta_grants_deep_strike_to_bearer_unit():
    army = _make_ork_army("Bully Boyz")
    warboss = _make_unit(
        "Warboss in Mega Armour",
        "orks-warboss-mega",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    army.add_unit(warboss)

    _apply_enhancement(warboss, "Tellyporta")

    assert warboss.has_deep_strike() is True


def test_glory_hog_and_proper_killy_apply_scouts_and_bearer_melee_damage_bonus():
    army = _make_ork_army("Da Big Hunt")
    squigosaur = _make_unit(
        "Beastboss on Squigosaur",
        "orks-beastboss-on-squigosaur",
        keywords=["CHARACTER", "MONSTER", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    snagga = _make_unit(
        "Beast Snagga Boss",
        "orks-beast-snagga-boss",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    army.add_unit(squigosaur)
    army.add_unit(snagga)

    _apply_enhancement(squigosaur, "Glory Hog")
    _apply_enhancement(snagga, "Proper Killy")

    has_scout, distance = squigosaur.has_scout()
    assert has_scout is True
    assert float(distance) == 9.0
    assert int(snagga.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0) == 1


def test_skrag_every_stash_registers_bearer_only_sticky_objective_claim_rule():
    army = _make_ork_army("Da Big Hunt")
    bearer = _make_unit(
        "Beastboss",
        "orks-skrag-bearer",
        keywords=["CHARACTER", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    army.add_unit(bearer)
    bearer.deployed = True
    bearer.reserve_status = "deployed"
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)

    _apply_enhancement(bearer, "Skrag Every Stash!")

    objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
    claim_rule = bearer.command_phase_sticky_objective_claim_rule(objective_point)

    assert claim_rule is not None
    assert str(claim_rule.get("source_scope", "") or "") == "bearer"
    assert bool(claim_rule.get("allow_embarked_transport", False)) is False
    assert str(claim_rule.get("source_model_id", "") or "") == str(
        bearer.special_rules.get("enhancement_skrag_every_stash_bearer_model_id", "") or ""
    )


def test_surly_as_a_squiggoth_applies_defensive_wound_penalty_when_strength_exceeds_toughness():
    ork_army = _make_ork_army("Da Big Hunt")
    bodyguard = _make_unit(
        "Squighog Boyz",
        "orks-squighog-boyz",
        keywords=["MOUNTED"],
        faction_keywords=["ORKS"],
        toughness="4",
    )
    leader = _make_unit(
        "Beastboss on Squigosaur",
        "orks-surly-bearer",
        keywords=["CHARACTER", "MONSTER", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
        toughness="6",
    )
    ork_army.add_unit(bodyguard)
    ork_army.add_unit(leader)
    leader.attach_to_unit(bodyguard)
    _apply_enhancement(leader, "Surly as a Squiggoth")

    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-surly-attacker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    enemy_army.add_unit(enemy)

    profile = _make_profile(name="Enemy Blade", weapon_type="melee", strength="6")
    wound_result = profile._wound_target_with_tracking(
        bodyguard,
        enemy.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any(
        "Surly as a Squiggoth" in str(mod or "")
        for mod in list(wound_result.get("modifiers", []) or [])
    )


def test_gitfinder_googlez_and_git_spotter_squig_grant_ranged_ignores_cover():
    dread_mob = _make_ork_army("Dread Mob")
    gitfinder_unit = _make_unit(
        "Mek",
        "orks-gitfinder-mek",
        keywords=["CHARACTER", "INFANTRY", "MEK"],
        faction_keywords=["ORKS"],
    )
    dread_mob.add_unit(gitfinder_unit)
    target = _make_unit(
        "Enemy Target",
        "enemy-target-gitfinder",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dread_mob.add_unit(target)
    _apply_enhancement(gitfinder_unit, "Gitfinder Googlez")
    gitfinder_bonuses = gitfinder_unit.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=gitfinder_unit.models[0],
    )
    assert bool(gitfinder_bonuses.get("ignores_cover", False))

    freebooter = _make_ork_army("Freebooter Krew")
    git_spotter_unit = _make_unit(
        "Kaptin",
        "orks-git-spotter-kaptin",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    freebooter.add_unit(git_spotter_unit)
    enemy_target = _make_unit(
        "Enemy Target",
        "enemy-target-git-spotter",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    freebooter.add_unit(enemy_target)
    _apply_enhancement(git_spotter_unit, "Git-spotter Squig")
    git_spotter_bonuses = git_spotter_unit.get_attack_keyword_bonuses(
        target=enemy_target,
        attack_type="ranged",
        model=git_spotter_unit.models[0],
    )
    assert bool(git_spotter_bonuses.get("ignores_cover", False))


def test_smoky_gubbinz_grants_stealth_to_bearer_unit():
    army = _make_ork_army("Dread Mob")
    mek = _make_unit(
        "Mek",
        "orks-smoky-mek",
        keywords=["CHARACTER", "INFANTRY", "MEK"],
        faction_keywords=["ORKS"],
    )
    army.add_unit(mek)

    _apply_enhancement(mek, "Smoky Gubbinz")

    assert mek.has_stealth() is True


def test_skwad_leader_allows_kommandos_attachment_and_grants_infiltrate_and_stealth_while_leading():
    army = _make_ork_army("Taktikal Brigade")
    kommandos = _make_unit(
        "Kommandos",
        "orks-kommandos",
        keywords=["INFANTRY", "KOMMANDOS"],
        faction_keywords=["ORKS"],
    )
    warboss = _make_unit(
        "Warboss",
        "orks-skwad-leader",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
        attached_to=[kommandos.get_datasheet_id()],
    )
    army.add_unit(kommandos)
    army.add_unit(warboss)
    _apply_enhancement(warboss, "Skwad Leader")

    assert warboss.can_attach_to(kommandos) is True
    warboss.attach_to_unit(kommandos)
    assert warboss.has_infiltrate() is True
    assert warboss.has_stealth() is True


def test_mek_kaptin_allows_flash_gitz_attachment_and_ranged_full_hit_rerolls():
    army = _make_ork_army("Taktikal Brigade")
    flash_gitz = _make_unit(
        "Flash Gitz",
        "orks-flash-gitz",
        keywords=["INFANTRY", "FLASH GITZ"],
        faction_keywords=["ORKS"],
    )
    big_mek = _make_unit(
        "Big Mek",
        "orks-mek-kaptin",
        keywords=["CHARACTER", "INFANTRY", "MEK"],
        faction_keywords=["ORKS"],
        attached_to=[flash_gitz.get_datasheet_id()],
    )
    army.add_unit(flash_gitz)
    army.add_unit(big_mek)
    _apply_enhancement(big_mek, "Mek Kaptin")

    assert big_mek.can_attach_to(flash_gitz) is True
    big_mek.attach_to_unit(flash_gitz)

    hit_mods = flash_gitz.get_model_hit_reroll_modifiers(
        flash_gitz.models[0],
        attack_type="ranged",
    )
    assert bool(hit_mods.get("reroll_hit_full", False))
    assert any("Mek Kaptin" in str(reason or "") for reason in list(hit_mods.get("reroll_hit_full_reasons", ()) or ()))


def test_ard_case_adds_toughness_and_removes_firing_deck():
    army = _make_ork_army("War Horde")
    battlewagon = _make_unit(
        "Battlewagon",
        "orks-battlewagon-ard-case",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        toughness="10",
        abilities=[
            {
                "name": "Firing Deck",
                "description": "Firing Deck 22.",
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "'Ard Case",
                "description": "Add 2 to the bearer's Toughness characteristic, but it no longer has the Firing Deck ability.",
                "type": "Wargear",
                "parameter": "",
            },
        ],
    )
    army.add_unit(battlewagon)
    battlewagon._refresh_bearer_keyword_flags()

    assert int(battlewagon.toughness) == 12
    assert battlewagon.has_firing_deck() == (False, 0)


def test_blastajet_force_field_applies_invulnerable_save_and_removes_grenades_keyword():
    army = _make_ork_army("War Horde")
    blastajet = _make_unit(
        "Wazbom Blastajet",
        "orks-wazbom-blastajet-force-field",
        keywords=["VEHICLE", "AIRCRAFT", "GRENADES"],
        faction_keywords=["ORKS"],
        toughness="9",
        abilities=[
            {
                "name": "Blastajet Force Field",
                "description": "The bearer has a 4+ invulnerable save, but it loses the Grenades keyword.",
                "type": "Wargear",
                "parameter": "",
            }
        ],
    )
    army.add_unit(blastajet)
    blastajet.models[0].optional_wargear.append("Blastajet Force Field")
    blastajet._refresh_bearer_keyword_flags()

    inv_value, _source = blastajet.get_model_invulnerable_save_override(blastajet.models[0])
    assert int(inv_value or 0) == 4
    assert blastajet.has_any_keyword("GRENADES") is False
