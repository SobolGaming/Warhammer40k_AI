from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, battle_size: BattlefieldSize):
    game = Game(Battlefield(battle_size))
    csm_army = Army.with_detachment("Chaos Space Marines", "Deceptors")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    return game, csm_player, enemy_player, csm_army, enemy_army


def _find_masters_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "deceptors_masters_of_misdirection_selection":
            continue
        return req
    return None


def _confirm_option(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "confirm":
            return option
    raise AssertionError("Confirm option not found.")


def test_masters_of_misdirection_queues_in_declare_battle_formations_step():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game(battle_size=BattlefieldSize.STRIKE_FORCE)
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    cultists = _make_unit(
        "Cultist Mob",
        keywords=["DAMNED", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    other = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(legionaries)
    csm_army.add_unit(cultists)
    csm_army.add_unit(other)
    enemy_army.add_unit(enemy)
    game.map.units = [legionaries, cultists, other, enemy]
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()

    request = _find_masters_request(game)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("ability_name", "") or "") == "Masters of Misdirection"
    assert int(ctx.get("max_units_per_type", 0) or 0) == 3
    assert int(ctx.get("max_units", 0) or 0) == 6
    allowed_ids = {str(v) for v in list(ctx.get("allowed_unit_ids") or []) if str(v or "")}
    assert allowed_ids == {
        str(get_entity_id(legionaries) or ""),
        str(get_entity_id(cultists) or ""),
    }
    assert str(request.player_id or "") == str(csm_player.id or "")


def test_masters_of_misdirection_selection_validation_and_apply():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game(battle_size=BattlefieldSize.STRIKE_FORCE)
    legionaries = [
        _make_unit(
            f"Legionaries {idx}",
            keywords=["HERETIC ASTARTES", "INFANTRY", "BATTLELINE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        for idx in range(1, 5)
    ]
    cultists = [
        _make_unit(
            f"Cultist Mob {idx}",
            keywords=["DAMNED", "INFANTRY", "BATTLELINE"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        for idx in range(1, 4)
    ]
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in legionaries:
        unit.name = "Legionaries"
        csm_army.add_unit(unit)
    for unit in cultists:
        unit.name = "Cultist Mob"
        csm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = list(csm_army.units) + [enemy]
    game.rebuild_entity_registry()

    mgr = csm_army.chaos_space_marines_detachments
    mgr.queue_masters_of_misdirection_selection_request(game=game, player=csm_player)
    request = _find_masters_request(game)
    assert request is not None
    confirm = _confirm_option(request)

    invalid = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={
            "unit_ids": [
                str(get_entity_id(legionaries[0]) or ""),
                str(get_entity_id(legionaries[1]) or ""),
                str(get_entity_id(legionaries[2]) or ""),
                str(get_entity_id(legionaries[3]) or ""),
                str(get_entity_id(cultists[0]) or ""),
                str(get_entity_id(cultists[1]) or ""),
            ]
        },
        player_id=csm_player.id,
    )
    assert not bool(getattr(invalid, "ok", False))
    invalid_errors = [str(err or "") for err in list(getattr(invalid, "errors", ()) or ())]
    assert any("at most 3 legionaries" in err.lower() for err in invalid_errors)

    valid = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={
            "unit_ids": [
                str(get_entity_id(legionaries[0]) or ""),
                str(get_entity_id(legionaries[1]) or ""),
                str(get_entity_id(legionaries[2]) or ""),
                str(get_entity_id(cultists[0]) or ""),
                str(get_entity_id(cultists[1]) or ""),
                str(get_entity_id(cultists[2]) or ""),
            ]
        },
        player_id=csm_player.id,
    )
    assert bool(getattr(valid, "ok", False))
    assert bool(legionaries[0].special_rules.get("masters_of_misdirection_infiltrators"))
    assert bool(legionaries[2].special_rules.get("masters_of_misdirection_infiltrators"))
    assert not bool(legionaries[3].special_rules.get("masters_of_misdirection_infiltrators"))
    assert bool(cultists[0].special_rules.get("masters_of_misdirection_infiltrators"))
    assert bool(cultists[2].special_rules.get("masters_of_misdirection_infiltrators"))


def test_masters_of_misdirection_grants_infiltrators_to_attached_non_epic_character_only():
    game, _csm_player, _enemy_player, csm_army, _enemy_army = _build_game(battle_size=BattlefieldSize.STRIKE_FORCE)
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    cultists = _make_unit(
        "Cultist Mob",
        keywords=["DAMNED", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    unattached = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    leader = _make_unit(
        "Chaos Lord",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        attached_to=[legionaries.get_datasheet_id()],
    )
    epic_hero = _make_unit(
        "Abaddon the Despoiler",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER", "EPIC HERO"],
        faction_keywords=["HERETIC ASTARTES"],
        attached_to=[cultists.get_datasheet_id()],
    )
    csm_army.add_unit(legionaries)
    csm_army.add_unit(cultists)
    csm_army.add_unit(unattached)
    csm_army.add_unit(leader)
    csm_army.add_unit(epic_hero)
    game.map.units = list(csm_army.units)
    game.rebuild_entity_registry()

    leader.attach_to_unit(legionaries)
    epic_hero.attach_to_unit(cultists)

    mgr = csm_army.chaos_space_marines_detachments
    applied = mgr.apply_masters_of_misdirection_selection(
        [
            str(get_entity_id(legionaries) or ""),
            str(get_entity_id(cultists) or ""),
        ],
        game=game,
    )
    assert set(applied) == {
        str(get_entity_id(legionaries) or ""),
        str(get_entity_id(cultists) or ""),
    }
    assert legionaries.has_infiltrate() is True
    assert cultists.has_infiltrate() is True
    assert unattached.has_infiltrate() is False
    assert leader.has_infiltrate() is True
    assert epic_hero.has_infiltrate() is False


def test_masters_of_misdirection_max_units_per_type_depends_on_battle_size():
    incursion_game, _p1, _p2, incursion_army, _enemy = _build_game(battle_size=BattlefieldSize.INCURSION)
    strike_game, _p3, _p4, strike_army, _enemy2 = _build_game(battle_size=BattlefieldSize.STRIKE_FORCE)
    onslaught_game, _p5, _p6, onslaught_army, _enemy3 = _build_game(battle_size=BattlefieldSize.ONSLAUGHT)
    assert incursion_army.chaos_space_marines_detachments.masters_of_misdirection_max_units_per_type(game=incursion_game) == 2
    assert strike_army.chaos_space_marines_detachments.masters_of_misdirection_max_units_per_type(game=strike_game) == 3
    assert onslaught_army.chaos_space_marines_detachments.masters_of_misdirection_max_units_per_type(game=onslaught_game) == 4
