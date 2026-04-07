from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
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
                "Sv": "3",
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    tau_army = Army.with_detachment("Tau", "Det")
    tau_army.faction_id = "TAU"
    enemy_army = Army.with_detachment("Enemy", "Det")
    enemy_army.faction_id = "EN"

    tau_player = Player("Tau", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    return game, tau_army, enemy_army, tau_player, enemy_player


def test_kroot_packmates_parses_reactive_shoot_rule():
    ability = {
        "name": "Kroot Packmates",
        "description": (
            "Once per turn, in your opponent's Shooting phase, when a friendly Kroot Infantry unit within 6\" of this unit "
            "is selected as the target of an attack, one unit from your army with this ability can use it. "
            "If it does, after that enemy unit has finished making its attacks, that unit with this ability can shoot as if it were "
            "your Shooting phase, but when resolving those attacks it can only target that enemy unit "
            "(and only if it is an eligible target)."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    riders = _make_unit(
        "Krootox Riders",
        abilities=[ability],
        keywords=["KROOT", "MOUNTED"],
        faction_keywords=["T'AU EMPIRE"],
    )

    rule = riders.get_guns_blazing_rule()
    assert rule is not None
    assert str((rule or {}).get("source", "") or "") == "Kroot Packmates"
    assert str((rule or {}).get("friendly_keyword", "") or "") == "KROOT INFANTRY"
    assert int((rule or {}).get("range", 0) or 0) == 6


def test_kroot_packmates_queues_reactive_shooting_decision():
    from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Kroot Packmates",
        "description": (
            "Once per turn, in your opponent's Shooting phase, when a friendly Kroot Infantry unit within 6\" of this unit "
            "is selected as the target of an attack, one unit from your army with this ability can use it. "
            "If it does, after that enemy unit has finished making its attacks, that unit with this ability can shoot as if it were "
            "your Shooting phase, but when resolving those attacks it can only target that enemy unit "
            "(and only if it is an eligible target)."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    game, tau_army, enemy_army, tau_player, _enemy_player = _build_game()
    enemy_attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"])
    friendly_target = _make_unit(
        "Kroot Carnivores",
        keywords=["KROOT", "INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    riders = _make_unit(
        "Krootox Riders",
        abilities=[ability],
        keywords=["KROOT", "MOUNTED"],
        faction_keywords=["T'AU EMPIRE"],
    )

    enemy_army.add_unit(enemy_attacker)
    tau_army.add_unit(friendly_target)
    tau_army.add_unit(riders)

    enemy_attacker.deployed = True
    friendly_target.deployed = True
    riders.deployed = True
    enemy_attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_target.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    riders.models[0].set_location(9.0, 0.0, 0.0, 0.0)
    game.map.units = [enemy_attacker, friendly_target, riders]
    game.current_player_index = 1
    game.rebuild_entity_registry()
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=enemy_attacker,
        target_units=[friendly_target],
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy_attacker,
        hits_by_target={friendly_target: 1},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_DECLARE_SHOTS
    assert bool((request.context or {}).get("guns_blazing_flow", False))
    assert str((request.context or {}).get("guns_blazing_source", "") or "") == "Kroot Packmates"
    assert request.player_id == tau_player.id
    assert str((request.context or {}).get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")
