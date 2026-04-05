from __future__ import annotations

import os
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


BLACK_RAGE_DESCRIPTION = (
    'Each time this model makes a melee attack, you can re-roll the Hit roll. '
    'While this model\'s unit is not within 6" of one or more friendly Blood Angels Character models, '
    'or 12" of one or more friendly Chaplain models, it cannot be selected to Fall Back and its Objective '
    'Control characteristic is 0.'
)

_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Enemy"}
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
                "OC": str(int(objective_control)),
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


def _actual_unit(name: str, *, datasheet_id: str | None = None, faction_id: str = "SM") -> Unit:
    return Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id=faction_id))


def _mock_target_unit(name: str = "Enemy Unit") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
    )


def _build_game() -> tuple[Game, Army, Army]:
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)


def _attach_for_test(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    leader.can_be_attached_to = [bodyguard.name]


def _base_oc(model) -> int:
    return int(getattr(model, "_objective_control", 0) or 0)


def _effective_oc(unit: Unit, model, *, game_map) -> int:
    return int(unit.get_effective_model_characteristic(model, "objective_control", game_map=game_map) or 0)


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_black_rage_melee_reroll_applies_only_to_black_rage_models_in_attached_unit() -> None:
    game, sm_army, enemy_army = _build_game()
    death_company = _actual_unit("Death Company Marines")
    captain = _actual_unit("Captain")
    target = _mock_target_unit()

    _attach_for_test(death_company, captain)
    sm_army.add_unit(death_company)
    sm_army.add_unit(captain)
    enemy_army.add_unit(target)
    game.rebuild_entity_registry()

    profile = _make_melee_profile()
    dc_hit = profile._hit_target_with_tracking(
        target,
        death_company.models[0],
        {"distance_to_target": 1.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    leader_hit = profile._hit_target_with_tracking(
        target,
        captain.models[0],
        {"distance_to_target": 1.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )

    assert any("Black Rage" in reason for reason in list(dc_hit.get("reroll_full_reasons", []) or []))
    assert not any("Black Rage" in reason for reason in list(leader_hit.get("reroll_full_reasons", []) or []))


def test_black_rage_objective_control_only_drops_for_black_rage_models() -> None:
    game, sm_army, _enemy_army = _build_game()
    death_company = _actual_unit("Death Company Marines")
    captain = _actual_unit("Captain")

    _attach_for_test(death_company, captain)
    sm_army.add_unit(death_company)
    sm_army.add_unit(captain)
    _deploy(death_company, 0.0, 0.0)
    _deploy(captain, 0.5, 0.0, spacing=0.0)
    game.map.units = [death_company, captain]
    game.rebuild_entity_registry()

    assert _effective_oc(death_company, death_company.models[0], game_map=game.map) == 0
    assert _effective_oc(captain, captain.models[0], game_map=game.map) == _base_oc(captain.models[0])


def test_black_rage_restores_objective_control_near_blood_angels_character() -> None:
    game, sm_army, _enemy_army = _build_game()
    death_company = _actual_unit("Death Company Marines")
    dante = _actual_unit("Commander Dante")

    sm_army.add_unit(death_company)
    sm_army.add_unit(dante)
    _deploy(death_company, 0.0, 0.0)
    _deploy(dante, 20.0, 0.0, spacing=0.0)
    game.map.units = [death_company, dante]
    game.rebuild_entity_registry()

    assert _effective_oc(death_company, death_company.models[0], game_map=game.map) == 0

    _deploy(dante, 5.0, 0.0, spacing=0.0)

    assert _effective_oc(death_company, death_company.models[0], game_map=game.map) == _base_oc(death_company.models[0])


def test_black_rage_restores_objective_control_near_chaplain() -> None:
    game, sm_army, _enemy_army = _build_game()
    death_company = _actual_unit("Death Company Marines")
    chaplain = _actual_unit("Chaplain", datasheet_id="000001174")

    sm_army.add_unit(death_company)
    sm_army.add_unit(chaplain)
    _deploy(death_company, 0.0, 0.0)
    _deploy(chaplain, 20.0, 0.0, spacing=0.0)
    game.map.units = [death_company, chaplain]
    game.rebuild_entity_registry()

    assert _effective_oc(death_company, death_company.models[0], game_map=game.map) == 0

    _deploy(chaplain, 11.0, 0.0, spacing=0.0)

    assert _effective_oc(death_company, death_company.models[0], game_map=game.map) == _base_oc(death_company.models[0])


def test_black_rage_blocks_fall_back_without_support() -> None:
    game, sm_army, _enemy_army = _build_game()
    death_company = _actual_unit("Death Company Marines")
    sm_army.add_unit(death_company)
    _deploy(death_company, 0.0, 0.0)
    game.map.units = [death_company]
    game.rebuild_entity_registry()

    assert death_company.black_rage_fall_back_lock_source(game_map=game.map) == "Black Rage"
    assert death_company.fall_back((6.0, 0.0, 0.0), [], game.map) is False


def test_death_company_captain_self_satisfies_black_rage_support_gate() -> None:
    game, sm_army, _enemy_army = _build_game()
    captain = _actual_unit("Death Company Captain")
    sm_army.add_unit(captain)
    _deploy(captain, 0.0, 0.0, spacing=0.0)
    game.map.units = [captain]
    game.rebuild_entity_registry()

    assert captain.black_rage_fall_back_lock_source(game_map=game.map) == ""
    assert _effective_oc(captain, captain.models[0], game_map=game.map) == _base_oc(captain.models[0])


def test_support_matrix_classifies_black_rage_as_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability("Black Rage", BLACK_RAGE_DESCRIPTION, faction_id="SM")

    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "blood angels character" in lowered
    assert "chaplain" in lowered
    assert "fall back" in lowered
    assert "objective control 0" in lowered
