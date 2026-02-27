from __future__ import annotations

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        movement: int = 6,
        toughness: int = 4,
    ):
        self.id = datasheet_id or f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    movement: int = 6,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            movement=movement,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sororitas_units: list[Unit], enemy_units: list[Unit]):
    sororitas_army = Army("Adepta Sororitas", "Penitent Host")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(sororitas_units or []):
        sororitas_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    sororitas_player = Player("Sororitas Player", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    return game, sororitas_player, sororitas_army


def _find_quarry_request(game: Game, *, ability: str, battle_round: int | None = None, source_unit_id: str = ""):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability):
            continue
        if source_unit_id and str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
            continue
        if battle_round is None:
            return req
        try:
            ctx_round = int(ctx.get("battle_round", 0) or 0)
        except (TypeError, ValueError):
            ctx_round = 0
        if ctx_round == int(battle_round):
            return req
    return None


def _select_choice(game: Game, player: Player, request, *, choice_key: str):
    target_key = str(choice_key or "").strip().lower()
    option_id = ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        key = str(payload.get("choice_key", "") or "").strip().lower()
        if key != target_key:
            continue
        option_id = str(getattr(option, "option_id", "") or "")
        break
    assert option_id
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    return dispatch_decision(game, request, result)


def _apply_penitent_enhancement(unit: Unit, *, enh_id: str, name: str, description: str) -> None:
    Enhancement(
        id=enh_id,
        name=name,
        faction_id="AS",
        detachment="Penitent Host",
        points=20,
        description=description,
    ).apply_to_unit(unit)


def test_penitent_host_enhancement_descriptors_registered():
    expected = {
        "000009029002": "Psalm of Righteous Judgement",
        "000009029003": "Verse of Holy Piety",
        "000009029004": "Refrain of Enduring Faith",
        "000009029005": "Catechism of Divine Penitence",
    }
    for enh_id, name in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enh_id, name=name)
        assert desc is not None
        assert str(desc.name or "") == name


def test_psalm_of_righteous_judgement_converts_miracle_die_on_penitent_kill():
    penitent = _create_unit(
        "Penitent Engines",
        keywords=["PENITENT", "ADEPTA SORORITAS", "VEHICLE"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, _player, army = _build_game(sororitas_units=[penitent], enemy_units=[enemy])

    _apply_penitent_enhancement(
        penitent,
        enh_id="000009029002",
        name="Psalm of Righteous Judgement",
        description=(
            "While the bearer is on the battlefield, each time an enemy unit is destroyed by a penitent unit from your "
            "army, you can discard 1 Miracle dice then gain 1 Miracle dice showing a value of 6."
        ),
    )

    aof = army.acts_of_faith
    aof.miracle_dice = [2]
    aof.on_unit_destroyed(enemy, game=game, destroyed_by_unit=penitent)
    assert list(aof.miracle_dice) == [6]

    # With only sixes, the optional discard path is skipped by deterministic fallback.
    aof.miracle_dice = [6]
    aof.on_unit_destroyed(enemy, game=game, destroyed_by_unit=penitent)
    assert list(aof.miracle_dice) == [6]


def test_verse_of_holy_piety_applies_additional_vow_for_bearer_unit_once_per_battle():
    penitent = _create_unit(
        "Penitent Engines",
        keywords=["PENITENT", "ADEPTA SORORITAS", "VEHICLE"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=8,
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness=5)
    game, player, army = _build_game(sororitas_units=[penitent], enemy_units=[enemy])

    _apply_penitent_enhancement(
        penitent,
        enh_id="000009029003",
        name="Verse of Holy Piety",
        description=(
            "Once per battle, at the start of the battle round, select one Vow of Atonement. "
            "Until the start of the next battle round, that Vow of Atonement is active for the bearer's unit "
            "in addition to any that is active for your army."
        ),
    )

    mgr = getattr(army, "adepta_sororitas_detachments", None)
    assert mgr is not None

    baseline_move = int(penitent.models[0].movement)

    game.turn = 1
    army.on_battle_round_start(1)

    desperate_req = _find_quarry_request(
        game,
        ability="desperate_for_redemption",
        battle_round=1,
    )
    assert desperate_req is not None
    assert bool(_select_choice(game, player, desperate_req, choice_key="path_of_the_penitent").ok)

    verse_req = _find_quarry_request(
        game,
        ability="verse_of_holy_piety_vow",
        battle_round=1,
        source_unit_id=str(get_entity_id(penitent)),
    )
    assert verse_req is not None
    assert bool(_select_choice(game, player, verse_req, choice_key="death_before_disgrace").ok)

    assert mgr.desperate_for_redemption_active_vow_key(battle_round=1) == "path_of_the_penitent"
    assert mgr.verse_of_holy_piety_active_vow_key(penitent, battle_round=1) == "death_before_disgrace"
    assert int(penitent.models[0].movement) == baseline_move + 3

    fight_on_death = penitent.get_melee_fight_on_death_after_attacks_rule(model=penitent.models[0])
    assert isinstance(fight_on_death, dict)
    assert int(fight_on_death.get("threshold", 0) or 0) == 2

    game.turn = 2
    army.on_battle_round_start(2)
    assert mgr.verse_of_holy_piety_active_vow_key(penitent, battle_round=2) == ""
    verse_req_round_2 = _find_quarry_request(
        game,
        ability="verse_of_holy_piety_vow",
        battle_round=2,
        source_unit_id=str(get_entity_id(penitent)),
    )
    assert verse_req_round_2 is None


def test_refrain_of_enduring_faith_grants_invulnerable_save_only_while_leading():
    bodyguard = _create_unit(
        "Battle Sisters Squad",
        datasheet_id="battle-sisters-ds",
        keywords=["ADEPTA SORORITAS", "INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    leader = _create_unit(
        "Canoness",
        datasheet_id="canoness-ds",
        keywords=["ADEPTA SORORITAS", "INFANTRY", "CHARACTER", "CANONESS"],
        faction_keywords=["ADEPTA SORORITAS"],
        attached_to=["battle-sisters-ds"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _game, _player, _army = _build_game(sororitas_units=[leader, bodyguard], enemy_units=[enemy])

    _apply_penitent_enhancement(
        leader,
        enh_id="000009029004",
        name="Refrain of Enduring Faith",
        description="While the bearer is leading a unit, models in that unit have a 5+ invulnerable save.",
    )

    inv_before, _src_before = leader.get_model_invulnerable_save_override(leader.models[0])
    assert int(inv_before or 0) != 5

    leader.attach_to_unit(bodyguard)
    inv_led, src_led = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
    assert int(inv_led or 0) == 5
    assert "Refrain" in str(src_led or "")

    leader.models[0].wounds = 0
    inv_after, _src_after = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
    assert int(inv_after or 0) != 5


def test_catechism_of_divine_penitence_grants_penitent_keyword_and_repentia_attachment():
    leader = _create_unit(
        "Canoness",
        datasheet_id="canoness-ds",
        keywords=["ADEPTA SORORITAS", "INFANTRY", "CHARACTER", "CANONESS"],
        faction_keywords=["ADEPTA SORORITAS"],
        attached_to=["battle-sisters-ds"],
    )
    repentia = _create_unit(
        "Repentia Squad",
        datasheet_id="repentia-ds",
        keywords=["ADEPTA SORORITAS", "INFANTRY", "REPENTIA"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _game, _player, _army = _build_game(sororitas_units=[leader, repentia], enemy_units=[enemy])

    assert bool(leader.can_attach_to(repentia)) is False

    _apply_penitent_enhancement(
        leader,
        enh_id="000009029005",
        name="Catechism of Divine Penitence",
        description=(
            "The bearer gains the PENITENT keyword and can be attached to a REPENTIA SQUAD unit during "
            "the Declare Battle Formations step."
        ),
    )

    assert bool(leader.models[0].has_any_keyword("PENITENT"))
    assert bool(leader.can_attach_to(repentia))
