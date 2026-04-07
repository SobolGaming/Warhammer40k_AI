from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    spirit_army = Army.with_detachment("Aeldari", "Spirit Conclave")
    spirit_army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "SM"
    spirit_player = Player("Aeldari", control=PlayerControl.REMOTE, army=spirit_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[spirit_player, enemy_player])
    return game, spirit_army, enemy_army


def test_spirit_conclave_wraithblades_and_wraithguard_gain_battleline():
    _game, spirit_army, _enemy_army = _build_game()
    wraithblades = _make_unit(
        "Wraithblades",
        keywords=["INFANTRY", "WRAITHBLADES", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    wraithguard = _make_unit(
        "Wraithguard",
        keywords=["INFANTRY", "WRAITHGUARD", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    wraithlord = _make_unit(
        "Wraithlord",
        keywords=["MONSTER", "WRAITHLORD", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    spirit_army.add_unit(wraithblades)
    spirit_army.add_unit(wraithguard)
    spirit_army.add_unit(wraithlord)

    assert wraithblades.is_battleline
    assert wraithguard.is_battleline
    assert not wraithlord.is_battleline


def test_shepherds_of_the_dead_assigns_vengeful_dead_token_on_destroyed_asuryani_psyker_model():
    game, spirit_army, enemy_army = _build_game()
    psyker = _make_unit(
        "Spiritseer",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    spirit_army.add_unit(psyker)
    enemy_army.add_unit(enemy)
    game.map.units = [psyker, enemy]
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=enemy.models[0],
        attacker_unit=enemy,
        target_model=psyker.models[0],
        target_unit=psyker,
        weapon_profile=None,
        is_mortal=False,
        game_map=game.map,
    )

    mgr = spirit_army.aeldari_detachments
    assert int(mgr.spirit_conclave_vengeful_dead_tokens(enemy) or 0) == 1


def test_shepherds_of_the_dead_does_not_assign_token_for_non_psyker_model():
    game, spirit_army, enemy_army = _build_game()
    non_psyker = _make_unit(
        "Guardian Defenders",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    spirit_army.add_unit(non_psyker)
    enemy_army.add_unit(enemy)
    game.map.units = [non_psyker, enemy]
    game.rebuild_entity_registry()

    game.event_system.publish(
        "model_destroyed",
        attacker_model=enemy.models[0],
        attacker_unit=enemy,
        target_model=non_psyker.models[0],
        target_unit=non_psyker,
        weapon_profile=None,
        is_mortal=False,
        game_map=game.map,
    )

    mgr = spirit_army.aeldari_detachments
    assert int(mgr.spirit_conclave_vengeful_dead_tokens(enemy) or 0) == 0


def test_shepherds_of_the_dead_grants_hit_and_wound_bonus_for_wraith_construct_vs_tokened_unit():
    _game, spirit_army, enemy_army = _build_game()
    wraithguard = _make_unit(
        "Wraithguard",
        keywords=["INFANTRY", "WRAITHGUARD", "WRAITH CONSTRUCT"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    guardians = _make_unit(
        "Guardian Defenders",
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    spirit_army.add_unit(wraithguard)
    spirit_army.add_unit(guardians)
    enemy_army.add_unit(enemy)

    mgr = spirit_army.aeldari_detachments
    mgr.spirit_conclave_add_vengeful_dead_tokens(enemy, count=1)

    hit_bonus, _ = mgr.shepherds_of_the_dead_hit_bonus(wraithguard.models[0], wraithguard, enemy)
    wound_bonus, _ = mgr.shepherds_of_the_dead_wound_bonus(wraithguard.models[0], wraithguard, enemy)
    non_wraith_hit, _ = mgr.shepherds_of_the_dead_hit_bonus(guardians.models[0], guardians, enemy)

    assert int(hit_bonus) == 1
    assert int(wound_bonus) == 1
    assert int(non_wraith_hit) == 0


def test_spirit_guides_grants_battle_focus_to_nearby_wraith_targets():
    _game, spirit_army, _enemy_army = _build_game()
    psyker = _make_unit(
        "Farseer",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    wraithlord = _make_unit(
        "Wraithlord",
        keywords=["MONSTER", "WRAITHLORD"],
        faction_keywords=["AELDARI"],
    )
    spirit_army.add_unit(psyker)
    spirit_army.add_unit(wraithlord)

    _set_unit_location(psyker, x=0.0, y=0.0)
    _set_unit_location(wraithlord, x=10.0, y=0.0)
    assert spirit_army.aeldari_detachments.spirit_guides_battle_focus_applies(wraithlord)
    assert spirit_army.battle_focus._unit_has_battle_focus(wraithlord)

    _set_unit_location(wraithlord, x=20.0, y=0.0)
    assert not spirit_army.aeldari_detachments.spirit_guides_battle_focus_applies(wraithlord)
