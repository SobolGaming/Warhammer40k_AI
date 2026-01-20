from __future__ import annotations

from typing import Iterable, List, Dict


APPROVED_MISSION_COMBINATIONS: List[Dict] = [
    # A-D: Tipping Point missions
    {"id": "A", "primary": "Take and Hold", "deployment": "Tipping Point", "layouts": [1, 2, 4, 6, 7, 8]},
    {"id": "B", "primary": "Supply Drop", "deployment": "Tipping Point", "layouts": [1, 2, 4, 6, 7, 8]},
    {"id": "C", "primary": "Linchpin", "deployment": "Tipping Point", "layouts": [1, 2, 4, 6, 7, 8]},
    {"id": "D", "primary": "Scorched Earth", "deployment": "Tipping Point", "layouts": [1, 2, 4, 6, 7, 8]},
    # E-H: Hammer and Anvil missions
    {"id": "E", "primary": "Take and Hold", "deployment": "Hammer and Anvil", "layouts": [1, 7, 8]},
    {"id": "F", "primary": "Hidden Supplies", "deployment": "Hammer and Anvil", "layouts": [1, 7, 8]},
    {"id": "G", "primary": "Purge the Foe", "deployment": "Hammer and Anvil", "layouts": [1, 7, 8]},
    {"id": "H", "primary": "Supply Drop", "deployment": "Hammer and Anvil", "layouts": [1, 7, 8]},
    # I-L: Search and Destroy missions
    {"id": "I", "primary": "Hidden Supplies", "deployment": "Search and Destroy", "layouts": [1, 2, 3, 4, 6]},
    {"id": "J", "primary": "Linchpin", "deployment": "Search and Destroy", "layouts": [1, 2, 3, 4, 6]},
    {"id": "K", "primary": "Scorched Earth", "deployment": "Search and Destroy", "layouts": [1, 2, 3, 4, 6]},
    {"id": "L", "primary": "Take and Hold", "deployment": "Search and Destroy", "layouts": [1, 2, 3, 4, 6]},
    # M-P: Crucible of Battle missions
    {"id": "M", "primary": "Purge the Foe", "deployment": "Crucible of Battle", "layouts": [1, 2, 3, 4, 6]},
    {"id": "N", "primary": "Hidden Supplies", "deployment": "Crucible of Battle", "layouts": [1, 2, 3, 4, 6]},
    {"id": "O", "primary": "Terraform", "deployment": "Crucible of Battle", "layouts": [1, 2, 3, 4, 6]},
    {"id": "P", "primary": "Scorched Earth", "deployment": "Crucible of Battle", "layouts": [1, 2, 3, 4, 6]},
    # Q-R: Sweeping Engagement missions
    {"id": "Q", "primary": "Supply Drop", "deployment": "Sweeping Engagement", "layouts": [3, 5]},
    {"id": "R", "primary": "Terraform", "deployment": "Sweeping Engagement", "layouts": [3, 5]},
    # S-T: Dawn of War missions
    {"id": "S", "primary": "Linchpin", "deployment": "Dawn of War", "layouts": [5]},
    {"id": "T", "primary": "Purge the Foe", "deployment": "Dawn of War", "layouts": [5]},
]


def iter_mission_combinations(combos: Iterable[dict] | None = None) -> List[Dict]:
    return [dict(c) for c in (combos or APPROVED_MISSION_COMBINATIONS)]
