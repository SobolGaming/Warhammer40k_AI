from __future__ import annotations

from .adeptus_custodes_detachments import AdeptusCustodesDetachmentManager
from .adepta_sororitas_detachments import AdeptaSororitasDetachmentManager
from .adeptus_mechanicus_detachments import AdeptusMechanicusDetachmentManager
from .aeldari_detachments import AeldariDetachmentManager
from .astra_militarum_detachments import AstraMilitarumDetachmentManager
from .chaos_daemons_detachments import ChaosDaemonsDetachmentManager
from .chaos_knights_detachments import ChaosKnightsDetachmentManager
from .chaos_space_marines_detachments import ChaosSpaceMarinesDetachmentManager
from .death_guard_detachments import DeathGuardDetachmentManager
from .drukhari_detachments import DrukhariDetachmentManager
from .genestealer_cults_detachments import GenestealerCultsDetachmentManager
from .grey_knights_detachments import GreyKnightsDetachmentManager
from .imperial_agents_detachments import ImperialAgentsDetachmentManager
from .imperial_knights_detachments import ImperialKnightsDetachmentManager
from .leagues_of_votann_detachments import LeaguesOfVotannDetachmentManager
from .necrons_detachments import NecronsDetachmentManager
from .orks_detachments import OrksDetachmentManager
from .space_marines_detachments import SpaceMarinesDetachmentManager
from .tau_empire_detachments import TauEmpireDetachmentManager
from .thousand_sons_detachments import ThousandSonsDetachmentManager
from .tyranids_detachments import TyranidsDetachmentManager
from .world_eaters_detachments import WorldEatersDetachmentManager


DETACHMENT_MANAGER_CLASSES = {
    "adeptus_custodes_detachments": AdeptusCustodesDetachmentManager,
    "adepta_sororitas_detachments": AdeptaSororitasDetachmentManager,
    "adeptus_mechanicus_detachments": AdeptusMechanicusDetachmentManager,
    "aeldari_detachments": AeldariDetachmentManager,
    "astra_militarum_detachments": AstraMilitarumDetachmentManager,
    "chaos_daemons_detachments": ChaosDaemonsDetachmentManager,
    "chaos_knights_detachments": ChaosKnightsDetachmentManager,
    "chaos_space_marines_detachments": ChaosSpaceMarinesDetachmentManager,
    "death_guard_detachments": DeathGuardDetachmentManager,
    "drukhari_detachments": DrukhariDetachmentManager,
    "genestealer_cults_detachments": GenestealerCultsDetachmentManager,
    "grey_knights_detachments": GreyKnightsDetachmentManager,
    "imperial_agents_detachments": ImperialAgentsDetachmentManager,
    "imperial_knights_detachments": ImperialKnightsDetachmentManager,
    "leagues_of_votann_detachments": LeaguesOfVotannDetachmentManager,
    "necrons_detachments": NecronsDetachmentManager,
    "orks_detachments": OrksDetachmentManager,
    "space_marines_detachments": SpaceMarinesDetachmentManager,
    "tau_empire_detachments": TauEmpireDetachmentManager,
    "thousand_sons_detachments": ThousandSonsDetachmentManager,
    "tyranids_detachments": TyranidsDetachmentManager,
    "world_eaters_detachments": WorldEatersDetachmentManager,
}

DETACHMENT_MANAGER_BY_FACTION_ID = {
    getattr(cls, "faction_id", ""): attr
    for attr, cls in DETACHMENT_MANAGER_CLASSES.items()
    if getattr(cls, "faction_id", "")
}
DETACHMENT_MANAGER_BY_FACTION_ID["EC"] = "emperors_children_detachments"
