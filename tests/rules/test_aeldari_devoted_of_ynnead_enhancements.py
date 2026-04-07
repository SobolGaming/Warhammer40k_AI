from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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


def _build_game():
    army = Army.with_detachment("Aeldari", detachment_type="Devoted of Ynnead")
    army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
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
        detachment="Devoted of Ynnead",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def test_devoted_of_ynnead_enhancements_have_tool_descriptors():
    expected = {
        "000009919002": ("Gaze of Ynnead", "grant_weapon_keywords"),
        "000009919003": ("Storm of Whispers", "post_shoot_battleshock_test"),
        "000009919004": ("Borrowed Vigour", "bearer_melee_attacks_bonus"),
        "000009919005": ("Morbid Might", "bearer_melee_wound_reroll"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_gaze_of_ynnead_grants_devastating_wounds_only_to_eldritch_storm():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Farseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(bearer, enh_id="000009919002", name="Gaze of Ynnead")

    model = bearer.models[0]
    eldritch = bearer.get_model_weapon_keyword_bonuses(
        model=model,
        weapon_name="Eldritch Storm",
        attack_type="ranged",
    )
    other = bearer.get_model_weapon_keyword_bonuses(
        model=model,
        weapon_name="Shuriken Pistol",
        attack_type="ranged",
    )

    assert bool(eldritch.get("devastating_wounds")) is True
    assert bool(other.get("devastating_wounds")) is False


def test_storm_of_whispers_queues_post_shoot_battleshock_target_decision():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    bearer = _make_unit(
        "Warlock",
        army,
        keywords=["CHARACTER", "INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    _attach_enhancement(bearer, enh_id="000009919003", name="Storm of Whispers")
    enemy = _make_unit(
        "Enemy Unit",
        enemy_army,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    game.map.units = [bearer, enemy]
    game.rebuild_entity_registry()

    bearer_model = bearer.models[0]
    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=bearer,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: [bearer_model]},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
    assert str((request.context or {}).get("ability_name", "") or "") == "Storm of Whispers"

    chosen = request.options[0]
    result = resolve_decision_command(game, request, chosen.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))


def test_borrowed_vigour_adds_two_bearer_melee_attacks():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Archon",
        army,
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["AELDARI", "DRUKHARI"],
    )
    _attach_enhancement(bearer, enh_id="000009919004", name="Borrowed Vigour")

    sr = dict(getattr(bearer, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_borrowed_vigour"))
    assert int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 2


def test_morbid_might_grants_bearer_melee_wound_rerolls():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Succubus",
        army,
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["AELDARI", "DRUKHARI", "WYCH CULT"],
    )
    _attach_enhancement(bearer, enh_id="000009919005", name="Morbid Might")

    model = bearer.models[0]
    melee_mods = bearer.get_model_wound_reroll_modifiers(model=model, attack_type="melee")
    ranged_mods = bearer.get_model_wound_reroll_modifiers(model=model, attack_type="ranged")

    assert bool(melee_mods.get("reroll_wound_full")) is True
    assert any("morbid might" in str(reason).lower() for reason in list(melee_mods.get("reroll_wound_full_reasons", ()) or ()))
    assert bool(ranged_mods.get("reroll_wound_full")) is False
