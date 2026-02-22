from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
    ):
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
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _make_profile(*, psychic: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Psychic" if psychic else "",
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


def _build_flow_game(
    *,
    army: Army,
    enemy_army: Army,
    nml_controlled: int,
    nml_total: int = 2,
    enemy_controlled: int = 0,
    enemy_total: int = 0,
):
    player = SimpleNamespace(id="P1", name="P1", game=None, get_army=lambda: army)
    enemy = SimpleNamespace(id="P2", name="P2", game=None, get_army=lambda: enemy_army)
    army.player = player
    enemy_army.player = enemy

    objectives = []

    def _make_objective(x: float, y: float, controller):
        location = SimpleNamespace(
            x=float(x),
            y=float(y),
            removed=False,
            controlling_player=controller,
            update_control=lambda _game: None,
        )
        return SimpleNamespace(location=location)

    for i in range(int(nml_total)):
        controller = player if i < int(nml_controlled) else enemy
        objectives.append(_make_objective(15.0 + float(i), 10.0, controller))
    for i in range(int(enemy_total)):
        controller = player if i < int(enemy_controlled) else enemy
        objectives.append(_make_objective(25.0 + float(i), 10.0, controller))

    def _in_deployment_zone(x: float, _y: float, player_id: str) -> bool:
        x_val = float(x)
        if str(player_id) == str(player.id):
            return x_val <= 10.0
        if str(player_id) == str(enemy.id):
            return x_val >= 20.0
        return False

    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        players=[player, enemy],
        map=SimpleNamespace(objectives=objectives),
        get_current_player=lambda: player,
        is_position_in_deployment_zone=_in_deployment_zone,
        is_position_wholly_in_deployment_zone=lambda x, y, _base, pid: _in_deployment_zone(x, y, pid),
    )
    player.game = game
    enemy.game = game
    return game, enemy, objectives


def test_hexwarp_flow_of_magic_adds_wound_when_wholly_within_snapshot_zone():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    attacker_unit.models[0].set_location(15.0, 10.0, 0.0, 0.0)

    game, enemy_player, objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )

    army.thousand_sons_detachments.on_phase_start(game=game)
    for objective in objectives:
        objective.location.controlling_player = enemy_player

    profile = _make_profile(psychic=True)
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound["wound"] is True
    assert any("Flow of Magic" in str(entry) for entry in wound.get("modifiers", []))
    assert not bool(attack_instance.get("hexwarp_flow_reroll_wound_ones", False))


def test_hexwarp_flow_of_magic_rerolls_wound_roll_of_one_outside_flow(monkeypatch):
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    target_unit = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
    )
    army.add_unit(attacker_unit)
    enemy_army.add_unit(target_unit)
    attacker_unit.models[0].set_location(15.0, 10.0, 0.0, 0.0)

    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=0,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _d: 4)

    profile = _make_profile(psychic=True)
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound = profile._wound_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert int(wound.get("reroll", 0) or 0) == 4
    assert wound["wound"] is True
    assert bool(attack_instance.get("hexwarp_flow_reroll_wound_ones", False))
    assert any("Flow of Magic" in str(entry) for entry in wound.get("special_effects", []))


def test_hexwarp_flow_of_magic_does_not_apply_to_non_psychic_attacks():
    army = Army("Thousand Sons", "Hexwarp Thrallband")
    army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    attacker_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(attacker_unit)

    game, _enemy_player, _objectives = _build_flow_game(
        army=army,
        enemy_army=enemy_army,
        nml_controlled=1,
        nml_total=2,
    )
    army.thousand_sons_detachments.on_phase_start(game=game)

    non_psychic_profile = _make_profile(psychic=False)
    bonus, reroll_ones, source = army.thousand_sons_detachments.hexwarp_flow_of_magic_psychic_wound_modifiers(
        attacker_unit.models[0],
        non_psychic_profile,
        game=game,
    )

    assert int(bonus) == 0
    assert bool(reroll_ones) is False
    assert source == ""
