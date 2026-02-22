from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "8",
        oc: str = "1",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": str(oc),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
    wounds: str = "8",
    oc: str = "1",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            oc=oc,
        )
    )
    unit.deployed = True
    return unit


def _make_profile(*, ranged: bool, strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not ranged,
        is_ranged=lambda: ranged,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_simple_game(*, armies: list[Army], phase_name: str, current_player_index: int = 0):
    players = []
    for idx, army in enumerate(list(armies or [])):
        player = SimpleNamespace(
            id=f"P{idx + 1}",
            name=f"P{idx + 1}",
            game=None,
            has_control=lambda: False,
            get_army=lambda a=army: a,
        )
        army.player = player
        players.append(player)
    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        players=players,
        map=SimpleNamespace(roll_reroll_provider=None),
        get_current_player=lambda: players[int(current_player_index)],
    )
    for player in list(players or []):
        player.game = game
    return game


def _build_engine_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("P1", "Warpmeld Pact")
    army1.faction_id = "TS"
    army2 = Army("P2", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _option_with_choice(request, choice: bool):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return opt
    raise AssertionError(f"No option with choice={choice}.")


def test_warpmeld_pact_validation_applies_tzaangors_battleline_keyword():
    army = Army("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(tzaangors)

    army.validate_detachment_rules()

    keywords = [str(k or "").strip().lower() for k in list(getattr(tzaangors, "keywords", []) or [])]
    assert "battleline" in keywords


def test_warpmeld_pact_tzaangor_oc_bonus_requires_not_battle_shocked():
    army = Army("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    tzaangors = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        oc="1",
    )
    army.add_unit(tzaangors)
    army.validate_detachment_rules()

    model = tzaangors.models[0]
    assert int(model.objective_control) == 2

    tzaangors.status_effects = [BattleShockEffect(current_turn=1)]
    assert int(model.objective_control) == 1


def test_warpmeld_sacrifice_offense_adds_wound_bonus():
    army = Army("Thousand Sons", "Warpmeld Pact")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    attacker_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    game = _build_simple_game(armies=[army, enemy_army], phase_name="SHOOTING_PHASE", current_player_index=0)

    mgr = army.thousand_sons_detachments
    assert mgr.activate_warpmeld_sacrifice(attacker_unit, mode="offense", game=game)

    profile = _make_profile(ranged=True, strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result["wound"] is True
    assert any("Warpmeld Sacrifice" in str(entry) for entry in wound_result.get("modifiers", []))


def test_warpmeld_sacrifice_defense_subtracts_from_enemy_wound_roll():
    defender_army = Army("Thousand Sons", "Warpmeld Pact")
    defender_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    defender_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
    )
    attacker_unit = _make_unit(
        "Enemy Shooter",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    defender_army.add_unit(defender_unit)
    enemy_army.add_unit(attacker_unit)
    game = _build_simple_game(armies=[defender_army, enemy_army], phase_name="SHOOTING_PHASE", current_player_index=1)

    mgr = defender_army.thousand_sons_detachments
    assert mgr.activate_warpmeld_sacrifice(defender_unit, mode="defense", game=game)

    profile = _make_profile(ranged=True, strength="4")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = profile._wound_target_with_tracking(
        defender_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound_result["wound"] is False
    assert any("Warpmeld Sacrifice" in str(entry) and "-1" in str(entry) for entry in wound_result.get("modifiers", []))


def test_warpmeld_prompt_resolution_and_phase_end_mortals(monkeypatch):
    game, army1, army2, p1, _p2 = _build_engine_game()
    warpmeld_unit = _make_unit(
        "Tzaangors",
        keywords=["THOUSAND SONS", "TZEENTCH", "MUTANT", "INFANTRY", "TZAANGOR"],
        faction_keywords=["THOUSAND SONS"],
        wounds="8",
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="8",
    )
    army1.add_unit(warpmeld_unit)
    army2.add_unit(enemy_unit)
    game.map.units = [warpmeld_unit, enemy_unit]
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_thousand_sons_warpmeld_sacrifice(
        attacking_unit=warpmeld_unit,
        target_units=[enemy_unit],
    )

    unit_id = str(get_entity_id(warpmeld_unit) or "")
    requests = [
        r
        for r in list(game.decision_queue.list() or [])
        if str(getattr(r, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((r.context or {}).get("ability", "") or "") == "warpmeld_sacrifice"
        and str((r.context or {}).get("ability_mode", "") or "") == "offense"
        and str((r.context or {}).get("unit_id", "") or "") == unit_id
    ]
    assert requests
    request = requests[0]
    use_opt = _option_with_choice(request, True)
    resolved = resolve_decision_command(game, request, use_opt.option_id, player_id=p1.id)
    assert bool(getattr(resolved, "ok", False))

    mgr = army1.thousand_sons_detachments
    assert int(mgr.warpmeld_sacrifice_attacker_wound_bonus(warpmeld_unit.models[0], game=game) or 0) == 1

    before = int(warpmeld_unit.models[0].wounds)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _dice: 2)
    game._on_phase_end_thousand_sons_warpmeld_sacrifice(
        player=game.get_current_player(),
        phase=BattleRoundPhases.SHOOTING_PHASE,
    )
    after = int(warpmeld_unit.models[0].wounds)

    assert int(before - after) == 2
    assert int(mgr.warpmeld_sacrifice_attacker_wound_bonus(warpmeld_unit.models[0], game=game) or 0) == 0
