from __future__ import annotations

import uuid

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


HOLY_PIETY_TEXT = (
    "Each time this model makes a melee attack, unless this model's unit is Battle-shocked, "
    "you can re-roll the Hit roll."
)

THUNDEROUS_HEAD_BUTT_TEXT = (
    "Each time this model's unit is selected to fight, you can select one enemy unit within Engagement Range "
    "of this model and roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy "
    "unit suffers D3+3 mortal wounds."
)

POINT_BLANK_BARRAGE_TEXT = (
    "Each time a model in this unit makes a ranged attack that targets the closest eligible target, improve "
    "the Armour Penetration characteristic of that attack by 1."
)

PSYCHIC_BARRIER_TEXT = (
    "At the start of your opponent's Shooting phase, you can roll one D6: on a 1, this PSYKER's unit suffers "
    "D3 mortal wounds; on a 2+, until the end of the phase, models in this PSYKER's unit have a 4+ invulnerable save."
)

RATLING_BATTLEMUTT_TEXT = (
    "Once per battle, when this unit is selected to shoot, it can use this ability. If it does, until the end "
    "of the phase, ranged weapons equipped by models in this unit have the [LETHAL HITS] ability."
)

SHOOT_SHARP_AND_SCARPER_TEXT = (
    "In your Shooting phase, after this unit has shot, if it is not within Engagement Range of any enemy units, "
    "it can make a Normal move as if it were your Movement phase. If it does, until the end of the turn, this "
    "unit is not eligible to declare a charge."
)


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool = True):
        self._id = str(uuid.uuid4())
        self.name = name
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)

    def is_melee(self) -> bool:
        return not bool(self._ranged)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        move: int = 6,
        toughness: int = 4,
        save: int = 4,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 4,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, decision_type: str, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == decision_type
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _resolve_yes_no(game: Game, request, player: Player, *, use: bool) -> None:
    option_id = None
    for opt in list(getattr(request, "options", []) or []):
        if bool((getattr(opt, "payload", {}) or {}).get("choice", False)) == bool(use):
            option_id = opt.option_id
            break
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is True


def test_holy_piety_grants_melee_hit_reroll_only_while_not_battle_shocked():
    priest = _make_unit(
        "Ministorum Priest",
        abilities=[{"name": "Holy Piety", "description": HOLY_PIETY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="ministorum-priest",
    )
    model = priest.models[0]

    active_mods = priest.get_model_hit_reroll_modifiers(model, attack_type="melee")
    assert bool(active_mods.get("reroll_hit_full", False)) is True
    assert any("holy piety" in str(reason or "").lower() for reason in list(active_mods.get("reroll_hit_full_reasons", ()) or ()))

    priest.apply_status_effect(BattleShockEffect(current_turn=1))
    inactive_mods = priest.get_model_hit_reroll_modifiers(model, attack_type="melee")
    assert bool(inactive_mods.get("reroll_hit_full", False)) is False


def test_thunderous_head_butt_queues_and_applies_mortal_wounds(monkeypatch):
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    nork = _make_unit(
        "Nork Deddog",
        abilities=[{"name": "Thunderous Head-butt", "description": THUNDEROUS_HEAD_BUTT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="nork-deddog",
        wounds=8,
    )
    target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-unit",
        wounds=8,
    )

    am_army.add_unit(nork)
    enemy_army.add_unit(target)
    _deploy(nork, 0.0, 0.0)
    _deploy(target, 0.5, 0.0)
    _register_units(game, nork, target)

    game._on_fight_unit_selected_hammer_aflame(unit=nork)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, "thunderous_head_butt")
    assert request is not None

    rolls = iter([6, 2])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: next(rolls))

    result = resolve_decision_command(game, request, request.options[-1].option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(target.models[0].wounds or 0) == 3


def test_point_blank_barrage_parses_as_closest_target_ap_bonus():
    ogryns = _make_unit(
        "Ogryn Squad",
        abilities=[{"name": "Point-blank Barrage", "description": POINT_BLANK_BARRAGE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="ogryn-squad",
    )
    rule = ogryns.get_closest_eligible_ap_bonus_rule(ogryns.models[0])
    assert rule is not None
    assert int(rule.get("ap_bonus", 0) or 0) == 1
    assert str(rule.get("source", "") or "") == "Point-blank Barrage"


def test_psychic_barrier_success_grants_unit_invulnerable_save(monkeypatch):
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    psyker = _make_unit(
        "Primaris Psyker",
        abilities=[{"name": "Psychic Barrier (Psychic)", "description": PSYCHIC_BARRIER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "INFANTRY", "PSYKER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="primaris-psyker",
        wounds=4,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy")

    am_army.add_unit(psyker)
    enemy_army.add_unit(enemy)
    _deploy(psyker, 0.0, 0.0)
    _deploy(enemy, 12.0, 0.0)
    _register_units(game, psyker, enemy)

    game._on_phase_start_astra_militarum_psychic_barrier(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_request(game, DECISION_CONFIRM_YES_NO, "psychic_barrier")
    assert request is not None

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 2)
    _resolve_yes_no(game, request, am_player, use=True)

    invuln, _source = psyker.models[0].get_temporary_invulnerable_save()
    assert int(invuln or 0) == 4


def test_psychic_barrier_roll_one_inflicts_self_mortal_wounds(monkeypatch):
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1

    psyker = _make_unit(
        "Primaris Psyker",
        abilities=[{"name": "Psychic Barrier (Psychic)", "description": PSYCHIC_BARRIER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHARACTER", "INFANTRY", "PSYKER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="primaris-psyker",
        wounds=4,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy")

    am_army.add_unit(psyker)
    enemy_army.add_unit(enemy)
    _deploy(psyker, 0.0, 0.0)
    _deploy(enemy, 12.0, 0.0)
    _register_units(game, psyker, enemy)

    pre_wounds = int(psyker.models[0].wounds or 0)
    game._on_phase_start_astra_militarum_psychic_barrier(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_request(game, DECISION_CONFIRM_YES_NO, "psychic_barrier")
    assert request is not None

    rolls = iter([1, 3])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: next(rolls))
    _resolve_yes_no(game, request, am_player, use=True)

    assert int(psyker.models[0].wounds or 0) == int(pre_wounds - 3)
    invuln, _source = psyker.models[0].get_temporary_invulnerable_save()
    assert int(invuln or 0) == 0


def test_ratling_battlemutt_applies_lethal_hits_once_per_battle():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    ratlings = _make_unit(
        "Ratlings",
        abilities=[{"name": "Ratling Battlemutt", "description": RATLING_BATTLEMUTT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="ratlings",
    )
    ratlings.models[0].wargear = [_DummyWargear("Sniper Rifle", ranged=True)]
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy")

    am_army.add_unit(ratlings)
    enemy_army.add_unit(target)
    _deploy(ratlings, 0.0, 0.0)
    _deploy(target, 10.0, 0.0)
    _register_units(game, ratlings, target)

    game._on_shooting_targets_selected_ratling_battlemutt(attacking_unit=ratlings, target_units=[target])
    request = _find_request(game, DECISION_CONFIRM_YES_NO, "ratling_battlemutt")
    assert request is not None
    _resolve_yes_no(game, request, am_player, use=True)

    keywords = {entry.get("keyword") for entry in ratlings.models[0].get_temporary_weapon_keyword_bonuses("Sniper Rifle")}
    assert "LETHAL HITS" in keywords
    assert ratlings.has_used_unit_once_per_battle("ratling_battlemutt") is True

    game._on_shooting_targets_selected_ratling_battlemutt(attacking_unit=ratlings, target_units=[target])
    assert _find_request(game, DECISION_CONFIRM_YES_NO, "ratling_battlemutt") is None


def test_shoot_sharp_and_scarper_queues_reactive_move_using_move_characteristic():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    ratlings = _make_unit(
        "Ratlings",
        abilities=[{"name": "Shoot Sharp and Scarper", "description": SHOOT_SHARP_AND_SCARPER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="ratlings",
        move=6,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy")

    am_army.add_unit(ratlings)
    enemy_army.add_unit(enemy)
    _deploy(ratlings, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, ratlings, enemy)

    specs = ratlings.unit_post_shoot_reactive_move_no_charge_specs()
    assert len(specs) == 1
    assert bool(specs[0].get("use_move_characteristic", False)) is True
    assert bool(specs[0].get("requires_not_engaged", False)) is True

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=ratlings)
    request = next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "post_shoot_no_charge"
        ),
        None,
    )
    assert request is not None
    assert int((request.context or {}).get("max_distance", 0) or 0) == 6
    assert str((request.context or {}).get("movement_type", "") or "") == "reactive"
