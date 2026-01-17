from enum import Enum


class SetupPhase(Enum):
    """
    The phases of the setup phase.
    """
    MUSTER_ARMIES = 0
    SELECT_MISSION_OBJECTIVES = 1
    CREATE_BATTLEFIELD = 2  # Place terrain, objectives, etc.
    DETERMINE_ATTACKER_AND_DEFENDER = 3
    DECLARE_BATTLE_FORMATIONS = 4  # Attach leaders to units; declare reserves; declare embarked units.
    DEPLOY_ARMIES = 5
    REDEPLOY_UNITS = 6
    DETERMINE_FIRST_TURN_ORDER = 7
    RESOLVE_PREBATTLE_RULES = 8  # Resolve any pre-battle rules, abilities, or stratagems.


class BattleRoundPhases(Enum):
    """
    The phases of a battle round.
    """
    COMMAND_PHASE = 0
    MOVEMENT_PHASE = 1
    SHOOTING_PHASE = 2
    CHARGE_PHASE = 3
    FIGHT_PHASE = 4
