from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="World Eaters",
        keywords=None,
        faction_keywords=None,
        cost=100,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "6",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, faction_name="World Eaters", keywords=None, faction_keywords=None, cost=100):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        cost=cost,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_pos(unit, x, y, z=0.0):
    for model in list(getattr(unit, "models", []) or []):
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        base.x = float(x)
        base.y = float(y)
        try:
            base.z = float(z)
        except Exception:
            pass


def _make_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.player import Player, PlayerControl
    from warhammer40k_ai.roster.army import Army

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    we_army = Army.with_detachment("World Eaters", "Cult of Blood")
    we_army.faction_id = "WE"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=we_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    return game, we_army, enemy_army, p1, p2


def test_cult_of_blood_adds_battleline_keywords():
    from warhammer40k_ai.roster.army import Army

    army = Army.with_detachment("World Eaters", "Cult of Blood")
    army.faction_id = "WE"
    jakhals = _make_unit(
        "Jakhals",
        keywords=["JAKHALS"],
        faction_keywords=["WORLD EATERS"],
    )
    army.add_unit(jakhals)
    assert jakhals.is_battleline is True
    assert any(str(k).lower() == "battleline" for k in (jakhals.keywords or []))


def test_idols_of_khorne_prompt_queues_decision():
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_IDOL_OF_KHORNE

    game, we_army, _enemy_army, p1, _p2 = _make_game()
    mgr = we_army.world_eaters_detachments
    mgr.on_command_phase_start(game=game, player=p1)

    reqs = list(game.decision_queue.list() or [])
    assert any(r.decision_type == DECISION_CHOOSE_IDOL_OF_KHORNE for r in reqs)
    req = next(r for r in reqs if r.decision_type == DECISION_CHOOSE_IDOL_OF_KHORNE)
    labels = [opt.label for opt in list(req.options or [])]
    assert "None" in labels


def test_idol_of_infinite_rage_applies_hit_and_wound_bonus():
    from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers

    game, we_army, enemy_army, _p1, _p2 = _make_game()
    mgr = we_army.world_eaters_detachments
    assert mgr.activate_idol_of_khorne("INFINITE_RAGE")

    source = _make_unit(
        "World Eaters Titan",
        keywords=["TITANIC"],
        faction_keywords=["WORLD EATERS"],
    )
    attacker = _make_unit(
        "Jakhals",
        keywords=["JAKHALS"],
        faction_keywords=["WORLD EATERS"],
    )
    target = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )

    we_army.add_unit(source)
    we_army.add_unit(attacker)
    enemy_army.add_unit(target)

    _set_unit_pos(source, 0, 0)
    _set_unit_pos(attacker, 8, 0)
    _set_unit_pos(target, 12, 0)

    game.map.units = [source, attacker, target]

    weapon_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False))

    mods = get_aura_attack_modifiers(attacker, target, weapon_profile, game_map=game.map)
    assert int(mods.hit) == 1
    assert int(mods.wound) == 1


def test_idol_of_burning_wrath_applies_move_and_roll_bonuses():
    from warhammer40k_ai.utility.aura_effects import get_aura_advance_charge_roll_modifiers

    game, we_army, enemy_army, _p1, _p2 = _make_game()
    mgr = we_army.world_eaters_detachments
    assert mgr.activate_idol_of_khorne("BURNING_WRATH")

    source = _make_unit(
        "World Eaters Titan",
        keywords=["TITANIC"],
        faction_keywords=["WORLD EATERS"],
    )
    unit = _make_unit(
        "Goremongers",
        keywords=["GOREMONGERS"],
        faction_keywords=["WORLD EATERS"],
    )
    target = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )

    we_army.add_unit(source)
    we_army.add_unit(unit)
    enemy_army.add_unit(target)

    _set_unit_pos(source, 0, 0)
    _set_unit_pos(unit, 8, 0)
    _set_unit_pos(target, 12, 0)

    game.map.units = [source, unit, target]

    advance_mods, charge_mods = get_aura_advance_charge_roll_modifiers(unit, game_map=game.map)
    assert any(int(val) == 1 for val, _ in advance_mods)
    assert any(int(val) == 1 for val, _ in charge_mods)

    move_val = unit.get_effective_model_characteristic(unit.models[0], "movement", game_map=game.map)
    assert int(move_val) == 7


def test_idol_of_blessed_blood_grants_invulnerable_save():
    from warhammer40k_ai.units.wargear import WargearProfile

    game, we_army, enemy_army, _p1, _p2 = _make_game()
    mgr = we_army.world_eaters_detachments
    assert mgr.activate_idol_of_khorne("BLESSED_BLOOD")

    source = _make_unit(
        "World Eaters Titan",
        keywords=["TITANIC"],
        faction_keywords=["WORLD EATERS"],
    )
    unit = _make_unit(
        "Jakhals",
        keywords=["JAKHALS"],
        faction_keywords=["WORLD EATERS"],
    )
    target = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )

    we_army.add_unit(source)
    we_army.add_unit(unit)
    enemy_army.add_unit(target)

    _set_unit_pos(source, 0, 0)
    _set_unit_pos(unit, 8, 0)
    _set_unit_pos(target, 12, 0)

    game.map.units = [source, unit, target]

    melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=melee_parent,
    )

    target_model = unit.models[0]
    save_res = profile._save_with_tracking(target_model, {}, ap=0)
    assert int(save_res.get("final_save", 0)) == 4
