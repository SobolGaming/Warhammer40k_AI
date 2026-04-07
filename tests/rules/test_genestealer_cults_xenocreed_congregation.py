from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
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
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army.with_detachment("Genestealer Cults", "Xenocreed Congregation", points_limit=2000)
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = ["BODYGUARD"]
    leader.attached_to = bodyguard
    leaders = list(getattr(bodyguard, "attached_leaders", []) or [])
    leaders.append(leader)
    bodyguard.attached_leaders = leaders


def _has_fnp_value(entries: list[tuple[int, str | None]], value: int) -> bool:
    for dice_value, _cond in list(entries or []):
        if int(dice_value or 0) == int(value):
            return True
    return False


def _apply_xenocreed_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="GC",
        detachment="Xenocreed Congregation",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def test_unquestioning_fanaticism_grants_reroll_advance_and_charge_to_eligible_led_units():
    game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(clamavus)
    _attach_leader(neophytes, clamavus)

    purestrains = _make_unit(
        "Purestrain Genestealers",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    second_clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(purestrains)
    gsc_army.add_unit(second_clamavus)
    _attach_leader(purestrains, second_clamavus)

    mgr = gsc_army.genestealer_cults_detachments

    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_advance_applies(neophytes)) is True
    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_charge_applies(neophytes)) is True
    assert bool(neophytes.can_reroll_advance_roll()) is True
    assert bool(neophytes.can_reroll_charge_roll(game=game)) is True

    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_advance_applies(purestrains)) is False
    assert bool(mgr.xenocreed_unquestioning_fanaticism_reroll_charge_applies(purestrains)) is False


def test_unquestioning_fanaticism_fnp_applies_only_to_magus_primus_or_iconward_leader_models():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    acolytes = _make_unit(
        "Acolyte Hybrids with Autopistols",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(acolytes)
    gsc_army.add_unit(primus)
    _attach_leader(acolytes, primus)

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(clamavus)
    _attach_leader(neophytes, clamavus)

    primus_fnp = list(primus.has_feel_no_pain(target_model=primus.models[0]) or [])
    acolyte_fnp = list(acolytes.has_feel_no_pain(target_model=acolytes.models[0]) or [])
    clamavus_fnp = list(clamavus.has_feel_no_pain(target_model=clamavus.models[0]) or [])

    assert _has_fnp_value(primus_fnp, 3)
    assert not _has_fnp_value(acolyte_fnp, 3)
    assert not _has_fnp_value(clamavus_fnp, 3)


def test_xenocreed_enhancement_descriptors_registered() -> None:
    gene_sire = get_enhancement_tool_descriptor(enhancement_id="000009071002")
    assert gene_sire is not None
    assert gene_sire.name == "Gene-sire's Reliquant"
    assert gene_sire.effect == "reroll_battleshock_tests"

    denunciator = get_enhancement_tool_descriptor(enhancement_id="000009071003")
    assert denunciator is not None
    assert denunciator.name == "Denunciator of Tyrants"
    assert denunciator.effect == "add_hit_and_wound_roll_modifier"
    assert int(denunciator.effect_params.get("hit_roll_bonus", 0) or 0) == 1
    assert int(denunciator.effect_params.get("wound_roll_bonus", 0) or 0) == 1

    deeds = get_enhancement_tool_descriptor(enhancement_id="000009071004")
    assert deeds is not None
    assert deeds.name == "Deeds That Speak to the Masses"
    assert deeds.effect == "additional_starting_resurgence_points"
    assert int(deeds.effect_params.get("additional_resurgence_points", 0) or 0) == 2

    incendiary = get_enhancement_tool_descriptor(enhancement_id="000009071005")
    assert incendiary is not None
    assert incendiary.name == "Incendiary Inspiration"
    assert incendiary.effect == "charge_after_advance"
    assert bool(incendiary.effect_params.get("charge_after_advance", False)) is True


def test_gene_sires_reliquant_adds_battleshock_reroll_source_to_bearers_unit() -> None:
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(primus)
    _attach_leader(neophytes, primus)

    _apply_xenocreed_enhancement(
        primus,
        enhancement_id="000009071002",
        name="Gene-sire's Reliquant",
        description="MAGUS, PRIMUS or ACOLYTE ICONWARD model only. You can re-roll Battle-shock tests taken for the bearer's unit.",
    )

    assert "Gene-sire's Reliquant" in neophytes.leading_leadership_reroll_sources()


def test_denunciator_of_tyrants_adds_hit_and_wound_against_character_targets() -> None:
    _game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(primus)
    _attach_leader(neophytes, primus)

    _apply_xenocreed_enhancement(
        primus,
        enhancement_id="000009071003",
        name="Denunciator of Tyrants",
        description=(
            "MAGUS, PRIMUS or ACOLYTE ICONWARD model only. Each time a model in the bearer's unit makes an attack "
            "that targets a CHARACTER unit, add 1 to the Hit roll and add 1 to the Wound roll."
        ),
    )

    character_target = _make_unit(
        "Enemy Character",
        faction_name="Enemy",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    non_character_target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_army.add_unit(character_target)
    enemy_army.add_unit(non_character_target)

    hit_vs_character = neophytes.get_unit_hit_reroll_modifiers("ranged", target=character_target)
    wound_vs_character = neophytes.get_unit_wound_reroll_modifiers("ranged", target=character_target)
    hit_vs_non_character = neophytes.get_unit_hit_reroll_modifiers("ranged", target=non_character_target)
    wound_vs_non_character = neophytes.get_unit_wound_reroll_modifiers("ranged", target=non_character_target)

    assert int(hit_vs_character.get("hit", 0) or 0) >= 1
    assert any(
        "denunciator of tyrants" in str(reason or "").strip().lower()
        for reason in hit_vs_character.get("hit_reasons", ())
    )
    assert int(wound_vs_character.get("wound", 0) or 0) >= 1
    assert any(
        "denunciator of tyrants" in str(reason or "").strip().lower()
        for reason in wound_vs_character.get("wound_reasons", ())
    )
    assert not any(
        "denunciator of tyrants" in str(reason or "").strip().lower()
        for reason in hit_vs_non_character.get("hit_reasons", ())
    )
    assert not any(
        "denunciator of tyrants" in str(reason or "").strip().lower()
        for reason in wound_vs_non_character.get("wound_reasons", ())
    )


def test_deeds_that_speak_to_the_masses_adds_two_starting_resurgence_points() -> None:
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(primus)
    _attach_leader(neophytes, primus)

    _apply_xenocreed_enhancement(
        primus,
        enhancement_id="000009071004",
        name="Deeds That Speak to the Masses",
        description="Magus, Primus or Acolyte Iconward model only. You start the battle with 2 additional Resurgence points.",
    )

    gsc_army.on_battle_round_start(1)

    assert int(gsc_army.cult_ambush.resurgence_points or 0) == 12


def test_incendiary_inspiration_allows_bearers_unit_to_charge_after_advancing() -> None:
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(primus)
    _attach_leader(neophytes, primus)

    _apply_xenocreed_enhancement(
        primus,
        enhancement_id="000009071005",
        name="Incendiary Inspiration",
        description="MAGUS, PRIMUS or ACOLYTE ICONWARD model only. The bearer's unit is eligible to declare a charge in a turn in which it Advanced.",
    )

    assert bool(neophytes.can_charge_after_advance()) is True
