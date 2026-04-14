from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DARK_PACT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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
        model_count: int = 1,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
    ):
        self.id = str(name).lower().replace(" ", "_")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


_ARKIFANE_SPECS = (
    {
        "id": "000010744002",
        "name": "Touch of the Arkifane",
        "cp_cost": 1,
        "turn": "Either player's turn",
        "phase": "Any phase",
        "type": "Cult of the Arkifane - Battle Tactic Stratagem",
        "description": (
            "<b>WHEN:</b> Any phase.<br><br><b>TARGET:</b> One <span class=\"kwb\">HERETIC</span> "
            "<span class=\"kwb\">ASTARTES</span> unit from your army (excluding DAMNED units) that has "
            "not been selected to shoot or fight this phase.<br><br><b>EFFECT:</b> Until the end of the "
            "phase, each time your unit is selected to make a Dark Pact, it can select both abilities."
        ),
    },
    {
        "id": "000010744003",
        "name": "Balefire Boon",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Shooting or Fight phase",
        "type": "Cult of the Arkifane - Battle Tactic Stratagem",
        "description": (
            "<b>WHEN:</b> Your Shooting or Fight phase.<br><br><b>TARGET:</b> One SOUL FORGE unit from "
            "your army that has not been selected to shoot or fight this phase.<br><br><b>EFFECT:</b> "
            "Until the end of the phase, improve the Armour Penetration characteristic of weapons equipped "
            "by models in your unit by 1."
        ),
    },
    {
        "id": "000010744004",
        "name": "Soul-Tally Offering",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Shooting or Fight phase",
        "type": "Cult of the Arkifane - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Shooting or Fight phase.<br><br><b>TARGET:</b> One SOUL FORGE unit from "
            "your army that has not been selected to shoot or fight this phase.<br><br><b>EFFECT:</b> "
            "Until the end of the phase, each time a model in your unit makes an attack that targets a "
            "CHARACTER, MONSTER or VEHICLE unit, you can re-roll the Wound roll."
        ),
    },
    {
        "id": "000010744005",
        "name": "Biomechanoid Regeneration",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Command phase",
        "type": "Cult of the Arkifane - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Command phase.<br><br><b>TARGET:</b> One HERETIC ASTARTES unit from your "
            "army (excluding DAMNED units).<br><br><b>EFFECT:</b> One model in your unit regains up to D3 "
            "lost wounds, or up to 3 lost wounds instead if your unit has the SOUL FORGE keyword."
        ),
    },
    {
        "id": "000010744006",
        "name": "Forge-Fire Surge",
        "cp_cost": 1,
        "turn": "Your turn",
        "phase": "Movement phase",
        "type": "Cult of the Arkifane - Strategic Ploy Stratagem",
        "description": (
            "<b>WHEN:</b> Your Movement phase, just after a HERETIC ASTARTES unit from your army "
            "Advances.<br><br><b>TARGET:</b> That HERETIC ASTARTES unit.<br><br><b>EFFECT:</b> Until the "
            "end of the turn, your unit is eligible to shoot in a turn in which it Advanced. If it has "
            "the SOUL FORGE keyword, it is also eligible to declare a charge in a turn in which it "
            "Advanced."
        ),
    },
    {
        "id": "000010744007",
        "name": "Unholy Fortitude",
        "cp_cost": 1,
        "turn": "Opponent's turn",
        "phase": "Shooting phase",
        "type": "Cult of the Arkifane - Battle Tactic Stratagem",
        "description": (
            "<b>WHEN:</b> Your opponent's Shooting phase, just after an enemy unit has selected its "
            "targets.<br><br><b>TARGET:</b> One SOUL FORGE unit from your army that was selected as the "
            "target of one or more of the attacking unit's attacks.<br><br><b>EFFECT:</b> Until the end of "
            "the phase, add 1 to the Toughness characteristic of models in your unit."
        ),
    },
)


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.possible_abilities = ["Dark Pacts"]
    return unit


def _make_wargear(
    name: str,
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    return Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", "Cult of the Arkifane")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("Arkifane", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    csm_player.command_points = 10
    enemy_player.command_points = 10

    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_arkifane_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_arkifane_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    for spec in _ARKIFANE_SPECS:
        key = _norm_name(spec["name"])
        stratagem = existing.get(key)
        if stratagem is None:
            player.stratagems.available.append(
                Stratagem(
                    id=spec["id"],
                    name=spec["name"],
                    type=spec["type"],
                    description=spec["description"],
                    cp_cost=int(spec["cp_cost"]),
                    turn=spec["turn"],
                    phase=spec["phase"],
                    detachment="Cult of the Arkifane",
                    faction_id="CSM",
                )
            )
            continue
        stratagem.id = spec["id"]
        stratagem.name = spec["name"]
        stratagem.type = spec["type"]
        stratagem.description = spec["description"]
        stratagem.cp_cost = int(spec["cp_cost"])
        stratagem.turn = spec["turn"]
        stratagem.phase = spec["phase"]
        stratagem.detachment = "Cult of the Arkifane"
        stratagem.faction_id = "CSM"


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _find_dark_pact_request(game: Game, *, unit_id: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_DARK_PACT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("unit_id", "") or "") == str(unit_id):
            return request
    return None


def _find_dark_pact_option(request, *, choice: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice", "") or "").strip().upper() == str(choice).strip().upper():
            return option
    return None


def test_arkifane_stratagem_descriptors_registered():
    expected = {
        "000010744002": ("Touch of the Arkifane", "dark_pacts_may_select_both_bonuses"),
        "000010744003": ("Balefire Boon", "phase_weapon_ap_bonus"),
        "000010744004": ("Soul-Tally Offering", "wound_reroll_vs_character_monster_vehicle"),
        "000010744005": ("Biomechanoid Regeneration", "heal_wounded_model_in_unit"),
        "000010744006": (
            "Forge-Fire Surge",
            "shoot_after_advance_and_conditional_charge_after_advance_if_soul_forge",
        ),
        "000010744007": ("Unholy Fortitude", "defensive_toughness_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_touch_of_the_arkifane_adds_both_dark_pact_choice():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(legionaries)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, legionaries, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "TOUCH OF THE ARKIFANE") is not None

    assert csm_player.stratagems.use("TOUCH OF THE ARKIFANE", unit=legionaries, dequeue=True)
    assert int(csm_player.command_points or 0) == 9

    legionaries.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
    request = _find_dark_pact_request(game, unit_id=str(get_entity_id(legionaries) or ""))
    assert request is not None
    option = _find_dark_pact_option(request, choice="BOTH")
    assert option is not None

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        result = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert str(getattr(legionaries, "special_rules", {}).get("dark_pacts_choice", "") or "") == "BOTH"


def test_balefire_boon_improves_ap_until_end_of_phase():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=10,
        toughness=10,
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    forgefiend.models[0].wargear = [_make_wargear("Ectoplasma Cannon", melee=False, ap="0")]
    csm_army.add_unit(forgefiend)
    enemy_army.add_unit(enemy)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, forgefiend, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    profile = forgefiend.models[0].wargear[0].profiles["default"]
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == 0

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "BALEFIRE BOON") is not None

    assert csm_player.stratagems.use("BALEFIRE BOON", unit=forgefiend, dequeue=True)
    assert int(csm_player.command_points or 0) == 9
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == -1

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == 0


def test_soul_tally_offering_rerolls_wounds_only_vs_character_monster_vehicle():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=10,
        toughness=10,
    )
    enemy_character = _make_unit(
        "Enemy Character",
        faction_name="Enemy",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_squad = _make_unit("Enemy Squad", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    forgefiend.models[0].wargear = [_make_wargear("Ectoplasma Cannon", melee=False)]
    csm_army.add_unit(forgefiend)
    enemy_army.add_unit(enemy_character)
    enemy_army.add_unit(enemy_squad)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, forgefiend, 10.0, 10.0)
    _deploy_unit(game, enemy_character, 18.0, 10.0)
    _deploy_unit(game, enemy_squad, 22.0, 10.0)
    game.rebuild_entity_registry()

    profile = forgefiend.models[0].wargear[0].profiles["default"]
    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "SOUL-TALLY OFFERING") is not None
    assert csm_player.stratagems.use("SOUL-TALLY OFFERING", unit=forgefiend, dequeue=True)

    mgr = csm_army.chaos_space_marines_detachments
    applies_character, _source = mgr.cult_of_the_arkifane_soul_tally_offering_reroll_wound_applies(
        forgefiend.models[0],
        target_unit=enemy_character,
        weapon_profile=profile,
        game=game,
    )
    applies_squad, _other_source = mgr.cult_of_the_arkifane_soul_tally_offering_reroll_wound_applies(
        forgefiend.models[0],
        target_unit=enemy_squad,
        weapon_profile=profile,
        game=game,
    )
    assert applies_character is True
    assert applies_squad is False


def test_biomechanoid_regeneration_heals_d3_or_three_for_soul_forge_units():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=4,
    )
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=10,
        toughness=10,
    )
    csm_army.add_unit(legionaries)
    csm_army.add_unit(forgefiend)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, forgefiend, 14.0, 10.0)
    legionaries.models[0].wounds = 2
    forgefiend.models[0].wounds = 7
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "BIOMECHANOID REGENERATION")
    assert pending is not None
    with patch("warhammer40k_ai.rules.stratagems_chaos_space_marines.dice_module.get_roll", return_value=2):
        assert csm_player.stratagems.use("BIOMECHANOID REGENERATION", unit=legionaries, dequeue=True)
    assert int(legionaries.models[0].wounds or 0) == 4

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    game.turn = 2
    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "BIOMECHANOID REGENERATION")
    assert pending is not None
    assert csm_player.stratagems.use("BIOMECHANOID REGENERATION", unit=forgefiend, dequeue=True)
    assert int(forgefiend.models[0].wounds or 0) == 10


def test_forge_fire_surge_queues_after_advance_and_grants_shoot_plus_conditional_charge():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=10,
        toughness=10,
    )
    legionaries.models[0].wargear = [_make_wargear("Boltgun", melee=False)]
    forgefiend.models[0].wargear = [_make_wargear("Ectoplasma Cannon", melee=False)]
    csm_army.add_unit(legionaries)
    csm_army.add_unit(forgefiend)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, forgefiend, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=legionaries, action="advance")
    assert _pending_by_name(csm_player.stratagems, "FORGE-FIRE SURGE") is not None
    assert csm_player.stratagems.use("FORGE-FIRE SURGE", unit=legionaries, action="advance", dequeue=True)
    assert legionaries.can_shoot_after_advance(legionaries.models[0].wargear[0].profiles["default"]) is True
    assert legionaries.can_charge_after_advance() is False

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    game.turn = 2
    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=forgefiend, action="advance")
    assert _pending_by_name(csm_player.stratagems, "FORGE-FIRE SURGE") is not None
    assert csm_player.stratagems.use("FORGE-FIRE SURGE", unit=forgefiend, action="advance", dequeue=True)
    assert forgefiend.can_shoot_after_advance(forgefiend.models[0].wargear[0].profiles["default"]) is True
    assert forgefiend.can_charge_after_advance() is True


def test_unholy_fortitude_queues_on_enemy_target_selection_and_grants_toughness_bonus():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=10,
        toughness=10,
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(forgefiend)
    enemy_army.add_unit(enemy)
    csm_army.validate_detachment_rules()
    _deploy_unit(game, forgefiend, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    base_toughness = int(
        forgefiend.get_effective_model_characteristic(
            forgefiend.models[0],
            "toughness",
            game_map=game.map,
        )
        or 0
    )
    assert base_toughness == 10

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[forgefiend])
    assert _pending_by_name(csm_player.stratagems, "UNHOLY FORTITUDE") is not None

    assert csm_player.stratagems.use("UNHOLY FORTITUDE", unit=forgefiend, attacking_unit=enemy, dequeue=True)
    buffed_toughness = int(
        forgefiend.get_effective_model_characteristic(
            forgefiend.models[0],
            "toughness",
            game_map=game.map,
        )
        or 0
    )
    assert buffed_toughness == 11

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    game.turn = 2
    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    reset_toughness = int(
        forgefiend.get_effective_model_characteristic(
            forgefiend.models[0],
            "toughness",
            game_map=game.map,
        )
        or 0
    )
    assert reset_toughness == 10


def test_arkifane_stratagem_support_matrix_classifies_supported():
    import scripts.generate_ability_support_matrix as gsm

    for spec in _ARKIFANE_SPECS:
        status, _icon, notes = gsm._stratagem_support(
            spec["name"],
            spec["description"],
            detachment_name="Cult of the Arkifane",
            stratagem_id=spec["id"],
        )
        assert status == "Supported"
        assert str(notes or "").strip()
