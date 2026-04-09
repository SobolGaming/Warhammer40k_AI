from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


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


def _make_ranged_profile(*, name: str = "Autogun", skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentRangedWargear",
        (),
        {
            "name": str(name),
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(*, name: str = "Cult Knife", skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentMeleeWargear",
        (),
        {
            "name": str(name),
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * 1.5), float(y), 0.0, 0.0)


def _publish_current_phase_start(game: Game) -> None:
    current_player = game.get_current_player()
    assert current_player is not None
    game.event_system.publish("phase_start", player=current_player, phase=game.phase)


def _find_request(
    game: Game,
    *,
    decision_type: str,
    ability: str | None = None,
    reactive_move_kind: str | None = None,
):
    target_ability = str(ability or "").strip().lower()
    target_kind = str(reactive_move_kind or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type or ""):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if target_ability and str(ctx.get("ability", "") or "").strip().lower() != target_ability:
            continue
        if target_kind and str(ctx.get("reactive_move_kind", "") or "").strip().lower() != target_kind:
            continue
        return req
    return None


def _pending_reaction_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _attach_fake_wargear(unit: Unit, *, melee_names: list[str] | None = None, ranged_names: list[str] | None = None) -> None:
    melee = [str(name) for name in list(melee_names or []) if str(name)]
    ranged = [str(name) for name in list(ranged_names or []) if str(name)]
    for model in list(getattr(unit, "models", []) or []):
        wargear = []
        model_id = str(getattr(model, "id", "") or "")
        for idx, name in enumerate(melee):
            wargear.append(
                type(
                    "_FakeMeleeWargear",
                    (),
                    {
                        "id": f"fake-melee-{model_id}-{idx}",
                        "name": name,
                        "is_melee": staticmethod(lambda: True),
                        "is_ranged": staticmethod(lambda: False),
                    },
                )()
            )
        for idx, name in enumerate(ranged):
            wargear.append(
                type(
                    "_FakeRangedWargear",
                    (),
                    {
                        "id": f"fake-ranged-{model_id}-{idx}",
                        "name": name,
                        "is_melee": staticmethod(lambda: False),
                        "is_ranged": staticmethod(lambda: True),
                    },
                )()
            )
        model.wargear = wargear


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


def test_xenocreed_stratagem_descriptors_registered() -> None:
    expected = {
        "000009072002": ("VENGEANCE FOR THE MARTYR!", "mark_destroying_enemy_for_hit_rerolls"),
        "000009072003": ("FRENZIED DEVOTION", "non_character_melee_attacks_ws_bonus_and_hazardous"),
        "000009072004": ("TIRELESS FERVOUR", "charge_after_advance_or_fall_back_with_conditional_reroll"),
        "000009072005": ("TRANSCENDENT CELERITY", "grant_assault_to_ranged_weapons"),
        "000009072006": ("THE DOWNTRODDEN RISE", "cult_ambush_setup_without_marker"),
        "000009072007": ("THE PATH OF ANGUISH", "reactive_surge_move_toward_closest_enemy"),
    }

    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_frenzied_devotion_applies_attacks_ws_and_hazardous_only_to_non_character_models_and_cleans_up() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

    acolytes = _make_unit(
        "Acolyte Hybrids",
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
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(acolytes)
    gsc_army.add_unit(primus)
    enemy_army.add_unit(enemy)
    _attach_leader(acolytes, primus)
    _attach_fake_wargear(acolytes, melee_names=["Cult Knife"])
    _attach_fake_wargear(primus, melee_names=["Cult Knife"])
    _set_unit_position(acolytes, 0.0, 0.0)
    _set_unit_position(primus, 0.0, 0.0)
    _set_unit_position(enemy, 0.5, 0.0)
    game.map.units = [acolytes, primus, enemy]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    _publish_current_phase_start(game)

    assert bool(manager.use("FRENZIED DEVOTION", unit=acolytes, phase_name="Fight phase")) is True

    attacks_bonus, _reasons = acolytes.models[0].get_temporary_weapon_attacks_bonus("Cult Knife")
    bodyguard_keywords = acolytes.models[0].get_temporary_weapon_keyword_bonuses("Cult Knife")
    leader_attacks_bonus, _leader_reasons = primus.models[0].get_temporary_weapon_attacks_bonus("Cult Knife")
    leader_keywords = primus.models[0].get_temporary_weapon_keyword_bonuses("Cult Knife")

    assert int(attacks_bonus or 0) == 1
    assert any(str(rule.get("keyword", "") or "").upper() == "HAZARDOUS" for rule in bodyguard_keywords)
    assert int(leader_attacks_bonus or 0) == 0
    assert leader_keywords == []

    melee = _make_melee_profile(name="Cult Knife", skill="4+")
    with patch.object(wargear_mod, "get_roll", return_value=4):
        bodyguard_attack = melee.attack(enemy.models[0], acolytes.models[0], game_map=game.map)
    with patch.object(wargear_mod, "get_roll", return_value=4):
        leader_attack = melee.attack(enemy.models[0], primus.models[0], game_map=game.map)

    assert int(bodyguard_attack.hit_results[0].get("final_needed", 0) or 0) == 3
    assert int(leader_attack.hit_results[0].get("final_needed", 0) or 0) == 4

    gsc_army.genestealer_cults_detachments.cleanup_on_phase_end(BattleRoundPhases.FIGHT_PHASE, gsc_player)

    cleared_bonus, _ = acolytes.models[0].get_temporary_weapon_attacks_bonus("Cult Knife")
    assert int(cleared_bonus or 0) == 0
    assert acolytes.models[0].get_temporary_weapon_keyword_bonuses("Cult Knife") == []


def test_transcendent_celerity_grants_assault_and_cleans_up() -> None:
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

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
    _attach_fake_wargear(neophytes, ranged_names=["Autogun"])
    _attach_fake_wargear(primus, ranged_names=["Autogun"])
    game.map.units = [neophytes, primus]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    _publish_current_phase_start(game)

    assert bool(manager.use("TRANSCENDENT CELERITY", unit=neophytes, phase_name="Shooting phase")) is True

    bodyguard_keywords = neophytes.models[0].get_temporary_weapon_keyword_bonuses("Autogun")
    leader_keywords = primus.models[0].get_temporary_weapon_keyword_bonuses("Autogun")
    assert any(str(rule.get("keyword", "") or "").upper() == "ASSAULT" for rule in bodyguard_keywords)
    assert any(str(rule.get("keyword", "") or "").upper() == "ASSAULT" for rule in leader_keywords)

    gsc_army.genestealer_cults_detachments.cleanup_on_phase_end(BattleRoundPhases.SHOOTING_PHASE, gsc_player)

    assert neophytes.models[0].get_temporary_weapon_keyword_bonuses("Autogun") == []
    assert primus.models[0].get_temporary_weapon_keyword_bonuses("Autogun") == []


def test_tireless_fervour_allows_charge_after_advance_or_fall_back_and_rerolls_when_target_engaged_with_friendly_character() -> None:
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

    charger = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    anchor = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy_locked = _make_unit("Enemy Locked", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(charger)
    gsc_army.add_unit(anchor)
    enemy_army.add_unit(enemy_locked)
    enemy_army.add_unit(enemy_other)
    _set_unit_position(charger, 0.0, 0.0)
    _set_unit_position(anchor, 7.0, 0.0)
    _set_unit_position(enemy_locked, 8.0, 0.0)
    _set_unit_position(enemy_other, 25.0, 25.0)
    game.map.units = [charger, anchor, enemy_locked, enemy_other]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    _publish_current_phase_start(game)

    assert bool(manager.use("TIRELESS FERVOUR", unit=charger, phase_name="Charge phase")) is True

    charger.round_state.advanced_this_round = True
    assert bool(charger.can_charge_after_advance()) is True
    charger.round_state.fell_back_this_round = True
    assert bool(charger.can_charge_after_fall_back()) is True
    assert bool(charger.can_reroll_charge_roll(target_unit=enemy_locked, game=game, game_map=game.map)) is True
    assert bool(charger.can_reroll_charge_roll(target_unit=enemy_other, game=game, game_map=game.map)) is False

    gsc_army.genestealer_cults_detachments.cleanup_on_phase_end(BattleRoundPhases.CHARGE_PHASE, gsc_player)
    assert bool(charger.can_reroll_charge_roll(target_unit=enemy_locked, game=game, game_map=game.map)) is False


def test_vengeance_for_the_martyr_queues_and_grants_full_hit_rerolls_for_primus_loss() -> None:
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    acolytes = _make_unit(
        "Acolyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    destroyed_primus = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    surviving_character = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(acolytes)
    gsc_army.add_unit(destroyed_primus)
    gsc_army.add_unit(surviving_character)
    enemy_army.add_unit(enemy)
    game.map.units = [acolytes, destroyed_primus, surviving_character, enemy]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    manager._on_model_destroyed(
        attacker_unit=enemy,
        target_unit=destroyed_primus,
        target_model=destroyed_primus.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
    )
    assert _pending_reaction_by_name(manager, "VENGEANCE FOR THE MARTYR!") is not None

    assert bool(
        manager.use(
            "VENGEANCE FOR THE MARTYR!",
            unit=surviving_character,
            destroyed_model=destroyed_primus.models[0],
            destroyed_unit=destroyed_primus,
            enemy_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
    ) is True

    mods = acolytes.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=acolytes.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
    )
    assert bool(mods.get("reroll_hit_full")) is True


def test_vengeance_for_the_martyr_rerolls_ones_for_non_iconic_character_loss() -> None:
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    destroyed_clamavus = _make_unit(
        "Clamavus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    surviving_character = _make_unit(
        "Primus",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(destroyed_clamavus)
    gsc_army.add_unit(surviving_character)
    enemy_army.add_unit(enemy)
    game.map.units = [neophytes, destroyed_clamavus, surviving_character, enemy]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    manager._on_model_destroyed(
        attacker_unit=enemy,
        target_unit=destroyed_clamavus,
        target_model=destroyed_clamavus.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
    )
    assert _pending_reaction_by_name(manager, "VENGEANCE FOR THE MARTYR!") is not None

    assert bool(
        manager.use(
            "VENGEANCE FOR THE MARTYR!",
            unit=surviving_character,
            destroyed_model=destroyed_clamavus.models[0],
            destroyed_unit=destroyed_clamavus,
            enemy_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
    ) is True

    mods = neophytes.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=neophytes.models[0],
        weapon_profile=_make_ranged_profile(name="Autogun"),
    )
    assert bool(mods.get("reroll_hit_full")) is False
    assert 1 in tuple(mods.get("reroll_hit_values", ()) or ())


def test_the_path_of_anguish_queues_after_enemy_shooting_and_uses_blood_surge_move() -> None:
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(neophytes)
    enemy_army.add_unit(enemy)
    _set_unit_position(neophytes, 0.0, 0.0)
    _set_unit_position(enemy, 12.0, 0.0)
    game.map.units = [neophytes, enemy]
    game.rebuild_entity_registry()

    manager = gsc_player.stratagems
    manager.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    manager._on_unit_shooting_resolved_genestealer_cults_brood_brother_auxilia(
        attacker_unit=enemy,
        hits_by_target={neophytes: 1},
        killing_models_by_target={neophytes: [neophytes.models[0]]},
    )
    assert _pending_reaction_by_name(manager, "THE PATH OF ANGUISH") is not None

    assert bool(
        manager.use(
            "THE PATH OF ANGUISH",
            unit=neophytes,
            enemy_unit=enemy,
            killing_models_by_target={neophytes: [neophytes.models[0]]},
            phase_name="Shooting phase",
            dequeue=True,
            max_distance=4,
        )
    ) is True

    request = _find_request(
        game,
        decision_type=DECISION_MOVE_UNIT,
        reactive_move_kind="xenocreed_path_of_anguish",
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 4
    assert str(context.get("movement_type", "") or "") == "blood_surge"
    assert bool(context.get("reactive_move_allow_engagement_range", False)) is True
    assert str(context.get("reactive_move_attacker_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_the_downtrodden_rise_queues_and_builds_special_reserves_arrival_request() -> None:
    game, gsc_army, _enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 4

    neophytes = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(neophytes)
    neophytes.deployed = False
    neophytes.reserve_status = "reserves"
    game.map.units = []
    game.rebuild_entity_registry()

    cult_ambush = gsc_army.cult_ambush
    cult_ambush._prepare_unit_in_cult_ambush(neophytes, game=game)
    neophytes.can_arrive_from_reserves = lambda _turn: True

    manager = gsc_player.stratagems
    manager.refresh_available()
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    manager._queue_genestealer_cults_xenocreed_reinforcements_step_end_reactions(current_player=enemy_player)
    assert _pending_reaction_by_name(manager, "THE DOWNTRODDEN RISE") is not None

    assert bool(
        manager.use(
            "THE DOWNTRODDEN RISE",
            unit=neophytes,
            phase_name="Movement phase",
            dequeue=True,
        )
    ) is True

    request = _find_request(
        game,
        decision_type=DECISION_MOVE_UNIT,
        ability="the_downtrodden_rise",
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("placement_kind", "") or "") == "reserves_arrival"
    assert bool(context.get("reserves_arrival_ignore_turn_requirement", False)) is True
    assert bool(context.get("reserves_arrival_ignore_battlefield_edge_requirement", False)) is True
    assert float(context.get("reserves_arrival_min_enemy_distance_override", 0.0) or 0.0) == 6.0
