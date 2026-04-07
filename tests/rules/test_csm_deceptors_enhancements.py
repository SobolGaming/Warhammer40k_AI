from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        attached_to=None,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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
    datasheet_id: str | None = None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="CSM",
        detachment="Deceptors",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Deceptors")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.turn = 1
    return game, csm_army, enemy_army, csm_player, enemy_player


def _find_choose_quarry_request(game: Game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return request
    return None


def _find_option_id(request, *, payload_key: str, expected_value: str) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(payload_key, "") or "") == str(expected_value):
            return str(option.option_id)
    return ""


def test_deceptors_enhancement_descriptors_registered():
    expected = {
        "000008964002": ("Cursed Fang", "bearer_melee_ap_bonus_and_precision"),
        "000008964003": ("Falsehood", "optional_reserves_setup_and_reinforcements_model_swap_attach"),
        "000008964004": ("Shroud of Obfuscation", "bearer_gains_stealth_and_lone_operative"),
        "000008964005": ("Soul Link", "select_model_gain_psyker_and_replace_bearer_datasheet_abilities"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_cursed_fang_and_shroud_apply_bearer_only_combat_flags():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Deceptors")
    army.faction_id = "CSM"
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    army.add_unit(source)

    _apply_enhancement(
        source,
        enhancement_id="000008964002",
        name="Cursed Fang",
        description=(
            "HERETIC ASTARTES INFANTRY model only. Improve the Armour Penetration characteristic of the bearer’s "
            "melee weapons by 1, and the bearer’s melee weapons have the [PRECISION] ability."
        ),
    )
    _apply_enhancement(
        source,
        enhancement_id="000008964004",
        name="Shroud of Obfuscation",
        description="HERETIC ASTARTES INFANTRY model only. The bearer has the Stealth and Lone Operative abilities.",
    )

    bearer_id = str(source.special_rules.get("enhancement_bearer_model_id", "") or "")
    assert bearer_id
    bearer_model = next(
        model
        for model in list(source.models or [])
        if str(getattr(model, "id", getattr(model, "_id", "")) or "") == bearer_id
    )
    non_bearer = next(model for model in list(source.models or []) if model is not bearer_model)

    assert int(source.special_rules.get("enhancement_bearer_melee_ap_bonus", 0) or 0) >= 1
    assert bool(source.special_rules.get("enhancement_bearer_melee_precision", False))
    assert str(getattr(non_bearer, "name", "") or "") != ""
    assert bool(source.has_stealth())
    assert bool(source.has_lone_operative())


def test_falsehood_declare_and_reinforcements_swap_attach_flow():
    game, csm_army, enemy_army, csm_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    legionaries = _make_unit(
        "Legionaries",
        datasheet_id="deceptors_legionaries_ds",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
    )
    chaos_lord = _make_unit(
        "Chaos Lord",
        datasheet_id="deceptors_chaos_lord_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
        attached_to=["deceptors_legionaries_ds"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
    )
    csm_army.add_unit(legionaries)
    csm_army.add_unit(chaos_lord)
    enemy_army.add_unit(enemy)

    _apply_enhancement(
        chaos_lord,
        enhancement_id="000008964003",
        name="Falsehood",
        description=(
            "CHAOS LORD model only. In the Declare Battle Formations step, you can set the bearer up in Reserves "
            "instead of setting it up on the battlefield. If you do, in the Reinforcements step of one of your "
            "Movement phases, you can select one model in a friendly Legionaries or Chosen unit that has two or "
            "more models remaining and is on the battlefield (excluding Attached units). The selected model is "
            "destroyed and the bearer is set up as close as possible to where that model was destroyed. The bearer "
            "now attaches to that unit as its Leader."
        ),
    )

    _set_unit_location(legionaries, x=8.0, y=0.0)
    _set_unit_location(enemy, x=40.0, y=0.0)
    game.map.units = [legionaries, enemy]
    game.rebuild_entity_registry()
    game._find_closest_valid_reposition_position = lambda *_args, **_kwargs: (11.0, 0.0, 0.0, 0.0)

    mgr = csm_army.chaos_space_marines_detachments
    mgr.queue_deceptors_falsehood_declare_request(game=game, player=csm_player)
    declare_request = _find_choose_quarry_request(game, ability="deceptors_falsehood_declare_reserves")
    assert declare_request is not None
    reserves_choice = _find_option_id(declare_request, payload_key="choice_key", expected_value="RESERVES")
    assert reserves_choice
    declare_outcome = resolve_decision_command(game, declare_request, reserves_choice, player_id=csm_player.id)
    assert bool(getattr(declare_outcome, "ok", False))
    assert str(getattr(chaos_lord, "reserve_status", "") or "") == "reserves"

    target_model = legionaries.models[0]
    target_model_id = str(get_entity_id(target_model) or "")
    assert target_model_id

    game.handle_reserves_arrival_phase()
    reinforcement_request = _find_choose_quarry_request(game, ability="deceptors_falsehood_reinforcements")
    assert reinforcement_request is not None
    selected_option = _find_option_id(
        reinforcement_request,
        payload_key="target_model_id",
        expected_value=target_model_id,
    )
    assert selected_option
    reinforcement_outcome = resolve_decision_command(game, reinforcement_request, selected_option, player_id=csm_player.id)
    assert bool(getattr(reinforcement_outcome, "ok", False))
    assert len(list(legionaries.models or [])) == 2
    assert chaos_lord.attached_to is legionaries
    assert chaos_lord in list(getattr(legionaries, "attached_leaders", []) or [])
    assert str(getattr(chaos_lord, "reserve_status", "") or "") == "deployed"
    assert bool(chaos_lord.special_rules.get("enhancement_falsehood_reinforcements_used", False))


def test_soul_link_applies_keyword_and_replaces_abilities_until_next_command_phase():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    source = _make_unit(
        "Chaos Lord",
        datasheet_id="deceptors_soul_link_source_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    source.possible_abilities = [Ability("Source Ability", "CSM", "", "Datasheet", "")]
    target = _make_unit(
        "Master of Executions",
        datasheet_id="deceptors_soul_link_target_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    target.possible_abilities = [
        Ability("Borrowed Ability", "CSM", "This model has the Stealth ability.", "Datasheet", "")
    ]
    csm_army.add_unit(source)
    csm_army.add_unit(target)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(target, x=2.0, y=0.0)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008964005",
        name="Soul Link",
        description=(
            "HERETIC ASTARTES INFANTRY model only. At the start of your Command phase, you can select one other "
            "HERETIC ASTARTES INFANTRY CHARACTER model from your army (excluding EPIC HEROES). Until the start of "
            "your next Command phase, the bearer gains the PSYKER keyword, and replace the bearer’s datasheet "
            "abilities with the datasheet abilities of the CHARACTER you selected."
        ),
    )

    source_model = source.models[0]
    target_model = target.models[0]
    target_model_id = str(get_entity_id(target_model) or "")
    assert target_model_id

    game.start_command_phase()
    request = _find_choose_quarry_request(game, ability="deceptors_soul_link_target")
    assert request is not None
    option_id = _find_option_id(request, payload_key="target_model_id", expected_value=target_model_id)
    assert option_id
    outcome = resolve_decision_command(game, request, option_id, player_id=csm_player.id)
    assert bool(getattr(outcome, "ok", False))
    assert bool(source.special_rules.get("enhancement_soul_link_active", False))
    assert bool(source_model.has_any_keyword("PSYKER"))
    assert bool(source.has_stealth())
    assert [str(getattr(ability, "name", ability)) for ability in list(source._iter_active_possible_abilities())] == [
        "Borrowed Ability"
    ]

    game.turn = 2
    game.start_command_phase()
    second_request = _find_choose_quarry_request(game, ability="deceptors_soul_link_target")
    assert second_request is not None
    skip_id = _find_option_id(second_request, payload_key="action", expected_value="skip")
    assert skip_id
    skip_outcome = resolve_decision_command(game, second_request, skip_id, player_id=csm_player.id)
    assert bool(getattr(skip_outcome, "ok", False))
    assert not bool(source.special_rules.get("enhancement_soul_link_active", False))
    assert not bool(source_model.has_any_keyword("PSYKER"))
    assert not bool(source.has_stealth())
    assert [str(getattr(ability, "name", ability)) for ability in list(source._iter_active_possible_abilities())] == [
        "Source Ability"
    ]


def test_soul_link_allows_reserve_source_and_offboard_target_but_excludes_embarked_and_keeps_attachment_rules():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    source = _make_unit(
        "Chaos Lord",
        datasheet_id="deceptors_soul_link_reserve_source_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
        attached_to=["legionaries_ds"],
    )
    source.deployed = False
    source.reserve_status = "strategic_reserves"
    source.can_be_attached_to = ["Legionaries"]
    source.possible_abilities = [Ability("Source Ability", "CSM", "", "Datasheet", "")]

    target_reserve = _make_unit(
        "Master of Executions",
        datasheet_id="deceptors_soul_link_reserve_target_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    target_reserve.deployed = False
    target_reserve.reserve_status = "reserves"
    target_reserve.possible_abilities = [
        Ability("Deep Strike", "CSM", "", "Core", ""),
        Ability("Dark Pacts", "CSM", "", "Faction", ""),
        Ability("Borrowed Ability", "CSM", "", "Datasheet", ""),
    ]

    embarked_target = _make_unit(
        "Embarked Sorcerer",
        datasheet_id="deceptors_soul_link_embarked_target_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    transport = _make_unit(
        "Chaos Rhino",
        datasheet_id="deceptors_transport_ds",
        keywords=["TRANSPORT", "VEHICLE", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    embarked_target.embarked_in = transport

    csm_army.add_unit(source)
    csm_army.add_unit(target_reserve)
    csm_army.add_unit(embarked_target)
    csm_army.add_unit(transport)
    game.map.units = [transport]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008964005",
        name="Soul Link",
        description=(
            "HERETIC ASTARTES INFANTRY model only. At the start of your Command phase, you can select one other "
            "HERETIC ASTARTES INFANTRY CHARACTER model from your army (excluding EPIC HEROES). Until the start of "
            "your next Command phase, the bearer gains the PSYKER keyword, and replace the bearer’s datasheet "
            "abilities with the datasheet abilities of the CHARACTER you selected."
        ),
    )

    reserve_target_model_id = str(get_entity_id(target_reserve.models[0]) or "")
    embarked_target_model_id = str(get_entity_id(embarked_target.models[0]) or "")

    game.start_command_phase()
    request = _find_choose_quarry_request(game, ability="deceptors_soul_link_target")
    assert request is not None
    assert _find_option_id(request, payload_key="target_model_id", expected_value=reserve_target_model_id)
    assert not _find_option_id(request, payload_key="target_model_id", expected_value=embarked_target_model_id)

    option_id = _find_option_id(request, payload_key="target_model_id", expected_value=reserve_target_model_id)
    outcome = resolve_decision_command(game, request, option_id, player_id=csm_player.id)
    assert bool(getattr(outcome, "ok", False))

    active_abilities = list(source._iter_active_possible_abilities())
    assert [str(getattr(ability, "name", ability)) for ability in active_abilities] == [
        "Deep Strike",
        "Dark Pacts",
        "Borrowed Ability",
    ]
    assert [str(getattr(ability, "type", "")) for ability in active_abilities] == ["Core", "Faction", "Datasheet"]
    assert list(source.can_be_attached_to) == ["Legionaries"]


def test_soul_link_borrowed_once_per_battle_usage_is_tracked_per_model():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    source = _make_unit(
        "Chaos Lord",
        datasheet_id="deceptors_soul_link_once_source_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES", "CHAOS LORD"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    target = _make_unit(
        "Master of Executions",
        datasheet_id="deceptors_soul_link_once_target_ds",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=1,
    )
    target.possible_abilities = [Ability("Borrowed Once", "CSM", "Once per battle.", "Datasheet", "")]
    csm_army.add_unit(source)
    csm_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008964005",
        name="Soul Link",
        description=(
            "HERETIC ASTARTES INFANTRY model only. At the start of your Command phase, you can select one other "
            "HERETIC ASTARTES INFANTRY CHARACTER model from your army (excluding EPIC HEROES). Until the start of "
            "your next Command phase, the bearer gains the PSYKER keyword, and replace the bearer’s datasheet "
            "abilities with the datasheet abilities of the CHARACTER you selected."
        ),
    )

    target_model = target.models[0]
    source_model = source.models[0]
    assert target_model.mark_used_once_per_battle("borrowed_once", ability_name="Borrowed Once", source="datasheet")

    game.start_command_phase()
    request = _find_choose_quarry_request(game, ability="deceptors_soul_link_target")
    assert request is not None
    option_id = _find_option_id(request, payload_key="target_model_id", expected_value=str(get_entity_id(target_model) or ""))
    assert option_id
    outcome = resolve_decision_command(game, request, option_id, player_id=csm_player.id)
    assert bool(getattr(outcome, "ok", False))
    assert not source_model.has_used_once_per_battle("borrowed_once")
    assert source_model.mark_used_once_per_battle("borrowed_once", ability_name="Borrowed Once", source="datasheet")
