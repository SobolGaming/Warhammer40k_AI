from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class ChaosSpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "CSM"

    DETACHMENT_CABAL_OF_CHAOS = "Cabal of Chaos"

    def is_cabal_of_chaos(self) -> bool:
        return self.detachment_matches(self.DETACHMENT_CABAL_OF_CHAOS)
