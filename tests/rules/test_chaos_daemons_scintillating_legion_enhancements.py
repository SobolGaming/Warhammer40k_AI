from types import SimpleNamespace

from warhammer40k_ai.engine.game import Game, Battlefield
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear, WargearProfile


class MockDatasheet:
    def __init__(self, name: str, keywords=None, movement=6, model_count=1, base_size="32mm", save="4", wounds="5"):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": str(wounds),
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _attack_result(profile_name="Test Weapon"):
    return AttackResult(
        weapon_name=profile_name,
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="1",
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _make_cd_army(detachment: str):
    army = Army("Chaos Daemons", detachment)
    army.faction_id = "CD"
    return army


def test_inescapable_eye_grants_extra_flux_token():
    game = Game(Battlefield(width=44, height=30))
    army = _make_cd_army("Scintillating Legion")
    opponent = Army("Opponents", "Other")

    p1 = Player("P1", PlayerControl.LOCAL, army)
    p2 = Player("P2", PlayerControl.REMOTE, opponent)
    game.add_player(p1)
    game.add_player(p2)

    unit = Unit(MockDatasheet("Bearer", model_count=1))
    unit.deployed = True
    army.add_unit(unit)

    enh = Enhancement(
        id="000009810002",
        name="Inescapable Eye",
        faction_id="CD",
        detachment="Scintillating Legion",
    )
    enh.apply_to_unit(unit)

    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    mgr.tokens_by_player_id[str(p2.id)] = 1
    game.turn = 1

    before = mgr.tokens_for_player(p1)
    mgr.on_command_phase_start(game=game, player=p1)
    assert mgr.tokens_for_player(p1) == before + 2


def test_neverblade_melee_bonuses_and_hit_bonus(monkeypatch):
    army = _make_cd_army("Scintillating Legion")
    unit = Unit(MockDatasheet("Neverblade Bearer", model_count=1))
    unit.deployed = True
    army.add_unit(unit)

    Enhancement(
        id="000009810004",
        name="Neverblade",
        faction_id="CD",
        detachment="Scintillating Legion",
    ).apply_to_unit(unit)

    weapon = Wargear({
        "name": "Test Sword",
        "type": "Melee",
        "range": "Melee",
        "A": "2",
        "BS_WS": "3",
        "S": "5",
        "AP": "-1",
        "D": "1",
        "description": "",
    })
    profile = weapon.profiles["default"]
    attacker = unit.models[0]

    target = SimpleNamespace(toughness=5, models=[SimpleNamespace(is_alive=True)])

    result = profile._resolve_attack_count(
        target,
        attacker,
        _attack_result(),
        publish_roll_event=False,
    )
    assert result.num_attacks == 3

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 3)
    res = profile._wound_target_with_tracking(target, attacker, attack_instance={})
    assert res["wound"] is True

    target_unit = Unit(MockDatasheet("Target", model_count=1))
    target_unit.deployed = True
    ap_val = profile.get_effective_ap(attacker, target_unit)
    assert ap_val == -2

    # +1 to hit from Neverblade
    hit = profile._hit_target_with_tracking(
        target_unit,
        attacker,
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit["hit"] is True

    # Control: same roll without enhancement should miss
    unit_no = Unit(MockDatasheet("No Bonus", model_count=1))
    unit_no.deployed = True
    attacker_no = unit_no.models[0]
    weapon_no = Wargear({
        "name": "Test Sword",
        "type": "Melee",
        "range": "Melee",
        "A": "2",
        "BS_WS": "3",
        "S": "5",
        "AP": "-1",
        "D": "1",
        "description": "",
    })
    profile_no = weapon_no.profiles["default"]
    miss = profile_no._hit_target_with_tracking(
        target_unit,
        attacker_no,
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert miss["hit"] is False


def test_infernal_puppeteer_does_not_override_attacks():
    army = _make_cd_army("Scintillating Legion")

    bearer = Unit.__new__(Unit)
    bearer.name = "Bearer"
    bearer._id = "bearer"
    bearer.deployed = True
    bearer.get_parent_army = lambda: army
    bearer.special_rules = {"enhancement_infernal_puppeteer": True}

    origin = Unit.__new__(Unit)
    origin.name = "Origin"
    origin._id = "origin"
    origin.deployed = True
    origin.get_parent_army = lambda: army

    target = Unit.__new__(Unit)
    target.name = "Target"
    target._id = "target"

    bearer_model = SimpleNamespace(is_alive=True, name="Bearer Model")
    origin_model = SimpleNamespace(is_alive=True, name="Origin Model")
    target_model = SimpleNamespace(is_alive=True, name="Target Model")

    bearer.models = [bearer_model]
    origin.models = [origin_model]
    target.models = [target_model]

    weapon = SimpleNamespace()
    weapon.name = "Test Gun"
    weapon.profiles = {}

    profile = WargearProfile.__new__(WargearProfile)
    profile.name = "Test Gun"
    profile.keywords = []
    profile.parent_wargear = weapon
    profile.range = SimpleNamespace(max=24.0)
    profile.attacks = SimpleNamespace(value=2)
    profile.is_one_shot = lambda: False
    profile.is_bubblechukka = lambda: False

    attack_calls = []
    def mock_attack(*args, **kwargs):
        attack_calls.append(kwargs)
        return SimpleNamespace(total_hits=1)

    profile.attack = mock_attack
    weapon.profiles["default"] = profile
    bearer_model.wargear = [weapon]

    game_map = SimpleNamespace()
    game_map.has_line_of_sight = lambda m1, m2: True

    bearer._can_model_shoot_weapon_at_target = lambda m, wp, tu, gm, origin_unit=None: True

    bearer._execute_weapon_attacks(
        profile,
        target,
        [bearer_model],
        game_map,
        linked_fire_origin_unit=origin,
        linked_fire_mode="infernal_puppeteer",
    )

    assert attack_calls
    assert attack_calls[0].get("attacks_override") is None


def test_infernal_puppeteer_origin_requires_visibility_when_map_available(monkeypatch):
    from warhammer40k_ai.utility.aura_utils import get_eligible_infernal_puppeteer_origin_units

    army = _make_cd_army("Scintillating Legion")

    bearer = Unit.__new__(Unit)
    bearer.name = "Bearer"
    bearer._id = "bearer"
    bearer.deployed = True
    bearer.models = [SimpleNamespace(name="Bearer Model", is_alive=True)]
    bearer.get_parent_army = lambda: army

    origin_visible = Unit.__new__(Unit)
    origin_visible.name = "Visible Origin"
    origin_visible._id = "visible"
    origin_visible.deployed = True
    origin_visible.models = [SimpleNamespace(name="Visible Model", is_alive=True)]
    origin_visible.get_parent_army = lambda: army
    origin_visible.has_any_keyword = lambda kw: str(kw).strip().upper() in {"LEGIONES DAEMONICA", "TZEENTCH"}
    origin_visible.is_alive = lambda: True

    origin_hidden = Unit.__new__(Unit)
    origin_hidden.name = "Hidden Origin"
    origin_hidden._id = "hidden"
    origin_hidden.deployed = True
    origin_hidden.models = [SimpleNamespace(name="Hidden Model", is_alive=True)]
    origin_hidden.get_parent_army = lambda: army
    origin_hidden.has_any_keyword = lambda kw: str(kw).strip().upper() in {"LEGIONES DAEMONICA", "TZEENTCH"}
    origin_hidden.is_alive = lambda: True

    class _Map:
        def get_friendly_units(self, _unit):
            return [bearer, origin_visible, origin_hidden]

        def can_model_see_model(self, _from_model, to_model):
            return bool(getattr(to_model, "name", "") == "Visible Model")

    monkeypatch.setattr("warhammer40k_ai.utility.aura_utils.model_within_range_of_unit", lambda *_a, **_k: True)

    eligible = get_eligible_infernal_puppeteer_origin_units(bearer, game_map=_Map(), range_in=9.0)
    eligible_ids = {str(getattr(u, "_id", "")) for u in eligible}
    assert eligible_ids == {"visible"}


def test_improbable_shield_aura_grants_fnp():
    army = _make_cd_army("Scintillating Legion")

    bearer = Unit(MockDatasheet("Shield Bearer", model_count=1, keywords=["TZEENTCH", "LEGIONES DAEMONICA"]))
    bearer.deployed = True
    army.add_unit(bearer)

    target = Unit(MockDatasheet("Target", model_count=1, keywords=["TZEENTCH", "LEGIONES DAEMONICA"]))
    target.deployed = True
    army.add_unit(target)

    # Position units within 6"
    bearer.models[0].model_base.x = 0.0
    bearer.models[0].model_base.y = 0.0
    bearer.models[0].model_base.z = 0.0
    target.models[0].model_base.x = 3.0
    target.models[0].model_base.y = 0.0
    target.models[0].model_base.z = 0.0

    Enhancement(
        id="000009810005",
        name="Improbable Shield (Aura)",
        faction_id="CD",
        detachment="Scintillating Legion",
    ).apply_to_unit(bearer)

    entries = target.has_feel_no_pain(target_model=target.models[0])
    assert any(int(val) == 4 and "psychic" in str(cond or "").lower() for val, cond in entries)

    # Outside range: no FNP from Improbable Shield
    far = Unit(MockDatasheet("Far", model_count=1, keywords=["TZEENTCH", "LEGIONES DAEMONICA"]))
    far.deployed = True
    army.add_unit(far)
    far.models[0].model_base.x = 20.0
    far.models[0].model_base.y = 0.0
    far.models[0].model_base.z = 0.0

    entries_far = far.has_feel_no_pain(target_model=far.models[0])
    assert not any(int(val) == 4 and "psychic" in str(cond or "").lower() for val, cond in entries_far)
