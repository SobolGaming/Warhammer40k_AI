import os
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


WATCHER_ABILITY = {
    "name": "Watcher in the Dark",
    "description": (
        "Once per battle, in any phase, just after a mortal wound is allocated to an ADEPTUS ASTARTES model "
        "in this unit, this unit can summon a Watcher in the Dark. When it does, until the end of the phase, "
        "models in this unit have the Feel No Pain 4+ ability against mortal wounds. "
        "Designer’s Note: Place a Watcher in the Dark token next to the unit, removing it when this ability has been used."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, wounds=3, faction_name="Space Marines", faction_keywords=None, keywords=None):
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
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_model(name: str, unit: Unit, *, wounds: int = 3) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=int(wounds),
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _make_unit(name, *, abilities=None, wounds=3, faction_name="Space Marines", faction_keywords=None, keywords=None):
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            wounds=wounds,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["ADEPTUS ASTARTES"],
            keywords=keywords or ["INFANTRY"],
        )
    )
    unit.name = name
    return unit


def _make_profile():
    parent = SimpleNamespace(name="Warp Bolt", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
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


def _build_game(*, sm_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", sm_control, army=sm_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 1
    return game, sm_player, enemy_player


def test_watcher_in_the_dark_saves_the_current_non_attack_mortal_wound():
    game, sm_player, enemy_player = _build_game()
    target_unit = _make_unit("Deathwing Knights", abilities=[WATCHER_ABILITY], wounds=3)
    target_unit.models.append(_make_model("Knight 2", target_unit, wounds=3))
    attacker_unit = _make_unit("Enemy Psyker", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["PSYKER"], wounds=3)

    sm_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    target_model = target_unit.models[0]
    sm_player.set_next_optional_decision("WATCHER_IN_THE_DARK", True)

    with patch("warhammer40k_ai.units.model.get_roll", return_value=4):
        damage_applied = target_model.take_damage(1, is_mortal=True, weapon_profile=None, game_map=game.map)

    assert int(damage_applied or 0) == 0
    assert int(target_model.wounds or 0) == 3
    assert target_unit.has_used_unit_once_per_battle("watcher_in_the_dark:watcher_in_the_dark")
    for model in list(target_unit.models or []):
        entries = list(model.get_temporary_fnp_entries() or [])
        assert any(int(value or 0) == 4 and "mortal" in str(cond or "").lower() for value, cond in entries)


def test_watcher_in_the_dark_is_not_a_static_fnp_before_activation():
    target_unit = _make_unit("Deathwing Terminator Squad", abilities=[WATCHER_ABILITY], wounds=3)

    assert list(target_unit.has_feel_no_pain(target_model=target_unit.models[0]) or []) == []


def test_watcher_in_the_dark_can_be_skipped_then_used_on_later_attack_allocated_mortal_wound():
    game, sm_player, enemy_player = _build_game()
    target_unit = _make_unit("Deathwing Terminator Squad", abilities=[WATCHER_ABILITY], wounds=3)
    attacker_unit = _make_unit("Enemy Psyker", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["PSYKER"], wounds=3)

    sm_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    profile = _make_profile()
    target_model = target_unit.models[0]
    attacker_model = attacker_unit.models[0]

    sm_player.set_next_optional_decision("WATCHER_IN_THE_DARK", False)
    first = profile._apply_damage_with_tracking(
        target_model,
        attacker_model,
        1,
        True,
        attack_instance={"mortal_wound": True},
        game_map=game.map,
    )
    assert int(first.get("damage_applied", 0) or 0) == 1
    assert int(target_model.wounds or 0) == 2
    assert not target_unit.has_used_unit_once_per_battle("watcher_in_the_dark:watcher_in_the_dark")

    sm_player.set_next_optional_decision("WATCHER_IN_THE_DARK", True)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        second = profile._apply_damage_with_tracking(
            target_model,
            attacker_model,
            1,
            True,
            attack_instance={"mortal_wound": True},
            game_map=game.map,
        )

    assert int(second.get("fnp_saves", 0) or 0) == 1
    assert int(second.get("damage_applied", 0) or 0) == 0
    assert int(target_model.wounds or 0) == 2
    assert target_unit.has_used_unit_once_per_battle("watcher_in_the_dark:watcher_in_the_dark")


def test_watcher_in_the_dark_local_provider_consumes_queued_confirmation():
    from warhammer40k_ai.utility.decision_utils import resolve_decision_value

    game, sm_player, enemy_player = _build_game(sm_control=PlayerControl.LOCAL)
    target_unit = _make_unit("Deathwing Knights", abilities=[WATCHER_ABILITY], wounds=3)
    attacker_unit = _make_unit("Enemy Psyker", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["PSYKER"], wounds=3)

    sm_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    seen = {"pending": 0}

    def _provider(**kwargs):
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "context", {}).get("ability", "") or "") == "watcher_in_the_dark"
        ]
        assert pending
        req = pending[0]
        seen["pending"] = len(pending)
        option_id = next(
            opt.option_id
            for opt in list(getattr(req, "options", []) or [])
            if bool(getattr(opt, "payload", {}).get("choice", False))
        )
        _, apply_result = resolve_decision_value(game, req, option_id, player_id=getattr(sm_player, "id", None))
        assert apply_result is not None and getattr(apply_result, "ok", False)
        return "use"

    game.install_decision_providers(unit_mortal_wound_fnp_provider=_provider)

    with patch("warhammer40k_ai.units.model.get_roll", return_value=4):
        damage_applied = target_unit.models[0].take_damage(1, is_mortal=True, weapon_profile=None, game_map=game.map)

    assert int(damage_applied or 0) == 0
    assert seen["pending"] == 1
    assert list(game.decision_queue.list() or []) == []
    assert target_unit.has_used_unit_once_per_battle("watcher_in_the_dark:watcher_in_the_dark")


def test_watcher_in_the_dark_without_sync_owner_raises_and_leaves_request_pending():
    from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO

    game, sm_player, enemy_player = _build_game(sm_control=PlayerControl.LOCAL)
    target_unit = _make_unit("Deathwing Knights", abilities=[WATCHER_ABILITY], wounds=3)
    attacker_unit = _make_unit("Enemy Psyker", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["PSYKER"], wounds=3)

    sm_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    with patch("warhammer40k_ai.units.model.get_roll", return_value=4):
        try:
            target_unit.models[0].take_damage(1, is_mortal=True, weapon_profile=None, game_map=game.map)
        except RuntimeError as exc:
            assert "WATCHER_IN_THE_DARK' remained pending without a synchronous decision owner" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError when Watcher in the Dark has no synchronous owner.")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    assert pending[0].decision_type == DECISION_CONFIRM_YES_NO
    assert str((pending[0].context or {}).get("ability", "") or "") == "watcher_in_the_dark"


def test_support_matrix_classifies_watcher_in_the_dark_as_supported():
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Watcher in the Dark",
        WATCHER_ABILITY["description"],
        faction_id="SM",
    )

    assert status == "Supported"
    assert "mortal wound" in str(notes or "").lower()
    assert "feel no pain 4+" in str(notes or "").lower()
