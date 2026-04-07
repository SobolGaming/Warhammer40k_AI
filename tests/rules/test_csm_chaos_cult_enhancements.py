from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 2,
        model_count: int = 1,
        attached_to=None,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 2,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            model_count=model_count,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_melee_profile(*, strength: int = 4, ap: int = 0) -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Blade",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _apply_enhancement(unit: Unit, *, enh_id: str, name: str, description: str) -> None:
    enh = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="CSM",
        detachment="Chaos Cult",
        points=0,
        description=description,
    )
    unit.enhancement = enh
    enh.apply_to_unit(unit)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Chaos Space Marines", "Chaos Cult")
    army1.faction_id = "CSM"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _find_bodyguard_return_request(game: Game, *, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_ALLOCATE_DAMAGE:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") != "bodyguard_return":
            continue
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


def test_chaos_cult_enhancement_descriptors_registered():
    expected = {
        "000008981002": "Amulet of Tainted Vigour",
        "000008981003": "Cultist's Brand",
        "000008981004": "Incendiary Goad",
        "000008981005": "Warped Foresight",
    }
    for enhancement_id, enhancement_name in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == enhancement_name


def test_cultists_brand_requires_other_models_to_be_damned_excluding_dark_disciples():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Chaos Cult")
    army.faction_id = "CSM"

    bodyguard = _make_unit(
        "Accursed Cultists",
        datasheet_id="chaos_cult_bg_1",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    leader = _make_unit(
        "Dark Apostle",
        datasheet_id="chaos_cult_leader_1",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
        attached_to=["chaos_cult_bg_1"],
    )
    leader.models[1].name = "Dark Disciple"
    leader.models[2].name = "Dark Disciple"

    army.add_unit(bodyguard)
    army.add_unit(leader)
    leader.attach_to_unit(bodyguard)

    _apply_enhancement(
        leader,
        enh_id="000008981003",
        name="Cultist's Brand",
        description=(
            "DARK APOSTLE or DAMNED model only. If every other model in the bearer's unit "
            "(excluding Dark Disciples) is DAMNED, you can re-roll Advance and Charge rolls made "
            "for the bearer's unit."
        ),
    )

    mgr = army.chaos_space_marines_detachments
    assert bool(mgr.chaos_cult_cultists_brand_reroll_advance_applies(bodyguard)) is True
    assert bool(mgr.chaos_cult_cultists_brand_reroll_charge_applies(bodyguard)) is True

    bodyguard.models[0].keywords = ["INFANTRY"]
    assert bool(mgr.chaos_cult_cultists_brand_reroll_advance_applies(bodyguard)) is False
    assert bool(mgr.chaos_cult_cultists_brand_reroll_charge_applies(bodyguard)) is False


def test_incendiary_goad_applies_to_damned_models_with_correct_thresholds():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Chaos Cult")
    army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    bodyguard = _make_unit(
        "Accursed Cultists",
        datasheet_id="chaos_cult_bg_2",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=4,
    )
    leader = _make_unit(
        "Dark Apostle",
        datasheet_id="chaos_cult_leader_2",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
        attached_to=["chaos_cult_bg_2"],
    )
    leader.models[1].name = "Dark Disciple"
    leader.models[2].name = "Dark Disciple"
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )

    army.add_unit(bodyguard)
    army.add_unit(leader)
    enemy_army.add_unit(target)
    leader.attach_to_unit(bodyguard)

    _apply_enhancement(
        leader,
        enh_id="000008981004",
        name="Incendiary Goad",
        description=(
            "DARK APOSTLE or DAMNED model only. While the bearer's unit is below its Starting Strength, "
            "add 1 to the Strength characteristic of melee weapons equipped by DAMNED models in that unit, "
            "and while that unit is Below Half-strength, add 1 to the Attacks characteristic of those "
            "weapons as well."
        ),
    )

    mgr = army.chaos_space_marines_detachments
    profile = _make_melee_profile(strength=4, ap=0)
    damned_model = bodyguard.models[0]
    bearer_model = leader.models[0]

    s_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_strength_bonus(damned_model, weapon_profile=profile)
    a_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_attacks_bonus(damned_model, weapon_profile=profile)
    assert int(s_bonus) == 0
    assert int(a_bonus) == 0

    bodyguard.remove_model(bodyguard.models[-1])
    s_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_strength_bonus(damned_model, weapon_profile=profile)
    a_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_attacks_bonus(damned_model, weapon_profile=profile)
    assert int(s_bonus) == 1
    assert int(a_bonus) == 0

    bearer_s_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_strength_bonus(bearer_model, weapon_profile=profile)
    assert int(bearer_s_bonus) == 0

    wound_damned = profile._wound_target_with_tracking(
        target,
        damned_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(wound_damned["needed"]) == 4

    wound_bearer = profile._wound_target_with_tracking(
        target,
        bearer_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(wound_bearer["needed"]) == 5

    bodyguard.remove_model(bodyguard.models[1])
    bodyguard.remove_model(bodyguard.models[1])
    leader.remove_model(leader.models[-1])
    a_bonus, _source = mgr.chaos_cult_incendiary_goad_melee_attacks_bonus(damned_model, weapon_profile=profile)
    assert int(a_bonus) == 1


def test_warped_foresight_grants_scouts_while_bearer_leads_unit_with_scouts():
    army = Army.with_detachment("Chaos Space Marines", detachment_type="Chaos Cult")
    army.faction_id = "CSM"

    bodyguard = _make_unit(
        "Cultist Mob",
        datasheet_id="chaos_cult_bg_3",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    bodyguard.possible_abilities.append('Scouts 6"')
    leader = _make_unit(
        "Dark Apostle",
        datasheet_id="chaos_cult_leader_3",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
        attached_to=["chaos_cult_bg_3"],
    )
    leader.models[1].name = "Dark Disciple"
    leader.models[2].name = "Dark Disciple"

    army.add_unit(bodyguard)
    army.add_unit(leader)
    leader.attach_to_unit(bodyguard)

    leader_has_scout, _leader_distance = leader.has_scout()
    assert leader_has_scout is False

    _apply_enhancement(
        leader,
        enh_id="000008981005",
        name="Warped Foresight",
        description=(
            "DARK APOSTLE or DAMNED model only. While the bearer is leading a unit with the Scouts 6\" ability, "
            "every model in the bearer's unit has the Scouts 6\" ability."
        ),
    )

    leader_has_scout, leader_distance = leader.has_scout()
    assert leader_has_scout is True
    assert float(leader_distance) == 6.0

    leader.detach_from_unit()
    leader_has_scout, _leader_distance = leader.has_scout()
    assert leader_has_scout is False


def test_amulet_of_tainted_vigour_queues_filtered_command_phase_return(monkeypatch):
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    bodyguard = _make_unit(
        "Accursed Cultists",
        datasheet_id="chaos_cult_bg_4",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
    )
    leader = _make_unit(
        "Dark Apostle",
        datasheet_id="chaos_cult_leader_4",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
        attached_to=["chaos_cult_bg_4"],
    )
    leader.models[1].name = "Dark Disciple"
    leader.models[2].name = "Dark Disciple"
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    army.add_unit(bodyguard)
    army.add_unit(leader)
    enemy_army.add_unit(enemy)
    leader.attach_to_unit(bodyguard)

    valid_model = bodyguard.models[0]
    valid_model_id = str(get_entity_id(valid_model) or "")
    bodyguard.remove_model(valid_model)

    invalid_model = bodyguard.models[0]
    invalid_model.keywords = ["INFANTRY"]
    bodyguard.remove_model(invalid_model)

    _apply_enhancement(
        leader,
        enh_id="000008981002",
        name="Amulet of Tainted Vigour",
        description=(
            "DARK APOSTLE model only. In your Command phase, you can return up to D3 destroyed DAMNED models "
            "(excluding CHARACTER models) to the bearer's unit."
        ),
    )

    game.map.units = [bodyguard, leader, enemy]
    game.rebuild_entity_registry()

    monkeypatch.setattr("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", lambda _expr: 3)
    game._on_phase_start_optional_abilities(player=player, phase=game.phase)

    request = _find_bodyguard_return_request(game, ability_name="Amulet of Tainted Vigour")
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert list(ctx.get("allowed_model_ids", []) or []) == [valid_model_id]

    option_model_ids = []
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        mid = payload.get("model_id")
        if mid not in (None, ""):
            option_model_ids.append(str(mid))
    assert option_model_ids == [valid_model_id]
