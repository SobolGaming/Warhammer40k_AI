from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
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


def create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    ds = MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords)
    unit = Unit(ds)
    unit.deployed = True
    return unit


def make_profile(*, range_val: str, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Pulse Rifle" if is_ranged else "Combat Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_tau_army(detachment_type: str) -> Army:
    army = Army("T'au Empire", detachment_type)
    army.faction_id = "TAU"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))
    return army


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


def _attach_ranged_profile(unit: Unit, profile: WargearProfile) -> None:
    model = unit.models[0]
    model.wargear.append(
        SimpleNamespace(
            is_ranged=lambda: True,
            profiles={"default": profile},
        )
    )


def _configure_tau_shooting_game(army: Army, *, battle_round: int):
    game = SimpleNamespace(
        turn=int(battle_round),
        map=None,
        is_shooting_phase=lambda: True,
    )
    player = SimpleNamespace(id="P1", name="Player 1", game=game)
    game.get_current_player = lambda: player
    army.player = player
    return game, player


def test_superior_craftsmanship_adds_six_inches_to_ranged_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 30


def test_superior_craftsmanship_does_not_modify_melee_weapons():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="2", is_ranged=False)

    assert profile._effective_range_max(attacker) == 2


def test_superior_craftsmanship_requires_experimental_prototype_cadre_detachment():
    army = _build_tau_army("Kauyon")
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24


def test_superior_craftsmanship_requires_tau_empire_model_keyword():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Mercenary Squad",
        keywords=["INFANTRY"],
        faction_keywords=["KROOT"],
    )
    army.add_unit(unit)

    attacker = unit.models[0]
    profile = make_profile(range_val="24", is_ranged=True)

    assert profile._effective_range_max(attacker) == 24


def test_killing_blow_grants_assault_for_first_three_rounds():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 2
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is True


def test_killing_blow_assault_expires_after_third_round():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 4
    unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is False


def test_killing_blow_assault_requires_tau_empire_keyword():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 2
    unit = create_unit(
        "Mercenary Squad",
        keywords=["INFANTRY"],
        faction_keywords=["KROOT"],
    )
    army.add_unit(unit)
    profile = make_profile(range_val="24", is_ranged=True)

    assert unit.can_shoot_after_advance(profile) is False


def test_killing_blow_guided_units_gain_lethal_hits_first_three_rounds():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    game, player = _configure_tau_shooting_game(army, battle_round=2)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    observer_unit = create_unit(
        "Pathfinders",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)

    observer_profile = make_profile(range_val="24", is_ranged=True)
    _attach_ranged_profile(observer_unit, observer_profile)

    ftgg = ForTheGreaterGoodManager(army)
    army.for_the_greater_good = ftgg
    assert ftgg.mark_spotted(observer_unit, target_unit, game=game, player=player) is True

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is True
    assert "Lethal Hits" in hit_result.get("special_effects", [])


def test_killing_blow_lethal_hits_do_not_apply_after_third_round():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    game, player = _configure_tau_shooting_game(army, battle_round=4)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    observer_unit = create_unit(
        "Pathfinders",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)

    observer_profile = make_profile(range_val="24", is_ranged=True)
    _attach_ranged_profile(observer_unit, observer_profile)

    ftgg = ForTheGreaterGoodManager(army)
    army.for_the_greater_good = ftgg
    assert ftgg.mark_spotted(observer_unit, target_unit, game=game, player=player) is True

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is not True
    assert "Lethal Hits" not in hit_result.get("special_effects", [])


def test_killing_blow_lethal_hits_require_guided_unit():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    _configure_tau_shooting_game(army, battle_round=2)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(attacker_unit)
    army.for_the_greater_good = ForTheGreaterGoodManager(army)

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    hit_result = attack_profile._hit_target_with_tracking(
        target_unit,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit_result["hit"] is True
    assert attack_instance.get("lethal_hit") is not True
    assert "Lethal Hits" not in hit_result.get("special_effects", [])
