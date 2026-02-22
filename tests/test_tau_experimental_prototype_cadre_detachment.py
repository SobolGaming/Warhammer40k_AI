from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionQueue, DecisionRequest, DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
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


def make_named_ranged_profile(
    wargear_name: str,
    *,
    range_val: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
) -> tuple[WargearProfile, object]:
    parent = SimpleNamespace(
        name=str(wargear_name),
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": str(strength),
        "AP": str(ap),
        "D": str(damage),
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent), parent


def _supernova_launcher_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983002",
        name="Supernova Launcher",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one airbursting fragmentation projector equipped by the bearer. "
            "Improve the Strength characteristic of that weapon by 3, and improve the Armour Penetration and "
            "Damage characteristics of that weapon by 1."
        ),
    )


def _thermoneutronic_projector_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983003",
        name="Thermoneutronic Projector",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one T'au flamer equipped by the bearer. Improve the Strength "
            "characteristic of that weapon by 2, and improve the Armour Penetration and Damage characteristics "
            "of that weapon by 1."
        ),
    )


def _plasma_accelerator_rifle_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983004",
        name="Plasma Accelerator Rifle",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one plasma rifle equipped by the bearer. Improve the Strength "
            "characteristic of that weapon by 2, and improve the Attacks, Armour Penetration and Damage "
            "characteristics of that weapon by 1."
        ),
    )


def _fusion_blades_enhancement() -> Enhancement:
    return Enhancement(
        id="000009983005",
        name="Fusion Blades",
        faction_id="TAU",
        detachment="Experimental Prototype Cadre",
        description=(
            "T'AU EMPIRE model only. Select one fusion blaster equipped by the bearer. Improve the Attacks "
            "characteristic of that weapon by 1, improve the Strength characteristic of that weapon by 3, "
            "and that weapon has the [MELTA 4] ability."
        ),
    )


def _coordinated_exploitation_enhancement() -> Enhancement:
    return Enhancement(
        id="000008811002",
        name="Coordinated Exploitation",
        faction_id="TAU",
        detachment="Mont'ka",
        description=(
            "T'AU EMPIRE model only (excluding Kroot Shaper models). While the bearer is leading a unit, each time that "
            "unit is an Observer unit, until the end of the phase, ranged weapons equipped by models in a Guided unit "
            "have the [SUSTAINED HITS 1] ability while targeting their Spotted unit."
        ),
    )


def _exemplar_of_montka_enhancement() -> Enhancement:
    return Enhancement(
        id="000008811003",
        name="Exemplar of the Mont'ka",
        faction_id="TAU",
        detachment="Mont'ka",
        description=(
            "T'AU EMPIRE model only (excluding Kroot Shaper models). While the bearer is leading a unit, the Killing Blow "
            "Detachment rule applies to that unit during the fourth battle round as well."
        ),
    )


def _strategic_conqueror_enhancement() -> Enhancement:
    return Enhancement(
        id="000008811004",
        name="Strategic Conqueror",
        faction_id="TAU",
        detachment="Mont'ka",
        description=(
            "T'AU EMPIRE model only. At the start of the first battle round, before the first turn begins, select one objective "
            "marker on the battlefield. While a friendly T'AU EMPIRE model is within range of that objective marker and the bearer "
            "is on the battlefield, add 1 to that friendly model's Objective Control characteristic."
        ),
    )


def _strike_swiftly_enhancement() -> Enhancement:
    return Enhancement(
        id="000008811005",
        name="Strike Swiftly",
        faction_id="TAU",
        detachment="Mont'ka",
        description=(
            "T'AU EMPIRE model only. At the start of the battle, before any moves are made using the Scouts ability, you can "
            "select up to two friendly T'AU EMPIRE units within 6\" of the bearer that do not have the Scouts ability. Until "
            "the end of the battle, all models in the selected units have the Scouts 6\" ability."
        ),
    )


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


def _configure_tau_round_start_game(army: Army, *, objectives: list, battle_round: int = 1):
    game = SimpleNamespace(
        turn=int(battle_round),
        map=SimpleNamespace(objectives=list(objectives)),
        objectives=list(objectives),
        players=[],
        is_authoritative=True,
        decision_queue=DecisionQueue(),
    )
    player = SimpleNamespace(id="P1", name="Player 1", game=game, army=army, get_army=lambda: army, has_control=lambda: True)
    game.players = [player]
    game.get_current_player = lambda: player
    game.request_decision = lambda req: game.decision_queue.add(req)
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


def test_integrated_command_structure_targeting_triangulation_improves_ap(monkeypatch):
    army = _build_tau_army("Auxiliary Cadre")
    shooter = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    spotter = create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(shooter)
    army.add_unit(spotter)

    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit",
        lambda *_args, **_kwargs: True,
    )

    profile = make_profile(range_val="24", is_ranged=True)
    attacker = shooter.models[0]

    assert profile.get_effective_ap(attacker, target) == -1


def test_integrated_command_structure_targeting_triangulation_excludes_kroot_models(monkeypatch):
    army = _build_tau_army("Auxiliary Cadre")
    kroot_attacker = create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    spotter = create_unit(
        "Vespid Stingwings",
        keywords=["INFANTRY", "FLY", "VESPID STINGWINGS"],
        faction_keywords=["T'AU EMPIRE", "VESPID STINGWINGS"],
    )
    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(kroot_attacker)
    army.add_unit(spotter)

    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit",
        lambda *_args, **_kwargs: True,
    )

    profile = make_profile(range_val="24", is_ranged=True)
    attacker = kroot_attacker.models[0]

    assert profile.get_effective_ap(attacker, target) == 0


def test_integrated_command_structure_targeting_triangulation_requires_visibility(monkeypatch):
    army = _build_tau_army("Auxiliary Cadre")
    army.player.game.map = SimpleNamespace(can_model_see_model=lambda *_args, **_kwargs: False)
    shooter = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    spotter = create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    army.add_unit(shooter)
    army.add_unit(spotter)

    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit",
        lambda *_args, **_kwargs: True,
    )

    profile = make_profile(range_val="24", is_ranged=True)
    attacker = shooter.models[0]

    assert profile.get_effective_ap(attacker, target) == 0


def test_integrated_command_structure_localised_stealth_projectors_limit_ranged_targeting(monkeypatch):
    army = _build_tau_army("Auxiliary Cadre")
    projector = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    protected = create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    army.add_unit(projector)
    army.add_unit(protected)

    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.unit_wholly_within_range_of_unit",
        lambda *_args, **_kwargs: True,
    )

    distance, sources = protected.get_ranged_targeting_restriction()

    assert distance == 18.0
    assert any("Integrated Command Structure" in str(src) for src in sources)


def test_integrated_command_structure_localised_stealth_projectors_require_visibility(monkeypatch):
    army = _build_tau_army("Auxiliary Cadre")
    army.player.game.map = SimpleNamespace(can_model_see_model=lambda *_args, **_kwargs: False)
    projector = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    protected = create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    army.add_unit(projector)
    army.add_unit(protected)

    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.unit_wholly_within_range_of_unit",
        lambda *_args, **_kwargs: True,
    )

    distance, sources = protected.get_ranged_targeting_restriction()

    assert distance is None
    assert sources == []


def test_patient_hunter_grants_sustained_hits_in_round_three():
    army = _build_tau_army("Kauyon")
    _configure_tau_shooting_game(army, battle_round=3)
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
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Patient Hunter" in str(entry) for entry in hit_result.get("special_effects", []))


def test_patient_hunter_sustained_hits_not_active_before_round_three():
    army = _build_tau_army("Kauyon")
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
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 0
    assert not any("Patient Hunter" in str(entry) for entry in hit_result.get("special_effects", []))


def test_patient_hunter_guided_attacks_can_ignore_hit_modifiers():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager
    from warhammer40k_ai.units import wargear as wargear_mod
    from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE

    army = _build_tau_army("Kauyon")
    game, player = _configure_tau_shooting_game(army, battle_round=3)
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
    attack_instance = {
        "_aura_attack_mods": _aura_stub(),
        "hit_roll_modifiers": [(-1, "Test penalty")],
        "hit_modifier_choice": CHOICE_IGNORE_NEGATIVE,
    }
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _expr: 3
    try:
        hit_result = attack_profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            attack_instance,
            roll_value=None,
            allow_rerolls=False,
            log_roll=False,
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result["hit"] is True
    assert attack_instance.get("hit_modifier_choice") == CHOICE_IGNORE_NEGATIVE


def test_patient_hunter_ignore_modifiers_requires_guided_attack():
    from warhammer40k_ai.units import wargear as wargear_mod
    from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE

    army = _build_tau_army("Kauyon")
    _configure_tau_shooting_game(army, battle_round=3)
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

    attack_profile = make_profile(range_val="24", is_ranged=True)
    attacker_model = attacker_unit.models[0]
    attack_instance = {
        "_aura_attack_mods": _aura_stub(),
        "hit_roll_modifiers": [(-1, "Test penalty")],
        "hit_modifier_choice": CHOICE_IGNORE_NEGATIVE,
    }
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _expr: 3
    try:
        hit_result = attack_profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            attack_instance,
            roll_value=None,
            allow_rerolls=False,
            log_roll=False,
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result["hit"] is False


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


def test_coordinated_exploitation_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000008811002")
    assert desc is not None
    assert desc.name == "Coordinated Exploitation"
    assert desc.effect == "grant_ranged_sustained_hits_vs_spotted"
    assert int(desc.effect_params.get("sustained_hits_value", 0) or 0) == 1


def test_exemplar_of_montka_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000008811003")
    assert desc is not None
    assert desc.name == "Exemplar of the Mont'ka"
    assert desc.effect == "extend_killing_blow_to_round_four"


def test_strategic_conqueror_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000008811004")
    assert desc is not None
    assert desc.name == "Strategic Conqueror"
    assert desc.effect == "add_objective_control_near_selected_objective"
    assert int(desc.effect_params.get("objective_control_bonus", 0) or 0) == 1


def test_strike_swiftly_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000008811005")
    assert desc is not None
    assert desc.name == "Strike Swiftly"
    assert desc.effect == "grant_scouts_to_selected_units"
    assert int(desc.effect_params.get("max_units", 0) or 0) == 2
    assert int(desc.effect_params.get("scouts_distance", 0) or 0) == 6
    assert int(desc.effect_params.get("selection_range", 0) or 0) == 6


def test_coordinated_exploitation_grants_guided_sustained_hits_when_observer_has_bearer():
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
    observer_leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    observer_unit.attached_leaders = [observer_leader]
    observer_leader.attached_to = observer_unit

    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)
    army.add_unit(observer_leader)

    enhancement = _coordinated_exploitation_enhancement()
    observer_leader.enhancement = enhancement
    enhancement.apply_to_unit(observer_leader)

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
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Coordinated Exploitation" in str(effect) for effect in hit_result.get("special_effects", []))


def test_coordinated_exploitation_requires_bearer_to_be_leading_observer_unit():
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
    unjoined_leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    target_unit = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    army.add_unit(attacker_unit)
    army.add_unit(observer_unit)
    army.add_unit(unjoined_leader)

    enhancement = _coordinated_exploitation_enhancement()
    unjoined_leader.enhancement = enhancement
    enhancement.apply_to_unit(unjoined_leader)

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
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 0
    assert not any("Coordinated Exploitation" in str(effect) for effect in hit_result.get("special_effects", []))


def test_exemplar_of_montka_extends_killing_blow_assault_to_round_four_for_bearers_unit():
    army = _build_tau_army("Mont'ka")
    army.player.game.turn = 4
    bodyguard = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    army.add_unit(bodyguard)
    army.add_unit(leader)

    enhancement = _exemplar_of_montka_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    profile = make_profile(range_val="24", is_ranged=True)
    assert bodyguard.can_shoot_after_advance(profile) is True


def test_exemplar_of_montka_extends_guided_lethal_hits_to_round_four_for_bearers_unit():
    from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

    army = _build_tau_army("Mont'ka")
    game, player = _configure_tau_shooting_game(army, battle_round=4)

    attacker_unit = create_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    attacker_leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    attacker_unit.attached_leaders = [attacker_leader]
    attacker_leader.attached_to = attacker_unit

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
    army.add_unit(attacker_leader)
    army.add_unit(observer_unit)

    enhancement = _exemplar_of_montka_enhancement()
    attacker_leader.enhancement = enhancement
    enhancement.apply_to_unit(attacker_leader)

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


def test_strategic_conqueror_queues_objective_selection_at_start_of_first_battle_round():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(leader)

    enhancement = _strategic_conqueror_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    objective_b = SimpleNamespace(
        id="obj-b",
        name="Objective B",
        location=SimpleNamespace(x=12.0, y=12.0, control_radius=3.0, removed=False),
    )
    objective_a = SimpleNamespace(
        id="obj-a",
        name="Objective A",
        location=SimpleNamespace(x=4.0, y=4.0, control_radius=3.0, removed=False),
    )
    game, _player = _configure_tau_round_start_game(army, objectives=[objective_b, objective_a], battle_round=1)

    army.on_battle_round_start(1)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str(request.context.get("ability", "") or "") == "strategic_conqueror"
    assert str(request.context.get("source_unit_id", "") or "") == str(leader.id)
    objective_ids = [str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "") for opt in request.options]
    assert objective_ids == ["obj-a", "obj-b"]


def test_strategic_conqueror_selected_objective_grants_oc_bonus_while_bearer_on_battlefield():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(leader)

    enhancement = _strategic_conqueror_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    selected_objective = SimpleNamespace(
        id="obj-selected",
        name="Objective Selected",
        location=SimpleNamespace(x=0.0, y=0.0, control_radius=3.0, removed=False),
    )
    other_objective = SimpleNamespace(
        id="obj-other",
        name="Objective Other",
        location=SimpleNamespace(x=30.0, y=30.0, control_radius=3.0, removed=False),
    )
    game, player = _configure_tau_round_start_game(
        army,
        objectives=[selected_objective, other_objective],
        battle_round=1,
    )

    army.on_battle_round_start(1)
    request = list(game.decision_queue.list() or [])[0]
    option_id = None
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("objective_id", "") or "") == "obj-selected":
            option_id = getattr(opt, "option_id", None)
            break
    assert option_id is not None

    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=str(option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)
    assert apply_result.ok is True
    assert str(leader.special_rules.get("enhancement_strategic_conqueror_selected_objective_id", "") or "") == "obj-selected"

    bearer_model = leader.models[0]
    bearer_model.set_location(0.0, 0.0, 0.0, 0.0)
    assert bearer_model.objective_control == 2

    bearer_model.set_location(24.0, 24.0, 0.0, 0.0)
    assert bearer_model.objective_control == 1

    bearer_model.wounds = 0
    bearer_model.set_location(0.0, 0.0, 0.0, 0.0)
    assert bearer_model.objective_control == 1


def test_strategic_conqueror_rejects_invalid_objective_choice():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(leader)

    enhancement = _strategic_conqueror_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    existing_objective = SimpleNamespace(
        id="obj-existing",
        name="Objective Existing",
        location=SimpleNamespace(x=10.0, y=10.0, control_radius=3.0, removed=False),
    )
    game, player = _configure_tau_round_start_game(army, objectives=[existing_objective], battle_round=1)

    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Strategic Conqueror: select one objective marker on the battlefield.",
        player_id=getattr(player, "id", None),
        options=[DecisionOption.create("Invalid objective", payload={"objective_id": "obj-missing"})],
        context={
            "ability": "strategic_conqueror",
            "ability_name": "Strategic Conqueror",
            "source_unit_id": str(leader.id),
            "unit_id": str(leader.id),
            "optional": False,
        },
    )
    option_id = str(request.options[0].option_id)
    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)

    assert apply_result.ok is False
    assert any("objective marker" in str(err).lower() for err in apply_result.errors)


def test_strike_swiftly_queues_up_to_two_unit_selection_before_scout_moves():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_a = create_unit(
        "Strike Team A",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_b = create_unit(
        "Strike Team B",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    far_unit = create_unit(
        "Strike Team Far",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    has_scout = create_unit(
        "Pathfinders",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    has_scout.special_rules["enhancement_scout_distance"] = 6
    for unit in (leader, near_a, near_b, far_unit, has_scout):
        army.add_unit(unit)

    leader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    near_a.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    near_b.models[0].set_location(0.0, 5.0, 0.0, 0.0)
    far_unit.models[0].set_location(12.0, 0.0, 0.0, 0.0)
    has_scout.models[0].set_location(3.0, 3.0, 0.0, 0.0)

    enhancement = _strike_swiftly_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    game, _player = _configure_tau_round_start_game(army, objectives=[], battle_round=1)
    army.on_prebattle_rules_start(game=game)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str(request.context.get("ability", "") or "") == "strike_swiftly"
    assert str(request.context.get("source_unit_id", "") or "") == str(leader.id)

    options = list(request.options or [])
    assert options
    first_payload = dict(getattr(options[0], "payload", {}) or {})
    assert str(first_payload.get("action", "") or "").lower() == "skip"

    near_a_id = str(near_a.id)
    near_b_id = str(near_b.id)
    far_id = str(far_unit.id)
    has_scout_id = str(has_scout.id)
    selected_sets = {
        frozenset(
            str(v or "") for v in list((dict(getattr(opt, "payload", {}) or {}).get("selected_unit_ids") or []))
        )
        for opt in options
    }
    assert frozenset({near_a_id}) in selected_sets
    assert frozenset({near_b_id}) in selected_sets
    assert frozenset({near_a_id, near_b_id}) in selected_sets
    assert frozenset({far_id}) not in selected_sets
    assert frozenset({has_scout_id}) not in selected_sets


def test_strike_swiftly_selected_units_gain_scouts_six_for_battle():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_a = create_unit(
        "Strike Team A",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_b = create_unit(
        "Strike Team B",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    far_unit = create_unit(
        "Strike Team Far",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    for unit in (leader, near_a, near_b, far_unit):
        army.add_unit(unit)

    leader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    near_a.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    near_b.models[0].set_location(0.0, 5.0, 0.0, 0.0)
    far_unit.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    enhancement = _strike_swiftly_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    game, player = _configure_tau_round_start_game(army, objectives=[], battle_round=1)
    army.on_prebattle_rules_start(game=game)
    request = list(game.decision_queue.list() or [])[0]

    near_ids = {str(near_a.id), str(near_b.id)}
    option_id = None
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        ids = {str(v or "") for v in list(payload.get("selected_unit_ids") or []) if str(v or "")}
        if ids == near_ids:
            option_id = str(getattr(opt, "option_id", "") or "")
            break
    assert option_id

    before_a, dist_a = near_a.has_scout()
    before_b, dist_b = near_b.has_scout()
    before_far, dist_far = far_unit.has_scout()
    assert before_a is False and float(dist_a) == 0.0
    assert before_b is False and float(dist_b) == 0.0
    assert before_far is False and float(dist_far) == 0.0

    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)
    assert apply_result.ok is True

    after_a, dist_a = near_a.has_scout()
    after_b, dist_b = near_b.has_scout()
    after_far, dist_far = far_unit.has_scout()
    assert after_a is True and float(dist_a) == 6.0
    assert after_b is True and float(dist_b) == 6.0
    assert after_far is False and float(dist_far) == 0.0

    selected_ids = sorted(str(v or "") for v in list(leader.special_rules.get("enhancement_strike_swiftly_selected_unit_ids", []) or []))
    assert selected_ids == sorted(list(near_ids))
    assert bool(leader.special_rules.get("enhancement_strike_swiftly_resolved")) is True


def test_strike_swiftly_rejects_ineligible_selection():
    army = _build_tau_army("Mont'ka")
    leader = create_unit(
        "Cadre Fireblade",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    near_unit = create_unit(
        "Strike Team Near",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    far_unit = create_unit(
        "Strike Team Far",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    for unit in (leader, near_unit, far_unit):
        army.add_unit(unit)

    leader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    near_unit.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    far_unit.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    enhancement = _strike_swiftly_enhancement()
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    game, player = _configure_tau_round_start_game(army, objectives=[], battle_round=1)
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Strike Swiftly: select up to two friendly T'AU EMPIRE units within 6\" that do not have Scouts.",
        player_id=getattr(player, "id", None),
        options=[DecisionOption.create("Invalid far unit", payload={"selected_unit_ids": [str(far_unit.id)]})],
        context={
            "ability": "strike_swiftly",
            "ability_name": "Strike Swiftly",
            "source_unit_id": str(leader.id),
            "unit_id": str(leader.id),
            "optional": True,
        },
    )
    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=str(request.options[0].option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)

    assert apply_result.ok is False
    assert any("ineligible" in str(err).lower() for err in apply_result.errors)


def test_supernova_launcher_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983002")
    assert desc is not None
    assert desc.name == "Supernova Launcher"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "airbursting fragmentation projector"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 3
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_supernova_launcher_buffs_selected_airbursting_weapon_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    airburst_profile, airburst_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([airburst_wargear, burst_wargear])

    enhancement = _supernova_launcher_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target_for_wound = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    airburst_wound = airburst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert airburst_profile.get_effective_ap(attacker, target_for_wound) == -1
    assert burst_profile.get_effective_ap(attacker, target_for_wound) == 0
    assert any("Supernova Launcher" in str(entry) and "+3S" in str(entry) for entry in airburst_wound.get("modifiers", []))
    assert not any("Supernova Launcher" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = airburst_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Supernova Launcher +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Supernova Launcher +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_supernova_launcher_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    second_profile, second_wargear = make_named_ranged_profile("Airbursting Fragmentation Projector")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _supernova_launcher_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_supernova_launcher", False))
    assert int(unit.special_rules.get("enhancement_supernova_launcher_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert any("Supernova Launcher" in str(entry) and "+3S" in str(entry) for entry in first_wound.get("modifiers", []))
    assert not any("Supernova Launcher" in str(entry) for entry in second_wound.get("modifiers", []))


def test_thermoneutronic_projector_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983003")
    assert desc is not None
    assert desc.name == "Thermoneutronic Projector"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "t'au flamer"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 2
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_thermoneutronic_projector_buffs_selected_tau_flamer_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    flamer_profile, flamer_wargear = make_named_ranged_profile("T'au Flamer")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([flamer_wargear, burst_wargear])

    enhancement = _thermoneutronic_projector_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target_for_wound = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    flamer_wound = flamer_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target_for_wound,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert flamer_profile.get_effective_ap(attacker, target_for_wound) == -1
    assert burst_profile.get_effective_ap(attacker, target_for_wound) == 0
    assert any(
        "Thermoneutronic Projector" in str(entry) and "+2S" in str(entry)
        for entry in flamer_wound.get("modifiers", [])
    )
    assert not any("Thermoneutronic Projector" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = flamer_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Thermoneutronic Projector +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Thermoneutronic Projector +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_thermoneutronic_projector_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("T'au Flamer")
    second_profile, second_wargear = make_named_ranged_profile("T'au Flamer")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _thermoneutronic_projector_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_thermoneutronic_projector", False))
    assert int(unit.special_rules.get("enhancement_thermoneutronic_projector_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert any(
        "Thermoneutronic Projector" in str(entry) and "+2S" in str(entry)
        for entry in first_wound.get("modifiers", [])
    )
    assert not any("Thermoneutronic Projector" in str(entry) for entry in second_wound.get("modifiers", []))


def test_plasma_accelerator_rifle_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983004")
    assert desc is not None
    assert desc.name == "Plasma Accelerator Rifle"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "plasma rifle"
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 2
    assert int(desc.effect_params.get("attacks_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("damage_bonus", 0) or 0) == 1


def test_plasma_accelerator_rifle_buffs_selected_plasma_rifle_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    plasma_profile, plasma_wargear = make_named_ranged_profile("Plasma Rifle")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([plasma_wargear, burst_wargear])

    enhancement = _plasma_accelerator_rifle_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    plasma_wound = plasma_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert plasma_profile.get_effective_ap(attacker, target) == -1
    assert burst_profile.get_effective_ap(attacker, target) == 0
    assert any(
        "Plasma Accelerator Rifle" in str(entry) and "+2S" in str(entry)
        for entry in plasma_wound.get("modifiers", [])
    )
    assert not any("Plasma Accelerator Rifle" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_attack_count = plasma_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    other_attack_count = burst_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    assert selected_attack_count.num_attacks == 2
    assert other_attack_count.num_attacks == 1
    assert any("Plasma Accelerator Rifle +1A" in str(entry) for entry in selected_attack_count.special_modifiers)
    assert not any("Plasma Accelerator Rifle +1A" in str(entry) for entry in other_attack_count.special_modifiers)

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = plasma_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        allow_rerolls=False,
    )
    assert any("Plasma Accelerator Rifle +1D" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Plasma Accelerator Rifle +1D" in str(entry) for entry in other_damage.get("special_effects", []))


def test_plasma_accelerator_rifle_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("Plasma Rifle")
    second_profile, second_wargear = make_named_ranged_profile("Plasma Rifle")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _plasma_accelerator_rifle_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_plasma_accelerator_rifle", False))
    assert int(unit.special_rules.get("enhancement_plasma_accelerator_rifle_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    first_attack_count = first_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    second_attack_count = second_profile.preview_attack_count(target, attacker, publish_roll_event=False)

    assert first_profile.get_effective_ap(attacker, target) == -1
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert first_attack_count.num_attacks == 2
    assert second_attack_count.num_attacks == 1
    assert any("Plasma Accelerator Rifle +1A" in str(entry) for entry in first_attack_count.special_modifiers)
    assert not any("Plasma Accelerator Rifle +1A" in str(entry) for entry in second_attack_count.special_modifiers)
    assert any(
        "Plasma Accelerator Rifle" in str(entry) and "+2S" in str(entry)
        for entry in first_wound.get("modifiers", [])
    )
    assert not any("Plasma Accelerator Rifle" in str(entry) for entry in second_wound.get("modifiers", []))


def test_fusion_blades_has_tool_descriptor():
    desc = get_enhancement_tool_descriptor(enhancement_id="000009983005")
    assert desc is not None
    assert desc.name == "Fusion Blades"
    assert desc.effect == "selected_ranged_weapon_strength_ap_damage_bonus"
    assert desc.effect_params.get("weapon_name") == "fusion blaster"
    assert int(desc.effect_params.get("attacks_bonus", 0) or 0) == 1
    assert int(desc.effect_params.get("strength_bonus", 0) or 0) == 3
    assert int(desc.effect_params.get("melta_bonus", 0) or 0) == 4


def test_fusion_blades_buffs_selected_fusion_blaster_only():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    fusion_profile, fusion_wargear = make_named_ranged_profile("Fusion Blaster")
    burst_profile, burst_wargear = make_named_ranged_profile("Burst Cannon")
    attacker.wargear.extend([fusion_wargear, burst_wargear])

    enhancement = _fusion_blades_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    fusion_wound = fusion_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    burst_wound = burst_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert fusion_profile.get_effective_ap(attacker, target) == 0
    assert burst_profile.get_effective_ap(attacker, target) == 0
    assert any("Fusion Blades" in str(entry) and "+3S" in str(entry) for entry in fusion_wound.get("modifiers", []))
    assert not any("Fusion Blades" in str(entry) for entry in burst_wound.get("modifiers", []))

    selected_attack_count = fusion_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    other_attack_count = burst_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    assert selected_attack_count.num_attacks == 2
    assert other_attack_count.num_attacks == 1
    assert any("Fusion Blades +1A" in str(entry) for entry in selected_attack_count.special_modifiers)
    assert not any("Fusion Blades +1A" in str(entry) for entry in other_attack_count.special_modifiers)

    selected_damage_target = create_unit(
        "Selected Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_damage_target = create_unit(
        "Other Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    selected_damage = fusion_profile._damage_target_with_tracking(
        selected_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub(), "below_half_distance": True},
        allow_rerolls=False,
    )
    other_damage = burst_profile._damage_target_with_tracking(
        other_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub(), "below_half_distance": True},
        allow_rerolls=False,
    )
    assert any("Fusion Blades [MELTA 4]" in str(entry) for entry in selected_damage.get("special_effects", []))
    assert not any("Fusion Blades [MELTA 4]" in str(entry) for entry in other_damage.get("special_effects", []))


def test_fusion_blades_selects_single_matching_weapon_instance():
    army = _build_tau_army("Experimental Prototype Cadre")
    unit = create_unit(
        "Commander",
        keywords=["BATTLESUIT", "CHARACTER"],
        faction_keywords=["T'AU EMPIRE"],
    )
    army.add_unit(unit)
    attacker = unit.models[0]

    first_profile, first_wargear = make_named_ranged_profile("Fusion Blaster")
    second_profile, second_wargear = make_named_ranged_profile("Fusion Blaster")
    attacker.wargear.extend([first_wargear, second_wargear])

    enhancement = _fusion_blades_enhancement()
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert bool(unit.special_rules.get("enhancement_fusion_blades", False))
    assert int(unit.special_rules.get("enhancement_fusion_blades_weapon_slot_index", -1)) == 0

    target = create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_wound = first_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    second_wound = second_profile._wound_target_with_tracking(
        target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    first_attack_count = first_profile.preview_attack_count(target, attacker, publish_roll_event=False)
    second_attack_count = second_profile.preview_attack_count(target, attacker, publish_roll_event=False)

    assert first_profile.get_effective_ap(attacker, target) == 0
    assert second_profile.get_effective_ap(attacker, target) == 0
    assert first_attack_count.num_attacks == 2
    assert second_attack_count.num_attacks == 1
    assert any("Fusion Blades +1A" in str(entry) for entry in first_attack_count.special_modifiers)
    assert not any("Fusion Blades +1A" in str(entry) for entry in second_attack_count.special_modifiers)
    assert any("Fusion Blades" in str(entry) and "+3S" in str(entry) for entry in first_wound.get("modifiers", []))
    assert not any("Fusion Blades" in str(entry) for entry in second_wound.get("modifiers", []))

    first_damage_target = create_unit(
        "First Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    second_damage_target = create_unit(
        "Second Damage Target",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    first_damage = first_profile._damage_target_with_tracking(
        first_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub(), "below_half_distance": True},
        allow_rerolls=False,
    )
    second_damage = second_profile._damage_target_with_tracking(
        second_damage_target.models[0],
        attacker,
        {"_aura_attack_mods": _aura_stub(), "below_half_distance": True},
        allow_rerolls=False,
    )
    assert any("Fusion Blades [MELTA 4]" in str(entry) for entry in first_damage.get("special_effects", []))
    assert not any("Fusion Blades [MELTA 4]" in str(entry) for entry in second_damage.get("special_effects", []))
