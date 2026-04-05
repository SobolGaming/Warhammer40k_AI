from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_requests import build_risen_rubricae_requests
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_reroll_sources
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        abilities=None,
        attached_to=None,
        attached_to_names=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["THOUSAND SONS"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = list(attached_to_names or [])


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    abilities=None,
    attached_to=None,
    attached_to_names=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            abilities=abilities,
            attached_to=attached_to,
            attached_to_names=attached_to_names,
        )
    )


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ts_army = Army("Thousand Sons", "Rubricae Phalanx")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "SM"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=ts_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, ts_army, enemy_army, p1, p2


def _mark_deployed(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _make_ranged_profile(*, bs_ws: str = "4+") -> WargearProfile:
    parent = SimpleNamespace(name="Inferno Boltgun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged",
        {
            "range": "24",
            "A": "1",
            "BS_WS": str(bs_ws),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(*, bs_ws: str = "3+", strength: str = "6") -> WargearProfile:
    parent = SimpleNamespace(name="Force Stave", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": str(bs_ws),
            "S": str(strength),
            "AP": "1",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def _apply_enhancement(unit: Unit, enh_id: str, name: str) -> None:
    Enhancement(
        id=enh_id,
        name=name,
        faction_id="TS",
        detachment="Rubricae Phalanx",
        points=25,
        description="",
    ).apply_to_unit(unit)


def test_risen_rubricae_request_and_faq_attached_character_gains_infiltrators():
    game, army, _enemy_army, p1, _p2 = _build_game()
    source = _make_unit(
        "Exalted Sorcerer",
        "src",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER"],
    )
    rubricae_a = _make_unit("Rubric Marines A", "rb1", keywords=["THOUSAND SONS", "RUBRICAE", "BATTLELINE"])
    rubricae_b = _make_unit("Rubric Marines B", "rb2", keywords=["THOUSAND SONS", "RUBRICAE", "BATTLELINE"])
    other_rubricae = _make_unit("Scarab Occult Terminators", "rb3", keywords=["THOUSAND SONS", "RUBRICAE"])
    army.add_unit(source)
    army.add_unit(rubricae_a)
    army.add_unit(rubricae_b)
    army.add_unit(other_rubricae)
    _mark_deployed(source, rubricae_a, rubricae_b, other_rubricae)
    game.map.units = [source, rubricae_a, rubricae_b, other_rubricae]
    game.rebuild_entity_registry()

    _apply_enhancement(source, "000010205002", "Risen Rubricae")
    requests = build_risen_rubricae_requests(game, army.units, queue_requests=False)
    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "")) == "risen_rubricae"

    two_battleline = None
    one_other = None
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        ids = list(payload.get("selected_unit_ids", []) or [])
        if len(ids) == 2:
            two_battleline = opt
        if len(ids) == 1:
            one_other = opt
    assert two_battleline is not None
    assert one_other is not None

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=two_battleline.option_id,
    )
    _apply_choose_quarry(game, request, result)

    assert rubricae_a.has_infiltrate() is True
    assert rubricae_b.has_infiltrate() is True
    assert other_rubricae.has_infiltrate() is False

    attached_character = _make_unit(
        "Infernal Master",
        "ldr1",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER"],
        attached_to=[rubricae_a.get_datasheet_id()],
    )
    army.add_unit(attached_character)
    _mark_deployed(attached_character)
    attached_character.attach_to_unit(rubricae_a)

    # Rubricae Phalanx FAQ: attached CHARACTER also gains Infiltrators.
    assert attached_character.has_infiltrate() is True


def test_arcane_thralls_aura_grants_battleshock_reroll_to_rubricae_only():
    game, army, enemy_army, _p1, _p2 = _build_game()
    bearer = _make_unit("Sorcerer", "src", keywords=["THOUSAND SONS", "CHARACTER", "PSYKER"])
    rubricae = _make_unit("Rubric Marines", "rb1", keywords=["THOUSAND SONS", "RUBRICAE", "BATTLELINE"])
    non_rubricae = _make_unit("Tzaangors", "tz1", keywords=["THOUSAND SONS", "TZAANGOR"])
    enemy = _make_unit("Enemy Unit", "en1", keywords=["ADEPTUS ASTARTES"])
    army.add_unit(bearer)
    army.add_unit(rubricae)
    army.add_unit(non_rubricae)
    enemy_army.add_unit(enemy)
    _mark_deployed(bearer, rubricae, non_rubricae, enemy)
    game.map.units = [bearer, rubricae, non_rubricae, enemy]
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    rubricae.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    non_rubricae.models[0].set_location(6.0, 2.0, 0.0, 0.0)
    enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.rebuild_entity_registry()

    _apply_enhancement(bearer, "000010205003", "Arcane Thralls (Aura)")

    rubricae_sources = get_aura_battleshock_test_reroll_sources(rubricae, game_map=game.map)
    non_rubricae_sources = get_aura_battleshock_test_reroll_sources(non_rubricae, game_map=game.map)
    assert any("Arcane Thralls" in src for src in rubricae_sources)
    assert not any("Arcane Thralls" in src for src in non_rubricae_sources)


def test_lord_of_the_rubricae_grants_hit_bonus_only_for_rubricae_models():
    game, army, enemy_army, _p1, _p2 = _build_game()
    bodyguard = _make_unit("Rubric Marines", "rb1", keywords=["THOUSAND SONS", "RUBRICAE", "BATTLELINE"])
    leader = _make_unit(
        "Exalted Sorcerer",
        "ldr1",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    enemy = _make_unit("Enemy Unit", "en1", keywords=["ADEPTUS ASTARTES"])
    army.add_unit(bodyguard)
    army.add_unit(leader)
    enemy_army.add_unit(enemy)
    _mark_deployed(bodyguard, leader, enemy)
    leader.attach_to_unit(bodyguard)
    game.map.units = [bodyguard, leader, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, "000010205004", "Lord of the Rubricae")
    profile = _make_ranged_profile(bs_ws="4+")

    attack_instance = {"target_unit": enemy}
    hit_from_rubricae = profile._hit_target_with_tracking(
        enemy,
        bodyguard.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_from_rubricae["hit"] is True
    assert any("Lord of the Rubricae" in m for m in (hit_from_rubricae.get("modifiers") or []))

    attack_instance_leader = {"target_unit": enemy}
    hit_from_leader = profile._hit_target_with_tracking(
        enemy,
        leader.models[0],
        attack_instance_leader,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_from_leader["hit"] is False


def test_the_stave_abominus_grants_bearer_melee_sustained_d3_and_devastating():
    game, army, enemy_army, _p1, _p2 = _build_game()
    bearer_unit = _make_unit(
        "Infernal Master",
        "src",
        keywords=["THOUSAND SONS", "CHARACTER", "PSYKER", "INFANTRY"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", "en1", keywords=["ADEPTUS ASTARTES"])
    army.add_unit(bearer_unit)
    enemy_army.add_unit(enemy)
    _mark_deployed(bearer_unit, enemy)
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, "000010205005", "The Stave Abominus")
    profile = _make_melee_profile()
    bearer_model = bearer_unit.models[0]
    other_model = bearer_unit.models[1]

    bearer_attack = {"target_unit": enemy}
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        bearer_hit = profile._hit_target_with_tracking(
            enemy,
            bearer_model,
            bearer_attack,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
    assert bearer_hit["hit"] is True
    assert int(bearer_attack.get("sustained_hit", 0) or 0) == 2

    bearer_wound = profile._wound_target_with_tracking(
        enemy,
        bearer_model,
        bearer_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bearer_wound["wound"] is True
    assert bearer_attack.get("mortal_wound") is True

    other_attack = {"target_unit": enemy}
    other_hit = profile._hit_target_with_tracking(
        enemy,
        other_model,
        other_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert other_hit["hit"] is True
    assert int(other_attack.get("sustained_hit", 0) or 0) == 0
