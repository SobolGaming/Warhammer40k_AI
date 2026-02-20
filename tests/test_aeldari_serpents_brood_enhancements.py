from __future__ import annotations

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_CRUEL_AMUSEMENT, DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "4",
                "W": "3",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    army: Army,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    army.add_unit(unit)
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    army = Army("Aeldari", detachment_type="Serpent's Brood")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    player = Player("Aeldari", control=PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.current_player_index = 0
    return game, army, enemy_army, player, enemy_player


def _attach_enhancement(unit: Unit, *, enh_id: str, name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=enh_id,
        name=name,
        faction_id="AE",
        detachment="Serpent's Brood",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def test_serpents_brood_enhancements_have_tool_descriptors():
    expected = {
        "000010649002": ("Key of Ghosts", "grant_scouts_to_bearer_unit"),
        "000010649003": ("Weavers' Wail", "bearer_melee_strength_attacks_bonus"),
        "000010649004": ("Fanged Leer", "cruel_amusement_select_two_abilities"),
        "000010649005": ("Shedskin Raiment", "redeploy_units"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_key_of_ghosts_grants_scouts_six_to_bearer_unit():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Death Jester",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    _attach_enhancement(bearer, enh_id="000010649002", name="Key of Ghosts")

    has_scout, scout_distance = bearer.has_scout()
    assert has_scout is True
    assert float(scout_distance) == 6.0


def test_weavers_wail_adds_bearer_melee_strength_and_attacks():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Troupe Master",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    _attach_enhancement(bearer, enh_id="000010649003", name="Weavers' Wail")

    sr = dict(getattr(bearer, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_weavers_wail"))
    assert int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0) == 3
    assert int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 1
    assert str(sr.get("enhancement_bearer_model_id", "") or "")


def test_fanged_leer_allows_selecting_two_cruel_amusement_abilities():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    cruel_amusement_text = (
        "In your Shooting phase, each time this model is selected to shoot, select one of the abilities below. "
        "Until the end of the phase, this model's shrieker cannon has that ability."
    )
    bearer = _make_unit(
        "Death Jester",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
        abilities=[
            {
                "name": "Cruel Amusement",
                "description": cruel_amusement_text,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    _attach_enhancement(bearer, enh_id="000010649004", name="Fanged Leer")
    enemy = _make_unit(
        "Enemy Unit",
        enemy_army,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    game.map.units = [bearer, enemy]
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_cruel_amusement(attacking_unit=bearer, target_units=[enemy])
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_CRUEL_AMUSEMENT

    pair_option = next(
        opt
        for opt in list(request.options or [])
        if isinstance((opt.payload or {}).get("choices"), list)
        and len(list((opt.payload or {}).get("choices") or [])) == 2
        and set(list((opt.payload or {}).get("choices") or [])) == {"IGNORES_COVER", "PRECISION"}
    )
    result = resolve_decision_command(game, request, pair_option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))

    bonuses = bearer.get_model_weapon_keyword_bonuses(
        model=bearer.models[0],
        weapon_name="shrieker cannon",
        attack_type="ranged",
    )
    assert bool(bonuses.get("ignores_cover")) is True
    assert bool(bonuses.get("precision")) is True


def test_cruel_amusement_rejects_two_choices_without_fanged_leer():
    game, army, _enemy_army, player, _enemy_player = _build_game()

    cruel_amusement_text = (
        "In your Shooting phase, each time this model is selected to shoot, select one of the abilities below. "
        "Until the end of the phase, this model's shrieker cannon has that ability."
    )
    unit = _make_unit(
        "Death Jester",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
        abilities=[
            {
                "name": "Cruel Amusement",
                "description": cruel_amusement_text,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    game.map.units = [unit]
    game.rebuild_entity_registry()

    model = unit.models[0]
    request = DecisionRequest.create(
        DECISION_CHOOSE_CRUEL_AMUSEMENT,
        "Cruel Amusement: select a weapon ability.",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Ignores Cover + Precision",
                payload={"choices": ["IGNORES_COVER", "PRECISION"]},
            )
        ],
        context={
            "model_id": str(get_entity_id(model) or ""),
            "weapon_name": "shrieker cannon",
            "ability_name": "Cruel Amusement",
        },
    )
    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=str(request.options[0].option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)

    assert apply_result.ok is False
    assert any("fanged leer" in str(err).lower() for err in list(apply_result.errors or []))


def test_shedskin_raiment_redeploy_filters_to_harlequins_units():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.auto_resolve_dice_rolls = False
    game.attacker_index = 0
    game.defender_index = 1

    description = (
        "Shadowseer model only. After both players have deployed their armies, select up to three Harlequins units "
        "from your army and redeploy them. When doing so, you can set those units up in Strategic Reserves, "
        "regardless of how many units are already in Strategic Reserves."
    )
    bearer = _make_unit(
        "Shadowseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    _attach_enhancement(
        bearer,
        enh_id="000010649005",
        name="Shedskin Raiment",
        description=description,
    )
    harlequin_a = _make_unit(
        "Troupe",
        army,
        keywords=["INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    harlequin_b = _make_unit(
        "Skyweavers",
        army,
        keywords=["MOUNTED", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    non_harlequin = _make_unit(
        "Guardian Defenders",
        army,
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        enemy_army,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    _set_unit_location(bearer, x=0.0, y=0.0)
    _set_unit_location(harlequin_a, x=4.0, y=0.0)
    _set_unit_location(harlequin_b, x=6.0, y=0.0)
    _set_unit_location(non_harlequin, x=8.0, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)

    game.map.units = [bearer, harlequin_a, harlequin_b, non_harlequin, enemy]
    game.rebuild_entity_registry()

    game.execute_redeploy_units_phase()
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability_name", "") or "") == "Shedskin Raiment"

    target_ids = {
        str((opt.payload or {}).get("target_unit_id", "") or "")
        for opt in list(request.options or [])
    }
    harlequin_a_id = str(get_entity_id(harlequin_a) or "")
    harlequin_b_id = str(get_entity_id(harlequin_b) or "")
    non_harlequin_id = str(get_entity_id(non_harlequin) or "")

    assert harlequin_a_id in target_ids
    assert harlequin_b_id in target_ids
    assert non_harlequin_id not in target_ids
    assert any(
        str((opt.payload or {}).get("target_unit_id", "") or "") == harlequin_a_id
        and str((opt.payload or {}).get("redeploy_action", "") or "").lower() == "strategic_reserves"
        for opt in list(request.options or [])
    )
