from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
    ) -> None:
        count = max(1, int(model_count or 1))
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10" if "VEHICLE" in set(self.keywords) else "6",
                "T": "10" if "VEHICLE" in set(self.keywords) else "4",
                "Sv": "3" if "VEHICLE" in set(self.keywords) else "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3" if "VEHICLE" in set(self.keywords) else "1",
                "base_size": "60mm" if "VEHICLE" in set(self.keywords) else "32mm",
                "inv_sv": "7",
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_phase = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _ranged_wargear(
    name: str = "Galvanic Carbine",
    *,
    range_value: str = "24",
    strength: str = "4",
    attacks: str = "1",
    damage: str = "1",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": str(range_value),
            "A": str(attacks),
            "BS_WS": "4+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )


def _melee_wargear(
    name: str = "Transonic Blades",
    *,
    attacks: str = "2",
    strength: str = "4",
    ap: str = "-1",
    damage: str = "1",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.auto_resolve_dice_rolls = False

    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Eradication Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    admech_player = Player("AdMech", PlayerControl.LOCAL, army=admech_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.current_player_idx = 0
    admech_player.command_points = 6
    enemy_player.command_points = 6
    return game, admech_player, enemy_player, admech_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"Failed to place {getattr(unit, 'name', 'Unit')}"


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(reaction.get("stratagem", "")) == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if ability and str(context.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _find_option_by_choice(request, choice_key: str):
    wanted = str(choice_key or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == wanted:
            return option
    return None


def _norm_name(value: str) -> str:
    text = str(value or "").strip().upper()
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(dash, "-")
    return text


def test_eradication_cohort_stratagem_descriptors_registered():
    expected = {
        "000010748002": ("Servo-Driven Charge", "melee_weapons_gain_lance"),
        "000010748003": ("Unrelenting Aggression", "shoot_after_fall_back_and_charge_if_skitarii"),
        "000010748004": ("Unshackled Wrath", "ranged_keyword_choice_with_optional_hazardous"),
        "000010748005": ("Threat-Cogitation Targeters", "ranged_damage_reroll_vs_monster_vehicle"),
        "000010748006": ("Precision Onslaught", "charge_end_mortal_wounds_per_engaged_model"),
        "000010748007": ("Analytic Reprisals", "reactive_shooting_at_attacker"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_precision_onslaught_queues_and_adds_charge_end_mortal_wounds_spec():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    sicarians = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        model_count=3,
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for model in list(sicarians.models or []):
        model.wargear = [_melee_wargear()]
    admech_army.add_unit(sicarians)
    enemy_army.add_unit(target)
    _deploy_unit(game, sicarians, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "CHARGE_PHASE", 0)
    game.event_system.publish("charge_declared", unit=sicarians, target_units=[target])

    pending = _pending_by_name(admech_player.stratagems, "PRECISION ONSLAUGHT")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "PRECISION ONSLAUGHT",
        unit=sicarians,
        charging_unit=sicarians,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True

    specs = list(getattr(sicarians, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    assert any(str(spec.get("source_key", "") or "") == "eradication_precision_onslaught" for spec in specs)


def test_analytic_reprisals_queues_after_enemy_shooting_losses_and_creates_reactive_shooting_request():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    retaliators = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for model in list(retaliators.models or []):
        model.wargear = [_ranged_wargear()]
    attacker.models[0].wargear = [_ranged_wargear(name="Enemy Rifle")]
    admech_army.add_unit(retaliators)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, retaliators, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    with patch.object(game, "_setup_reactive_can_shoot_target", return_value=True):
        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[retaliators],
        )
        retaliators.models[0].wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={retaliators: []},
        )

        pending = _pending_by_name(admech_player.stratagems, "ANALYTIC REPRISALS")
        assert pending is not None

        ok = admech_player.stratagems.use(
            "ANALYTIC REPRISALS",
            unit=retaliators,
            attacking_unit=attacker,
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )

    assert ok is True
    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(attacker) or "")


def test_unrelenting_aggression_grants_shoot_after_fall_back_and_charge_only_to_skitarii():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    skitarii.models[0].wargear = [_ranged_wargear()]
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, skitarii, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)
    skitarii.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=skitarii, action="fall_back")
    pending = _pending_by_name(admech_player.stratagems, "UNRELENTING AGGRESSION")
    assert pending is not None
    ok = admech_player.stratagems.use(
        "UNRELENTING AGGRESSION",
        unit=skitarii,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True

    ranged_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_ranged=lambda: True))
    assert skitarii.can_shoot_after_fall_back(ranged_profile) is True
    assert skitarii.can_charge_after_fall_back() is True

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert skitarii.can_shoot_after_fall_back(ranged_profile) is False
    assert skitarii.can_charge_after_fall_back() is False

    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    breachers = _make_unit(
        "Kataphron Breachers",
        keywords=["INFANTRY", "KATAPHRON"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    breachers.models[0].wargear = [_ranged_wargear(name="Heavy Arc Rifle")]
    admech_army.add_unit(breachers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, breachers, 14.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "MOVEMENT_PHASE", 0)
    breachers.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=breachers, action="fall_back")
    pending = _pending_by_name(admech_player.stratagems, "UNRELENTING AGGRESSION")
    assert pending is not None
    ok = admech_player.stratagems.use(
        "UNRELENTING AGGRESSION",
        unit=breachers,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert breachers.can_shoot_after_fall_back(ranged_profile) is True
    assert breachers.can_charge_after_fall_back() is False


def test_unshackled_wrath_queues_choice_request_and_applies_selected_keywords_until_phase_end():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    skitarii.models[0].wargear = [_ranged_wargear(), _melee_wargear(name="Close Combat Weapon")]
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, skitarii, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(admech_player.stratagems, "UNSHACKLED WRATH")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "UNSHACKLED WRATH",
        unit=skitarii,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    request = _first_request(
        game,
        DECISION_CHOOSE_QUARRY,
        ability="eradication_cohort_unshackled_wrath_choice",
    )
    assert request is not None
    option = _find_option_by_choice(request, "OVERDRIVE")
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=admech_player.id)
    assert bool(getattr(result, "ok", False)) is True

    ranged_bonuses = list(skitarii.models[0].get_temporary_weapon_keyword_bonuses("Galvanic Carbine") or [])
    melee_bonuses = list(skitarii.models[0].get_temporary_weapon_keyword_bonuses("Close Combat Weapon") or [])
    keywords = {str(entry.get("keyword", "") or "").strip().upper() for entry in ranged_bonuses}
    assert {"SUSTAINED HITS 1", "LETHAL HITS", "HAZARDOUS"} <= keywords
    assert melee_bonuses == []

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(skitarii.models[0].get_temporary_weapon_keyword_bonuses("Galvanic Carbine") or []) == []


def test_servo_driven_charge_queues_on_fight_phase_start_and_grants_lance_to_melee_only():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    unit = _make_unit(
        "Pteraxii Sterylizors",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unit.models[0].wargear = [_ranged_wargear(name="Flechette Carbine"), _melee_wargear()]
    admech_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(admech_player.stratagems, "SERVO-DRIVEN CHARGE")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "SERVO-DRIVEN CHARGE",
        unit=unit,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    melee_bonuses = list(unit.models[0].get_temporary_weapon_keyword_bonuses("Transonic Blades") or [])
    ranged_bonuses = list(unit.models[0].get_temporary_weapon_keyword_bonuses("Flechette Carbine") or [])
    assert any(str(entry.get("keyword", "") or "").strip().upper() == "LANCE" for entry in melee_bonuses)
    assert ranged_bonuses == []

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(unit.models[0].get_temporary_weapon_keyword_bonuses("Transonic Blades") or []) == []


def test_threat_cogitation_targeters_marks_dynamic_monster_vehicle_damage_reroll_rule_until_phase_end():
    game, admech_player, enemy_player, admech_army, enemy_army = _build_game()
    dunecrawler = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    dunecrawler.models[0].wargear = [_ranged_wargear(name="Neutron Laser", damage="D6")]
    admech_army.add_unit(dunecrawler)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, dunecrawler, 10.0, 10.0)
    _deploy_unit(game, enemy, 26.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(admech_player.stratagems, "THREAT-COGITATION TARGETERS")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "THREAT-COGITATION TARGETERS",
        unit=dunecrawler,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    rule = dunecrawler.get_monster_vehicle_reroll_rule(dunecrawler.models[0])
    assert isinstance(rule, dict)
    assert rule.get("reroll_damage") is True
    assert str(rule.get("attack_type", "") or "").strip().lower() == "ranged"
    assert rule.get("requires_shooting_phase") is True
    sources_text = " ".join(list(rule.get("sources", []) or [])) or str(rule.get("source", "") or "")
    assert "THREAT" in sources_text.upper()

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert dunecrawler.get_monster_vehicle_reroll_rule(dunecrawler.models[0]) is None
