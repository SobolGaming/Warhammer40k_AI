import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


REPO_ROOT = Path(__file__).resolve().parents[2]


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "6",
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
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()


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
    )


FOR_THE_KHAN_TEXT = (
    "While this model is leading a unit, ranged weapons equipped by models in that unit have the [ASSAULT] "
    "ability and melee weapons equipped by models in that unit have the [LANCE] ability."
)


def test_for_the_khan_parses_ranged_assault_and_melee_lance_as_separate_clauses():
    leader = _make_unit(
        "Kor'sarro Khan",
        abilities=[_ability("For the Khan!", FOR_THE_KHAN_TEXT)],
        keywords=["CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Assault Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    _attach_leader(bodyguard, leader)

    model = bodyguard.models[0]
    rules = list(bodyguard._get_attack_keyword_bonus_rules(model=model) or [])
    summary = {(str(rule.get("attack_type") or ""), str(rule.get("keyword") or "")) for rule in rules}
    target = SimpleNamespace(
        toughness=4,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        has_any_keyword=lambda _k: False,
        is_vehicle=False,
        is_monster=False,
    )

    assert ("ranged", "ASSAULT") in summary
    assert ("melee", "LANCE") in summary

    melee_bonus = bodyguard.get_attack_keyword_bonuses(target=target, attack_type="melee", model=model)
    assert bool(melee_bonus.get("lance")) is True
    assert any("For the Khan!" in str(source) for source in list(melee_bonus.get("sources", ()) or ()))


def test_for_the_khan_lance_improves_melee_wound_rolls_after_a_charge():
    leader = _make_unit(
        "Kor'sarro Khan",
        abilities=[_ability("For the Khan!", FOR_THE_KHAN_TEXT)],
        keywords=["CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bodyguard = _make_unit(
        "Assault Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    _attach_leader(bodyguard, leader)
    bodyguard.round_state.charged_this_round = True

    attacker = bodyguard.models[0]
    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
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
        parent_wargear=parent,
    )
    target = SimpleNamespace(
        toughness=4,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        has_any_keyword=lambda _k: False,
        is_vehicle=False,
        is_monster=False,
    )
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 3]):
        profile._hit_target_with_tracking(target, attacker, attack_instance)
        wound_result = profile._wound_target_with_tracking(target, attacker, attack_instance)

    assert wound_result.get("wound") is True
    assert bool(attack_instance.get("bonus_lance")) is True
    assert int(wound_result.get("final_needed", 0) or 0) == 3
    assert any("Lance" in str(modifier) for modifier in list(wound_result.get("modifiers", ()) or ()))


def test_korsarro_khan_leader_targets_match_latest_space_marines_errata():
    datasheets = json.loads((REPO_ROOT / "wahapedia_data" / "Datasheets.json").read_text())
    leader_links = json.loads((REPO_ROOT / "wahapedia_data" / "Datasheets_leader.json").read_text())
    name_by_id = {str(row.get("id") or ""): str(row.get("name") or "") for row in datasheets}

    actual_names = {
        name_by_id.get(str(row.get("attached_id") or ""), "")
        for row in leader_links
        if str(row.get("leader_id") or "") == "000002709"
    }
    actual_names.discard("")

    assert actual_names == {
        "Assault Intercessor Squad",
        "Assault Squad",
        "Bladeguard Veteran Squad",
        "Command Squad",
        "Company Heroes",
        "Crusader Squad",
        "Crusader Squad (Legendary)",
        "Deathwatch Veterans",
        "Decimus Kill Team",
        "Fortis Kill Team",
        "Inner Circle Companions",
        "Intercessor Squad",
        "Sternguard Veteran Squad",
        "Sword Brethren Squad",
        "Tactical Squad",
        "Vanguard Veteran Squad",
        "Victrix Honour Guard",
        "Wolf Guard",
    }
