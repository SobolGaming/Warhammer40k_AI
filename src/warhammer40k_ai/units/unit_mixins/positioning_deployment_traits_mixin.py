"""Deep strike, infiltrate, stealth, scout, and redeploy helpers for Unit deployment/runtime state."""

from ._common import *
import logging
logger = logging.getLogger(__name__)


class PositioningDeploymentTraitsMixin:
    def _root_has_attached_unit_deep_strike_grant(self) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        try:
            sr_root = getattr(root, "special_rules", None)
            if isinstance(sr_root, dict) and bool(sr_root.get("bearer_unit_deep_strike")):
                return True
        except Exception:
            pass
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = []
        if members:
            for member in members:
                if member is None:
                    continue
                sr_member = getattr(member, "special_rules", None)
                if isinstance(sr_member, dict) and bool(sr_member.get("bearer_unit_deep_strike")):
                    return True
        text_grant_re = re.compile(
            r"models\s+in\s+(?:this|that|the\s+bearer'?s|this\s+model'?s)\s+unit\s+have\s+the\s+deep\s+strike\b",
            re.IGNORECASE,
        )
        abilities = list(getattr(root, "possible_abilities", []) or []) + list(getattr(root, "abilities", []) or [])
        for ability in abilities:
            try:
                checker = getattr(root, "_ability_is_active", None)
                if callable(checker) and not bool(checker(ability)):
                    continue
            except Exception:
                continue
            try:
                if isinstance(ability, str):
                    text = ability
                else:
                    text = str(getattr(ability, "description", "") or getattr(ability, "name", "") or "")
            except Exception:
                continue
            normalized = root._normalize_rules_text(text or "")
            if normalized and text_grant_re.search(normalized):
                return True
        return False


    def get_deep_strike_min_distance_override(self) -> Optional[float]:
        """
        Return an override for the minimum enemy distance when using Deep Strike, if applicable.

        Currently supports:
        - Power from Pain (Swooping Descent) min distance
        - Cloudstrider (Baharroth) min distance when chosen for the current turn
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        min_dist: Optional[float] = None
        try:
            pain_min = float(sr.get("pain_deep_strike_min_distance", 0) or 0)
            if pain_min > 0:
                min_dist = pain_min if min_dist is None else min(min_dist, pain_min)
        except Exception:
            pass

        try:
            cloud_min = float(sr.get("cloudstrider_deep_strike_min_distance", 0) or 0)
        except Exception:
            cloud_min = 0.0
        if cloud_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cloudstrider_choice_turn_owner", "") or "")
                turn = int(sr.get("cloudstrider_choice_turn", 0) or 0)
                if game is not None and owner_id:
                    if str(getattr(game.get_current_player(), "id", "") or "") != owner_id:
                        cloud_min = 0.0
                    elif int(getattr(game, "turn", 0) or 0) != turn:
                        cloud_min = 0.0
            except Exception:
                cloud_min = 0.0
            if cloud_min > 0:
                min_dist = cloud_min if min_dist is None else min(min_dist, cloud_min)

        try:
            cosmic_min = float(sr.get("cosmic_precision_deep_strike_min_distance", 0) or 0)
        except Exception:
            cosmic_min = 0.0
        if cosmic_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cosmic_precision_turn_owner", "") or "")
                turn = int(sr.get("cosmic_precision_turn", 0) or 0)
                exp = str(sr.get("cosmic_precision_expires_phase", "") or "").strip().upper()
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        cosmic_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        cosmic_min = 0.0
                    elif exp and pname and exp != pname:
                        cosmic_min = 0.0
            except Exception:
                cosmic_min = 0.0
            if cosmic_min > 0:
                min_dist = cosmic_min if min_dist is None else min(min_dist, cosmic_min)

        try:
            reletavistic_min = float(sr.get("enhancement_reletavistic_tether_deep_strike_min_distance", 0) or 0)
        except Exception:
            reletavistic_min = 0.0
        if reletavistic_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                requires_bearer_alive = bool(sr.get("enhancement_reletavistic_tether_requires_bearer_alive", True))
                bearer_model_id = str(
                    sr.get("enhancement_reletavistic_tether_bearer_model_id", "")
                    or sr.get("enhancement_bearer_model_id", "")
                    or ""
                ).strip()
                if requires_bearer_alive and bearer_model_id:
                    get_model_by_id = getattr(root, "get_attached_unit_model_by_id", None)
                    if callable(get_model_by_id):
                        bearer_model = get_model_by_id(bearer_model_id)
                        if bearer_model is None or not bool(getattr(bearer_model, "is_alive", False)):
                            reletavistic_min = 0.0
                if reletavistic_min > 0 and game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    source_owner = str(getattr(getattr(army, "player", None), "id", "") or "") if army is not None else ""
                    if source_owner and cur_owner and source_owner != cur_owner:
                        reletavistic_min = 0.0
            except Exception:
                reletavistic_min = 0.0
            if reletavistic_min > 0:
                min_dist = reletavistic_min if min_dist is None else min(min_dist, reletavistic_min)

        try:
            screaming_descent_min = float(sr.get("dread_talons_screaming_descent_deep_strike_min_distance", 0) or 0)
        except Exception:
            screaming_descent_min = 0.0
        if screaming_descent_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("dread_talons_screaming_descent_turn_owner", "") or "")
                turn = int(sr.get("dread_talons_screaming_descent_turn", 0) or 0)
                exp = str(sr.get("dread_talons_screaming_descent_phase", "") or "").strip().upper()
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        screaming_descent_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        screaming_descent_min = 0.0
                    elif exp and pname and exp != pname:
                        screaming_descent_min = 0.0
            except Exception:
                screaming_descent_min = 0.0
            if screaming_descent_min > 0:
                min_dist = (
                    screaming_descent_min
                    if min_dist is None
                    else min(min_dist, screaming_descent_min)
                )

        try:
            cloudstrike_min = float(sr.get("cloudstrike_deep_strike_min_distance", 0) or 0)
        except Exception:
            cloudstrike_min = 0.0
        if cloudstrike_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("cloudstrike_turn_owner", "") or "")
                turn = int(sr.get("cloudstrike_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("cloudstrike_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        cloudstrike_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        cloudstrike_min = 0.0
                    elif exp and pname and exp != pname:
                        cloudstrike_min = 0.0
            except Exception:
                cloudstrike_min = 0.0
            if cloudstrike_min > 0:
                min_dist = cloudstrike_min if min_dist is None else min(min_dist, cloudstrike_min)

        try:
            tunnel_crawlers_min = float(sr.get("tunnel_crawlers_deep_strike_min_distance", 0) or 0)
        except Exception:
            tunnel_crawlers_min = 0.0
        if tunnel_crawlers_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("tunnel_crawlers_turn_owner", "") or "")
                turn = int(sr.get("tunnel_crawlers_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("tunnel_crawlers_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        tunnel_crawlers_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        tunnel_crawlers_min = 0.0
                    elif exp and pname and exp != pname:
                        tunnel_crawlers_min = 0.0
            except Exception:
                tunnel_crawlers_min = 0.0
            if tunnel_crawlers_min > 0:
                min_dist = tunnel_crawlers_min if min_dist is None else min(min_dist, tunnel_crawlers_min)

        try:
            denizens_min = float(sr.get("denizens_deep_strike_min_distance", 0) or 0)
        except Exception:
            denizens_min = 0.0
        if denizens_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("denizens_deep_strike_turn_owner", "") or "")
                turn = int(sr.get("denizens_deep_strike_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("denizens_deep_strike_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        denizens_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        denizens_min = 0.0
                    elif exp and pname and exp != pname:
                        denizens_min = 0.0
            except Exception:
                denizens_min = 0.0
            if denizens_min > 0:
                min_dist = denizens_min if min_dist is None else min(min_dist, denizens_min)

        try:
            rapid_min = float(sr.get("rapid_manifestation_deep_strike_min_distance", 0) or 0)
        except Exception:
            rapid_min = 0.0
        if rapid_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("rapid_manifestation_turn_owner", "") or "")
                turn = int(sr.get("rapid_manifestation_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("rapid_manifestation_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        rapid_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        rapid_min = 0.0
                    elif exp and pname and exp != pname:
                        rapid_min = 0.0
            except Exception:
                rapid_min = 0.0
            if rapid_min > 0:
                min_dist = rapid_min if min_dist is None else min(min_dist, rapid_min)

        try:
            combat_manifestation_min = float(sr.get("combat_manifestation_deep_strike_min_distance", 0) or 0)
        except (TypeError, ValueError):
            combat_manifestation_min = 0.0
        if combat_manifestation_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("combat_manifestation_deep_strike_turn_owner", "") or "")
            turn_raw = sr.get("combat_manifestation_deep_strike_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("combat_manifestation_deep_strike_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    combat_manifestation_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    combat_manifestation_min = 0.0
                elif exp and pname and exp != pname:
                    combat_manifestation_min = 0.0
            if combat_manifestation_min > 0:
                min_dist = (
                    combat_manifestation_min
                    if min_dist is None
                    else min(min_dist, combat_manifestation_min)
                )

        try:
            tau_shortened_blade_min = float(sr.get("tau_shortened_blade_deep_strike_min_distance", 0) or 0)
        except (TypeError, ValueError):
            tau_shortened_blade_min = 0.0
        if tau_shortened_blade_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("tau_shortened_blade_deep_strike_turn_owner", "") or "")
            turn_raw = sr.get("tau_shortened_blade_deep_strike_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("tau_shortened_blade_deep_strike_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    tau_shortened_blade_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    tau_shortened_blade_min = 0.0
                elif exp and pname and exp != pname:
                    tau_shortened_blade_min = 0.0
            if tau_shortened_blade_min > 0:
                min_dist = (
                    tau_shortened_blade_min
                    if min_dist is None
                    else min(min_dist, tau_shortened_blade_min)
                )

        try:
            relic_teleportarium_min = float(
                sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_min_distance", 0) or 0
            )
        except (TypeError, ValueError):
            relic_teleportarium_min = 0.0
        if relic_teleportarium_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_turn_owner", "") or "")
            turn_raw = sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("space_marines_inner_circle_relic_teleportarium_deep_strike_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    relic_teleportarium_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    relic_teleportarium_min = 0.0
                elif exp and pname and exp != pname:
                    relic_teleportarium_min = 0.0
            if relic_teleportarium_min > 0:
                min_dist = (
                    relic_teleportarium_min
                    if min_dist is None
                    else min(min_dist, relic_teleportarium_min)
                )

        try:
            angelic_host_min = float(
                sr.get("space_marines_angelic_host_descent_of_angels_deep_strike_min_distance", 0) or 0
            )
        except (TypeError, ValueError):
            angelic_host_min = 0.0
        if angelic_host_min > 0:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            game = getattr(getattr(army, "player", None), "game", None)
            owner_id = str(sr.get("space_marines_angelic_host_descent_of_angels_turn_owner", "") or "")
            turn_raw = sr.get("space_marines_angelic_host_descent_of_angels_turn", 0)
            try:
                turn = int(turn_raw or 0)
            except (TypeError, ValueError):
                turn = 0
            if game is not None:
                try:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    cur_turn = 0
                get_current_player = getattr(game, "get_current_player", None)
                cur_player = get_current_player() if callable(get_current_player) else None
                cur_owner = str(getattr(cur_player, "id", "") or "")
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                exp = str(sr.get("space_marines_angelic_host_descent_of_angels_expires_phase", "") or "").strip().upper()
                if owner_id and cur_owner and owner_id != cur_owner:
                    angelic_host_min = 0.0
                elif turn and cur_turn and turn != cur_turn:
                    angelic_host_min = 0.0
                elif exp and pname and exp != pname:
                    angelic_host_min = 0.0
            if angelic_host_min > 0:
                min_dist = angelic_host_min if min_dist is None else min(min_dist, angelic_host_min)

        try:
            hallowed_beacon_min = float(sr.get("hallowed_beacon_deep_strike_min_distance", 0) or 0)
        except Exception:
            hallowed_beacon_min = 0.0
        if hallowed_beacon_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("hallowed_beacon_turn_owner", "") or "")
                turn = int(sr.get("hallowed_beacon_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("hallowed_beacon_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        hallowed_beacon_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        hallowed_beacon_min = 0.0
                    elif exp and pname and exp != pname:
                        hallowed_beacon_min = 0.0
            except Exception:
                hallowed_beacon_min = 0.0
            if hallowed_beacon_min > 0:
                min_dist = hallowed_beacon_min if min_dist is None else min(min_dist, hallowed_beacon_min)

        try:
            hearthband_materialisation_min = float(
                sr.get("hearthband_materialisation_matrices_deep_strike_min_distance", 0) or 0
            )
        except Exception:
            hearthband_materialisation_min = 0.0
        if hearthband_materialisation_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("hearthband_materialisation_matrices_turn_owner", "") or "")
                turn = int(sr.get("hearthband_materialisation_matrices_turn", 0) or 0)
                if game is not None:
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("hearthband_materialisation_matrices_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        hearthband_materialisation_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        hearthband_materialisation_min = 0.0
                    elif exp and pname and exp != pname:
                        hearthband_materialisation_min = 0.0
            except Exception:
                hearthband_materialisation_min = 0.0
            if hearthband_materialisation_min > 0:
                min_dist = (
                    hearthband_materialisation_min
                    if min_dist is None
                    else min(min_dist, hearthband_materialisation_min)
                )

        try:
            gift_of_the_prescient_min = float(sr.get("gift_of_the_prescient_deep_strike_min_distance", 0) or 0)
        except (TypeError, ValueError):
            gift_of_the_prescient_min = 0.0
        if gift_of_the_prescient_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                if game is not None:
                    phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    expires_phase = str(sr.get("gift_of_the_prescient_expires_phase", "") or "").strip().upper()
                    if expires_phase and phase_name and expires_phase != phase_name:
                        gift_of_the_prescient_min = 0.0
            except Exception:
                gift_of_the_prescient_min = 0.0
            if gift_of_the_prescient_min > 0:
                min_dist = (
                    gift_of_the_prescient_min
                    if min_dist is None
                    else min(min_dist, gift_of_the_prescient_min)
                )

        try:
            dark_apparitions_min = float(sr.get("dark_apparitions_deep_strike_min_distance", 0) or 0)
        except Exception:
            dark_apparitions_min = 0.0
        if dark_apparitions_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
                if game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    exp = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
                    if owner_id and cur_owner and owner_id != cur_owner:
                        dark_apparitions_min = 0.0
                    elif exp and pname and exp != pname:
                        dark_apparitions_min = 0.0
            except Exception:
                dark_apparitions_min = 0.0
            if dark_apparitions_min > 0:
                min_dist = dark_apparitions_min if min_dist is None else min(min_dist, dark_apparitions_min)

        try:
            through_the_veil_min = float(sr.get("thousand_sons_through_the_veil_deep_strike_min_distance", 0) or 0)
        except Exception:
            through_the_veil_min = 0.0
        if through_the_veil_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("thousand_sons_through_the_veil_turn_owner", "") or "")
                turn = int(sr.get("thousand_sons_through_the_veil_turn", 0) or 0)
                exp = str(sr.get("thousand_sons_through_the_veil_expires_phase", "") or "").strip().upper()
                active = bool(sr.get("thousand_sons_through_the_veil_active"))
                if not active:
                    through_the_veil_min = 0.0
                elif game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    if owner_id and cur_owner and owner_id != cur_owner:
                        through_the_veil_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        through_the_veil_min = 0.0
                    elif exp and pname and exp != pname:
                        through_the_veil_min = 0.0
            except Exception:
                through_the_veil_min = 0.0
            if through_the_veil_min > 0:
                min_dist = (
                    through_the_veil_min
                    if min_dist is None
                    else min(min_dist, through_the_veil_min)
                )

        try:
            twisted_mirage_min = float(sr.get("thousand_sons_twisted_mirage_deep_strike_min_distance", 0) or 0)
        except Exception:
            twisted_mirage_min = 0.0
        if twisted_mirage_min > 0:
            try:
                game = None
                try:
                    army = root.get_parent_army()
                except Exception:
                    army = None
                try:
                    game = getattr(getattr(army, "player", None), "game", None)
                except Exception:
                    game = None
                owner_id = str(sr.get("thousand_sons_twisted_mirage_turn_owner", "") or "")
                turn = int(sr.get("thousand_sons_twisted_mirage_turn", 0) or 0)
                exp = str(sr.get("thousand_sons_twisted_mirage_expires_phase", "") or "").strip().upper()
                active = bool(sr.get("thousand_sons_twisted_mirage_active"))
                if not active:
                    twisted_mirage_min = 0.0
                elif game is not None:
                    cur_player = getattr(game, "get_current_player", lambda: None)()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    pname = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
                    cur_turn = int(getattr(game, "turn", 0) or 0)
                    if owner_id and cur_owner and owner_id != cur_owner:
                        twisted_mirage_min = 0.0
                    elif turn and cur_turn and turn != cur_turn:
                        twisted_mirage_min = 0.0
                    elif exp and pname and exp != pname:
                        twisted_mirage_min = 0.0
            except Exception:
                twisted_mirage_min = 0.0
            if twisted_mirage_min > 0:
                min_dist = (
                    twisted_mirage_min
                    if min_dist is None
                    else min(min_dist, twisted_mirage_min)
                )

        return float(min_dist) if min_dist is not None else None


    def get_dark_apparitions_friendly_distance_requirement(self, *, game=None) -> Optional[float]:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return None
        try:
            required = float(sr.get("dark_apparitions_requires_emperors_children_within", 0) or 0)
        except Exception:
            required = 0.0
        if required <= 0:
            return None
        gm = game
        if gm is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is not None:
            owner_id = str(sr.get("dark_apparitions_turn_owner", "") or "")
            exp_phase = str(sr.get("dark_apparitions_expires_phase", "") or "").strip().upper()
            try:
                cur_player = getattr(gm, "get_current_player", lambda: None)()
                cur_owner = str(getattr(cur_player, "id", "") or "")
            except Exception:
                cur_owner = ""
            try:
                cur_phase = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                cur_phase = ""
            if owner_id and cur_owner and owner_id != cur_owner:
                return None
            if exp_phase and cur_phase and exp_phase != cur_phase:
                return None
        return float(required)


    def is_dark_apparitions_arrival_valid(
        self,
        prospective_positions: list[tuple[float, float, float, float]],
        *,
        game=None,
        game_map=None,
    ) -> bool:
        required = self.get_dark_apparitions_friendly_distance_requirement(game=game)
        if required is None:
            return True
        if not prospective_positions:
            return False
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        if root is None:
            return False
        gm = game_map
        if gm is None and game is not None:
            gm = getattr(game, "map", None)
        if gm is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            try:
                gm = getattr(getattr(getattr(army, "player", None), "game", None), "map", None)
            except Exception:
                gm = None
        if gm is None:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        player = getattr(army, "player", None)
        if player is None:
            return False
        mgr = getattr(army, "emperors_children", None)
        checker = getattr(mgr, "is_emperors_children_unit", None) if mgr is not None else None

        def _is_emperors_children_unit(unit_obj) -> bool:
            if unit_obj is None:
                return False
            if callable(checker):
                try:
                    return bool(checker(unit_obj))
                except Exception:
                    return False
            try:
                if unit_obj.has_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            try:
                if unit_obj.has_any_keyword("EMPEROR'S CHILDREN"):
                    return True
            except Exception:
                pass
            return False

        from ...utility.aura_utils import horizontal_distance_between_bases_2d

        unit_id = str(get_entity_id(root) or "")
        friendly_model_bases: list[Any] = []
        seen: set[str] = set()
        for unit_obj in list(getattr(gm, "units", []) or []):
            try:
                friendly_root = unit_obj.get_attached_unit_root() if hasattr(unit_obj, "get_attached_unit_root") else unit_obj
            except Exception:
                friendly_root = unit_obj
            if friendly_root is None:
                continue
            friendly_id = str(get_entity_id(friendly_root) or "")
            if friendly_id and friendly_id == unit_id:
                continue
            if friendly_id and friendly_id in seen:
                continue
            if friendly_id:
                seen.add(friendly_id)
            try:
                if friendly_root.get_parent_army().player is not player:
                    continue
            except Exception:
                continue
            if not _is_emperors_children_unit(friendly_root):
                continue
            try:
                if not friendly_root.is_alive():
                    continue
            except Exception:
                continue
            if not bool(getattr(friendly_root, "deployed", False)):
                continue
            if str(getattr(friendly_root, "reserve_status", "deployed")) != "deployed":
                continue
            if getattr(friendly_root, "embarked_in", None) is not None:
                continue
            if bool(getattr(friendly_root, "is_embarked", False)):
                continue
            for model in list(getattr(friendly_root, "models", []) or []):
                if not getattr(model, "is_alive", True):
                    continue
                base = getattr(model, "model_base", None)
                if base is None:
                    continue
                friendly_model_bases.append(base)
        if not friendly_model_bases:
            return False
        unit_models = list(getattr(root, "models", []) or [])
        for idx, (x, y, z, facing) in enumerate(list(prospective_positions or [])):
            if idx >= len(unit_models):
                break
            try:
                base = root._create_potential_base(x, y, z, facing, model=unit_models[idx])
            except Exception:
                return False
            if base is None:
                return False
            within_required = False
            for friendly_base in list(friendly_model_bases or []):
                try:
                    if float(horizontal_distance_between_bases_2d(base, friendly_base)) <= float(required) + 1e-6:
                        within_required = True
                        break
                except Exception:
                    continue
            if not within_required:
                return False
        return True


    def is_through_the_veil_arrival_valid(
        self,
        prospective_positions: list[tuple[float, float, float, float]],
        *,
        game=None,
        game_map=None,
    ) -> bool:
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("thousand_sons_through_the_veil_active")):
            return True
        gm = game
        if gm is None:
            try:
                army = root.get_parent_army()
            except Exception:
                army = None
            gm = getattr(getattr(army, "player", None), "game", None) if army is not None else None
        if gm is None:
            return False
        owner_id = str(sr.get("thousand_sons_through_the_veil_turn_owner", "") or "")
        effect_turn = int(sr.get("thousand_sons_through_the_veil_turn", 0) or 0)
        exp_phase = str(sr.get("thousand_sons_through_the_veil_expires_phase", "") or "").strip().upper()
        cur_player = getattr(gm, "get_current_player", lambda: None)()
        cur_owner = str(getattr(cur_player, "id", "") or "")
        cur_turn = int(getattr(gm, "turn", 0) or 0)
        cur_phase = str(getattr(getattr(gm, "phase", None), "name", "") or "").strip().upper()
        if owner_id and cur_owner and owner_id != cur_owner:
            return True
        if effect_turn and cur_turn and effect_turn != cur_turn:
            return True
        if exp_phase and cur_phase and exp_phase != cur_phase:
            return True
        name_u = str(getattr(root, "name", "") or "").strip().upper()
        has_scarab_keyword = False
        try:
            has_scarab_keyword = bool(root.has_any_keyword("SCARAB OCCULT TERMINATORS"))
        except Exception:
            has_scarab_keyword = False
        if not (has_scarab_keyword or "SCARAB OCCULT TERMINATORS" in name_u):
            return True
        if not prospective_positions:
            return False
        try:
            army = root.get_parent_army()
        except Exception:
            army = None
        if army is None:
            return False
        player = getattr(army, "player", None)
        mgr = getattr(army, "thousand_sons_detachments", None)
        if player is None or mgr is None:
            return False
        zones_fn = getattr(mgr, "_active_hexwarp_flow_zones", None)
        zones = set(zones_fn(game=gm) or {"own"}) if callable(zones_fn) else {"own"}
        if not zones:
            zones = {"own"}
        players = list(getattr(gm, "players", []) or [])
        opponent = next((candidate for candidate in players if candidate is not player), None)
        unit_models = list(getattr(root, "models", []) or [])
        for idx, (x, y, z, facing) in enumerate(list(prospective_positions or [])):
            if idx >= len(unit_models):
                break
            try:
                base = root._create_potential_base(x, y, z, facing, model=unit_models[idx])
            except Exception:
                return False
            if base is None:
                return False
            try:
                in_own = bool(gm.is_position_wholly_in_deployment_zone(float(x), float(y), base, player.id))
            except Exception:
                return False
            try:
                in_enemy = bool(
                    opponent is not None
                    and gm.is_position_wholly_in_deployment_zone(float(x), float(y), base, opponent.id)
                )
            except Exception:
                return False
            zone = "nml"
            if in_own:
                zone = "own"
            elif in_enemy:
                zone = "enemy"
            if zone not in zones:
                return False
        return True


    def _enemy_is_afflicted_for_deep_strike_distance(
        self,
        enemy_unit,
        *,
        game=None,
        game_map=None,
    ) -> bool:
        if enemy_unit is None:
            return False
        try:
            from ...rules.nurgles_gift import NurglesGiftManager
        except Exception:
            return False
        try:
            root = enemy_unit.get_attached_unit_root() if hasattr(enemy_unit, "get_attached_unit_root") else enemy_unit
        except Exception:
            root = enemy_unit
        if root is None:
            return False
        gm = game_map
        if gm is None and game is not None:
            gm = getattr(game, "map", None)
        if game is None:
            try:
                army = self.get_parent_army()
            except Exception:
                army = None
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        try:
            return bool(NurglesGiftManager.get_afflicted_plague_for_unit(root, game=game, game_map=gm) is not None)
        except Exception:
            return False


    def get_deep_strike_min_distance_vs_enemy(
        self,
        enemy_unit,
        *,
        game=None,
        game_map=None,
    ) -> Optional[float]:
        """
        Return a per-enemy Deep Strike minimum distance override, if the unit has one.

        Used for rules like Death Approaches where Afflicted enemies have a smaller
        minimum distance than other enemy units.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        get_specs = getattr(root, "unit_deep_strike_afflicted_distance_specs", None)
        if not callable(get_specs):
            return None
        try:
            specs = list(get_specs() or [])
        except Exception:
            specs = []
        if not specs:
            return None
        afflicted = bool(
            self._enemy_is_afflicted_for_deep_strike_distance(
                enemy_unit,
                game=game,
                game_map=game_map,
            )
        )
        best: Optional[float] = None
        for spec in specs:
            try:
                dist = float(
                    spec.get("afflicted_distance", 0)
                    if afflicted
                    else spec.get("other_distance", 0)
                )
            except Exception:
                dist = 0.0
            if dist <= 0:
                continue
            best = dist if best is None else min(best, dist)
        return float(best) if best is not None else None


    def has_infiltrate(self) -> bool:
        """Check if the unit has Infiltrate ability."""
        # Use cached result if available
        if 'infiltrate' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['infiltrate']

        found = False
        # Rubricae Phalanx (Risen Rubricae): selected unit models gain Infiltrators.
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        try:
            sr = getattr(self, "special_rules", None)
            rsr = getattr(root, "special_rules", None)
            if (
                (isinstance(sr, dict) and sr.get("imperialis_fleet_clandestine_operation_infiltrators"))
                or (isinstance(rsr, dict) and rsr.get("imperialis_fleet_clandestine_operation_infiltrators"))
            ):
                found = True
            if isinstance(rsr, dict) and rsr.get("masters_of_misdirection_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    get_members = getattr(root, "get_attached_unit_members", None)
                    if callable(get_members):
                        members = list(get_members() or [])
                    if not members:
                        members = [root]
                    if self in members:
                        is_character = False
                        has_any_keyword = getattr(self, "has_any_keyword", None)
                        if callable(has_any_keyword):
                            is_character = bool(has_any_keyword("CHARACTER"))
                        if not is_character:
                            has_keyword = getattr(self, "has_keyword", None)
                            if callable(has_keyword):
                                is_character = bool(has_keyword("CHARACTER"))
                        is_epic_hero = False
                        if callable(has_any_keyword):
                            is_epic_hero = bool(has_any_keyword("EPIC HERO"))
                        if not is_epic_hero:
                            has_keyword = getattr(self, "has_keyword", None)
                            if callable(has_keyword):
                                is_epic_hero = bool(has_keyword("EPIC HERO"))
                        if is_character and not is_epic_hero:
                            found = True
            if isinstance(rsr, dict) and rsr.get("risen_rubricae_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
            if not found and isinstance(rsr, dict) and rsr.get("ethereal_pathway_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
            if not found and isinstance(rsr, dict) and rsr.get("informant_network_infiltrators"):
                if self is root:
                    found = True
                else:
                    members = []
                    try:
                        members = list(root.get_attached_unit_members() or [])
                    except Exception:
                        members = []
                    if not members:
                        members = [root]
                    if self in members:
                        found = True
        except Exception:
            found = False
        if not found:
            try:
                if self._butcher_lord_infiltrators_active():
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_mistweave",
                    enhancement_id="000009915005",
                    enhancement_name="mistweave",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_blackwing_shroud",
                    enhancement_id="000010466002",
                    enhancement_name="blackwing shroud",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "enhancement_the_blade_driven_deep",
                    enhancement_id="000008490002",
                    enhancement_name="the blade driven deep",
                ):
                    found = True
            except Exception:
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_skitarii_clandestine_infiltrator",
                    enhancement_id="000008560003",
                    enhancement_name="clandestine infiltrator",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_eager_for_bloodshed",
                    enhancement_id="000010688005",
                    enhancement_name="eager for bloodshed",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_reapers_cowl_infiltrators",
                    enhancement_id="000009781004",
                    enhancement_name="reaper's cowl",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_dimensional_sanctum_infiltrators",
                    enhancement_id="000008546002",
                    enhancement_name="dimensional sanctum",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_enhancement(
                    "enhancement_predatory_instincts_infiltrators",
                    enhancement_id="000009075002",
                    enhancement_name="predatory instincts",
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._attached_unit_has_active_leading_enhancement(
                    "declare_battle_formations_selected_leading_infiltrators",
                    require_bearer_alive=True,
                ):
                    found = True
            except (AttributeError, TypeError, ValueError):
                pass
        if not found:
            try:
                if self._skwad_leader_is_leading_kommandos():
                    found = True
            except Exception:
                pass
        if not found:
            found, _ = self._find_ability_with_patterns(["infiltrators", "infiltrate"])
        
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['infiltrate'] = found
        
        return found


    def has_stealth(self) -> bool:
        """Check if the unit has Stealth ability."""
        # Stratagem: SMOKESCREEN grants Stealth until end of phase.
        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and sr.get("smokescreen_active") is True:
            return True
        if isinstance(sr, dict) and sr.get("traitoris_storm_of_darkness_active") is True:
            return True
        # Enhancement: Praesidius grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_praesidius_stealth"):
            return True
        # Enhancement: Umbral Raptor grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_umbral_raptor_stealth"):
            return True
        # Enhancement: Ghostweave Cloak grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_ghostweave_cloak_stealth"):
            return True
        # Deceptors: Shroud of Obfuscation grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_shroud_of_obfuscation_stealth"):
            return True
        # Chaos Knights (Lords of Dread): Blessing of the Dark Master grants Stealth to the bearer model.
        if isinstance(sr, dict) and sr.get("enhancement_blessing_of_the_dark_master_stealth"):
            return True
        # Dread Talons: Night's Shroud grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_nights_shroud_stealth"):
            return True
        # Nightmare Hunt: Greyveil Hex grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_greyveil_hex_stealth"):
            return True
        # Enhancement: Phial of the Abyss grants Stealth to models in the bearer's unit.
        if isinstance(sr, dict) and sr.get("enhancement_phial_of_the_abyss"):
            return True
        # Reaper's Wager: Reaper's Cowl grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_reapers_cowl_stealth",
            enhancement_id="000009781004",
            enhancement_name="reaper's cowl",
        ):
            return True
        # Wrathful Procession: Pyrebrand grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_pyrebrand",
            enhancement_id="000009843002",
            enhancement_name="pyrebrand",
        ):
            return True
        # Orks Dread Mob: Smoky Gubbinz grants Stealth to models in the bearer's unit.
        if self._attached_unit_has_active_enhancement(
            "enhancement_smoky_gubbinz",
            enhancement_id="000008877004",
            enhancement_name="smoky gubbinz",
        ):
            return True
        # Orks Taktikal Brigade: Skwad Leader bearer gains Stealth while leading Kommandos.
        try:
            if self._skwad_leader_is_leading_kommandos():
                return True
        except Exception:
            pass
        # Attached leader abilities can grant Stealth to the bodyguard unit while leading.
        try:
            root = self.get_attached_unit_root() if hasattr(self, "get_attached_unit_root") else self
        except Exception:
            root = self
        if root is self:
            try:
                for ability, _leader in root._iter_attached_leader_leading_abilities():
                    try:
                        name = str(getattr(ability, "name", "") or "Leading ability")
                        desc = str(getattr(ability, "description", "") or "") or name
                    except Exception:
                        name = "Leading ability"
                        desc = ""
                    text = self._normalize_rules_text(self._strip_eligibility_prefix(desc or name or ""))
                    if not text:
                        continue
                    low = text.lower().replace("\u2019", "'").replace("\u0192?T", "'")
                    low = re.sub(r"[^a-z0-9]+", " ", low)
                    low = re.sub(r"\s+", " ", low).strip()
                    if "while this model is leading a unit" not in low:
                        continue
                    if re.search(
                        r"(?:models in that unit|that unit) (?:have|has|gain|gains) (?:the )?stealth ability",
                        low,
                    ):
                        return True
            except Exception:
                pass
        # Rad-Zone Corps: Malphonic Susurrus grants Stealth while the bearer is leading.
        if self._attached_unit_has_active_leading_enhancement(
            "enhancement_malphonic_susurrus",
            enhancement_id="000008385003",
            enhancement_name="malphonic susurrus",
        ):
            return True
        # Awakened Dynasty: Nether-realm Casket grants Stealth while the bearer is leading.
        if self._attached_unit_has_active_leading_enhancement(
            "enhancement_nether_realm_casket",
            enhancement_id="000008372003",
            enhancement_name="nether-realm casket",
        ):
            return True
        # Start of opponent Shooting phase effects (e.g., Hallucinogen Grenades) can grant Stealth until end of phase.
        if isinstance(sr, dict) and sr.get("opponent_shooting_phase_stealth_active") is True:
            return True
        # Imperial Knights Valourstrike Lance: Bearer of the Evanescent Ion.
        if isinstance(sr, dict) and sr.get("imperial_knights_evanescent_ion_stealth_active") is True:
            return True
        # Death Guard Flyblown Host: Verminous Haze.
        army = self.get_parent_army()
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        applies_fn = getattr(dg_mgr, "verminous_haze_applies_to_unit", None) if dg_mgr is not None else None
        if callable(applies_fn) and applies_fn(self):
            return True
        # Drukhari: Skysplinter Assault (Phantasmal Smoke).
        drukhari_mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        phantasmal_fn = (
            getattr(drukhari_mgr, "skysplinter_phantasmal_smoke_stealth_applies", None)
            if drukhari_mgr is not None
            else None
        )
        if callable(phantasmal_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(phantasmal_fn(self, game=game)):
                return True
        # Orks: Taktikal Brigade (Lissen 'Ere - Sneaky Stalkin').
        orks_mgr = getattr(army, "orks_detachments", None) if army is not None else None
        sneaky_fn = getattr(orks_mgr, "taktikal_brigade_sneaky_stalkin_stealth_applies", None) if orks_mgr is not None else None
        if callable(sneaky_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(sneaky_fn(self, game=game)):
                return True
        # Haloscreed Battle Clade: Muted Servomotors.
        adm_mgr = getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None
        muted_fn = getattr(adm_mgr, "noospheric_transference_stealth_applies", None) if adm_mgr is not None else None
        if callable(muted_fn):
            game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
            if bool(muted_fn(self, game=game)):
                return True
        stealth_opt_fn = getattr(adm_mgr, "stealth_optimisation_stealth_applies", None) if adm_mgr is not None else None
        if callable(stealth_opt_fn) and bool(stealth_opt_fn(self)):
            return True
        # Astra Militarum: Siege Regiment (Smoke Shells).
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        smoke_fn = getattr(am_mgr, "siege_regiment_smoke_shells_stealth_applies", None) if am_mgr is not None else None
        if callable(smoke_fn) and bool(smoke_fn(self)):
            return True
        mechanised_smoke_fn = (
            getattr(am_mgr, "mechanised_assault_smoke_grenades_stealth_applies", None) if am_mgr is not None else None
        )
        if callable(mechanised_smoke_fn) and bool(mechanised_smoke_fn(self)):
            return True
        # Tyranids: Vanguard Onslaught (Chameleonic).
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        chameleonic_fn = (
            getattr(tyr_mgr, "vanguard_onslaught_chameleonic_stealth_applies", None) if tyr_mgr is not None else None
        )
        if callable(chameleonic_fn) and bool(chameleonic_fn(self)):
            return True
        # Use cached result if available
        if 'stealth' in getattr(self, '_ability_cache', {}):
            found = self._ability_cache['stealth']
        else:
            found, _ = self._find_ability_with_patterns(["stealth"])
            # Cache the result
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['stealth'] = found

        if found:
            return True

        try:
            from ...utility.aura_effects import get_aura_stealth
            aura_active, _reasons = get_aura_stealth(self)
            if aura_active:
                return True
        except Exception:
            pass
        
        return False


    def _is_non_self_scout_clause(self, text: str) -> bool:
        low = str(text or "").lower().replace("\u2019", "'").replace("\u0192?T", "'")
        low = re.sub(r"\s+", " ", low).strip()
        if "scout" not in low:
            return False
        if re.search(
            r"if this unit has a leader unit attached to it during the declare battle formations step,?\s*"
            r"that leader unit gains(?: the)? scouts?\s*\d+",
            low,
            flags=re.IGNORECASE,
        ):
            return True
        if re.search(
            r"if a [^.;]+ model from your army is attached to this unit during the declare battle formations step,?\s*"
            r"that model gains(?: the)? scouts?\s*\d+",
            low,
            flags=re.IGNORECASE,
        ):
            return True
        return False


    def _has_self_scout_source(self) -> bool:
        for keyword in list(getattr(self, "keywords", []) or []):
            if "scout" in str(keyword or "").lower():
                return True

        for ability in list(self._iter_active_possible_abilities() or []):
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    seg_low = str(segment or "").lower()
                    if "scout" not in seg_low:
                        continue
                    if self._is_non_self_scout_clause(seg_low):
                        continue
                    return True
                continue

            name = str(getattr(ability, "name", "") or "")
            if "scout" in name.lower():
                return True
            description = str(getattr(ability, "description", "") or "")
            for segment in self._iter_conditioned_text_segments(description):
                seg_low = str(segment or "").lower()
                if "scout" not in seg_low:
                    continue
                if self._is_non_self_scout_clause(seg_low):
                    continue
                return True

        for ability in list(getattr(self, "abilities", []) or []):
            try:
                if not self._ability_is_active(ability):
                    continue
            except Exception:
                pass
            if isinstance(ability, str):
                for segment in self._iter_conditioned_text_segments(ability):
                    seg_low = str(segment or "").lower()
                    if "scout" not in seg_low:
                        continue
                    if self._is_non_self_scout_clause(seg_low):
                        continue
                    return True
                continue

            name = str(getattr(ability, "name", "") or "")
            if "scout" in name.lower():
                return True
            description = str(getattr(ability, "description", "") or "")
            for segment in self._iter_conditioned_text_segments(description):
                seg_low = str(segment or "").lower()
                if "scout" not in seg_low:
                    continue
                if self._is_non_self_scout_clause(seg_low):
                    continue
                return True

        return False


    def _get_attached_unit_scout_bonus_distance(self) -> float:
        """
        Return the maximum scout distance granted via special rules across attached unit members.

        Used for enhancement/formation bonuses that grant Scouts to the bearer's unit.
        """
        try:
            root = self.get_attached_unit_root()
        except Exception:
            root = self
        bodyguard_not_embarked = True
        try:
            bodyguard_not_embarked = not (
                bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None))
            )
        except Exception:
            bodyguard_not_embarked = True
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        max_dist = 0.0
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            val = 0.0
            try:
                val = max(val, float(sr.get("enhancement_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("declare_battle_formations_selected_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("enhancement_warped_foresight_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("iconoclast_pave_the_way_scout_distance", 0) or 0))
            except Exception:
                pass
            try:
                val = max(val, float(sr.get("leading_bodyguard_scout_distance", 0) or 0))
            except Exception:
                pass
            if bodyguard_not_embarked:
                try:
                    val = max(
                        val,
                        float(sr.get("leading_bodyguard_scout_distance_requires_bodyguard_not_embarked", 0) or 0),
                    )
                except Exception:
                    pass
            if val > max_dist:
                max_dist = val
        return float(max_dist)


    def has_scout(self) -> Tuple[bool, float]:
        """Check if the unit has Scout ability and return the scout distance.
        
        Returns:
            Tuple[bool, float]: A tuple containing:
                - A boolean indicating if the unit has Scout ability
                - The scout distance in inches (0.0 if no Scout ability)
        """
        verminous_haze_active = False
        verminous_haze_distance = 0.0
        army = self.get_parent_army()
        dg_mgr = getattr(army, "death_guard_detachments", None) if army is not None else None
        active_fn = getattr(dg_mgr, "is_flyblown_host", None) if dg_mgr is not None else None
        if callable(active_fn):
            verminous_haze_active = bool(active_fn())
        scout_fn = getattr(dg_mgr, "verminous_haze_scout_distance_for_unit", None) if dg_mgr is not None else None
        if callable(scout_fn):
            verminous_haze_distance = float(scout_fn(self) or 0.0)
        am_scout_dynamic = False
        recon_survival_gear_distance = 0.0
        siege_eager_advance_distance = 0.0
        am_mgr = getattr(army, "astra_militarum_detachments", None) if army is not None else None
        recon_scout_fn = (
            getattr(am_mgr, "recon_element_survival_gear_scout_distance", None) if am_mgr is not None else None
        )
        if callable(recon_scout_fn):
            am_scout_dynamic = True
            recon_survival_gear_distance = float(recon_scout_fn(self) or 0.0)
        siege_scout_fn = (
            getattr(am_mgr, "siege_regiment_eager_advance_scout_distance", None) if am_mgr is not None else None
        )
        if callable(siege_scout_fn):
            am_scout_dynamic = True
            siege_eager_advance_distance = float(siege_scout_fn(self) or 0.0)
        csm_scout_dynamic = False
        mark_of_the_hound_distance = 0.0
        sorrowscent_vulture_distance = 0.0
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        csm_scout_fn = (
            getattr(csm_mgr, "renegade_raiders_mark_of_the_hound_scout_distance", None) if csm_mgr is not None else None
        )
        csm_nightmare_scout_fn = (
            getattr(csm_mgr, "nightmare_hunt_sorrowscent_vulture_scout_distance", None)
            if csm_mgr is not None
            else None
        )
        if callable(csm_scout_fn):
            csm_scout_dynamic = True
            mark_of_the_hound_distance = float(csm_scout_fn(self) or 0.0)
        if callable(csm_nightmare_scout_fn):
            csm_scout_dynamic = True
            sorrowscent_vulture_distance = float(csm_nightmare_scout_fn(self) or 0.0)

        # Use cached result if available
        if (
            (not verminous_haze_active)
            and (not am_scout_dynamic)
            and (not csm_scout_dynamic)
            and 'scout' in getattr(self, '_ability_cache', {})
        ):
            return self._ability_cache['scout']
        
        try:
            found, distance_str = self._find_ability_with_patterns(["scout"], extract_value=True, value_pattern=r'(\d+)')
        except ValueError:
            found, distance_str = False, None
        if found and not self._has_self_scout_source():
            found, distance_str = False, None
        if not found:
            try:
                for txt in self._iter_active_ability_texts():
                    low = str(txt or "").lower()
                    if "scout" not in low:
                        continue
                    if self._is_non_self_scout_clause(low):
                        continue
                    m = re.search(r"scouts?\s*(\d+)", low)
                    if m:
                        found = True
                        distance_str = m.group(1)
                        break
            except Exception:
                found, distance_str = False, None
        dist = float(distance_str) if found else 0.0
        try:
            bonus_dist = float(self._get_attached_unit_scout_bonus_distance() or 0.0)
        except Exception:
            bonus_dist = 0.0
        if bonus_dist > 0:
            found = True
            dist = max(float(dist or 0.0), float(bonus_dist))
        try:
            sr = getattr(self, "special_rules", None)
            leader_bonus_dist = 0.0
            if isinstance(sr, dict) and bool(getattr(self, "is_attached_leader", False)):
                leader_bonus_dist = float(sr.get("attached_unit_bodyguard_leader_scout_distance", 0) or 0.0)
                conditional_bonus_dist = float(
                    sr.get("attached_unit_bodyguard_leader_scout_distance_requires_bodyguard_embarked", 0) or 0.0
                )
                if conditional_bonus_dist > 0:
                    bodyguard = getattr(self, "attached_to", None)
                    if bodyguard is not None and bool(getattr(bodyguard, "is_embarked", False)):
                        leader_bonus_dist = max(float(leader_bonus_dist), float(conditional_bonus_dist))
        except Exception:
            leader_bonus_dist = 0.0
        if leader_bonus_dist > 0:
            found = True
            dist = max(float(dist or 0.0), float(leader_bonus_dist))
        if verminous_haze_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(verminous_haze_distance))
        if recon_survival_gear_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(recon_survival_gear_distance))
        if siege_eager_advance_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(siege_eager_advance_distance))
        if mark_of_the_hound_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(mark_of_the_hound_distance))
        if sorrowscent_vulture_distance > 0:
            found = True
            dist = max(float(dist or 0.0), float(sorrowscent_vulture_distance))
        result = (True, float(dist)) if found else (False, 0.0)

        # Attached units can only Scout if every model has Scouts (use smallest distance if mixed).
        try:
            if result[0] and (not bool(getattr(self, "is_leader", False)) or getattr(self, "attached_to", None) is None):
                root = self.get_attached_unit_root()
                leaders = list(getattr(root, "attached_leaders", []) or [])
                min_dist = float(result[1])
                for leader in leaders:
                    try:
                        l_found, l_dist = leader.has_scout()
                    except Exception:
                        l_found, l_dist = False, 0.0
                    if not l_found:
                        result = (False, 0.0)
                        break
                    try:
                        min_dist = min(min_dist, float(l_dist))
                    except Exception:
                        pass
                if result[0]:
                    result = (True, float(min_dist))
        except Exception:
            pass
        
        # Cache the result when there are no dynamic Verminous Haze state checks.
        if (not verminous_haze_active) and (not am_scout_dynamic) and (not csm_scout_dynamic):
            if not hasattr(self, '_ability_cache'):
                self._ability_cache = {}
            self._ability_cache['scout'] = result
        
        return result


    def get_scout_distance_normalized(self, max_scout_distance: float = 12.0) -> float:
        """Get the normalized scout distance for deployment considerations.
        
        Args:
            max_scout_distance (float): Maximum possible scout distance for normalization
            
        Returns:
            float: Normalized scout distance (0.0 to 1.0), where 1.0 represents maximum scout mobility
        """
        has_scout_ability, scout_distance = self.has_scout()
        if not has_scout_ability:
            return 0.0
        
        return min(scout_distance / max_scout_distance, 1.0)


    def _enhancement_redeploy_specs(self) -> list[dict]:
        sr = getattr(self, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        raw_specs = list(sr.get("enhancement_redeploy_specs", []) or [])
        specs: list[dict] = []
        for raw in raw_specs:
            if not isinstance(raw, dict):
                continue
            filters: list[str] = []
            for value in list(raw.get("filters", []) or []):
                token = str(value or "").strip().upper()
                if token and token not in filters:
                    filters.append(token)
            excluded_keywords: list[str] = []
            for value in list(raw.get("excluded_keywords", []) or []):
                token = str(value or "").strip().upper()
                if token and token not in excluded_keywords:
                    excluded_keywords.append(token)
            filter_any_groups: list[list[str]] = []
            for raw_group in list(raw.get("filter_any_groups", []) or []):
                raw_values = [raw_group] if isinstance(raw_group, str) else list(raw_group or [])
                group: list[str] = []
                for value in raw_values:
                    token = str(value or "").strip().upper()
                    if token and token not in group:
                        group.append(token)
                if group:
                    filter_any_groups.append(group)
            specs.append(
                {
                    "source": str(raw.get("source", "") or "").strip() or "Redeploy",
                    "source_model_id": str(raw.get("source_model_id", "") or "").strip(),
                    "max_units": max(1, int(raw.get("max_units", 1) or 1)),
                    "can_place_in_reserves": bool(raw.get("can_place_in_reserves", False)),
                    "filters": list(filters),
                    "excluded_keywords": list(excluded_keywords),
                    "filter_any_groups": [list(group) for group in filter_any_groups],
                    "requires_source_on_battlefield": bool(raw.get("requires_source_on_battlefield", False)),
                    "allow_embarked_transport_on_battlefield": bool(
                        raw.get("allow_embarked_transport_on_battlefield", False)
                    ),
                    "exclude_source_unit": bool(raw.get("exclude_source_unit", False)),
                    "must_include_source_unit": bool(raw.get("must_include_source_unit", False)),
                    "require_exact_count": bool(raw.get("require_exact_count", False)),
                    "army_once_per_ability": bool(raw.get("army_once_per_ability", False)),
                    "strategic_reserves_ignore_current_unit_count_limit": bool(
                        raw.get("strategic_reserves_ignore_current_unit_count_limit", False)
                    ),
                }
            )
        specs.sort(
            key=lambda spec: (
                str(spec.get("source_model_id", "") or ""),
                str(spec.get("source", "") or "").lower(),
                int(spec.get("max_units", 0) or 0),
                tuple(spec.get("filters", []) or []),
            )
        )
        return specs


    def has_redeploy(self) -> Tuple[bool, int, bool]:
        """Check if the unit grants redeploy capability.

        Returns:
            Tuple[bool, int, bool]:
                - has_redeploy: True if this unit grants redeploy to units in the army
                - count: number of units that can be redeployed (default 3; D3 treated as 3 for now)
                - can_place_in_reserves: True if redeployed units may be placed into Strategic Reserves regardless of limits

        Notes:
            We intentionally parse ability descriptions rather than names. The wording generally includes
            "after both players have deployed their armies" and "select up to" N units from your army "and redeploy them".
        """
        # Use cached result if available
        if 'redeploy' in getattr(self, '_ability_cache', {}):
            return self._ability_cache['redeploy']

        redeploy_specs = self._enhancement_redeploy_specs()
        if redeploy_specs:
            spec = dict(redeploy_specs[0] or {})
            result = (
                True,
                int(spec.get("max_units", 1) or 1),
                bool(spec.get("can_place_in_reserves", False)),
            )
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if list(spec.get("filters", []) or []):
                self._ability_cache["redeploy_filters"] = list(spec.get("filters", []) or [])
            if list(spec.get("excluded_keywords", []) or []):
                self._ability_cache["redeploy_excluded_keywords"] = list(spec.get("excluded_keywords", []) or [])
            if list(spec.get("filter_any_groups", []) or []):
                self._ability_cache["redeploy_filter_any_groups"] = [
                    list(group) for group in list(spec.get("filter_any_groups", []) or [])
                ]
            self._ability_cache["redeploy_ability_name"] = str(spec.get("source", "") or "Redeploy")
            self._ability_cache["redeploy_requires_source_on_battlefield"] = bool(
                spec.get("requires_source_on_battlefield", False)
            )
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = bool(
                spec.get("allow_embarked_transport_on_battlefield", False)
            )
            self._ability_cache["redeploy_exclude_source_unit"] = bool(spec.get("exclude_source_unit", False))
            self._ability_cache["redeploy_must_include_source_unit"] = bool(
                spec.get("must_include_source_unit", False)
            )
            self._ability_cache["redeploy_require_exact_count"] = bool(spec.get("require_exact_count", False))
            self._ability_cache["redeploy_army_once_per_ability"] = bool(
                spec.get("army_once_per_ability", False)
            )
            self._ability_cache["redeploy_strategic_reserves_ignore_current_unit_count_limit"] = bool(
                spec.get("strategic_reserves_ignore_current_unit_count_limit", False)
            )
            return result

        sr = getattr(self, "special_rules", None)
        if isinstance(sr, dict) and bool(sr.get("enhancement_orbital_uplink_reliquary", False)):
            try:
                count = int(sr.get("enhancement_orbital_uplink_reliquary_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(
                sr.get("enhancement_orbital_uplink_reliquary_can_place_in_reserves", True)
            )
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_orbital_uplink_reliquary_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_orbital_uplink_reliquary_source", "") or "Orbital Uplink Reliquary")
                .strip()
                or "Orbital Uplink Reliquary"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_hunters_guile", False)):
            try:
                count = int(sr.get("enhancement_hunters_guile_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_hunters_guile_can_place_in_reserves", True))
            raw_any_groups = list(sr.get("enhancement_hunters_guile_filter_any_groups", []) or [])
            filter_any_groups: list[list[str]] = []
            for raw_group in raw_any_groups:
                if isinstance(raw_group, str):
                    raw_values = [raw_group]
                else:
                    raw_values = list(raw_group or [])
                group: list[str] = []
                for value in raw_values:
                    keyword = str(value or "").strip().upper()
                    if not keyword or keyword in group:
                        continue
                    group.append(keyword)
                if group:
                    filter_any_groups.append(group)
            ability_name = (
                str(sr.get("enhancement_hunters_guile_source", "") or "Hunter's Guile")
                .strip()
                or "Hunter's Guile"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filter_any_groups:
                self._ability_cache["redeploy_filter_any_groups"] = [list(group) for group in filter_any_groups]
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_chariots_of_the_storm", False)):
            try:
                count = int(sr.get("enhancement_chariots_of_the_storm_max_units", 3) or 3)
            except Exception:
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_chariots_of_the_storm_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_chariots_of_the_storm_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_chariots_of_the_storm_source", "") or "Chariots of the Storm")
                .strip()
                or "Chariots of the Storm"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_advance_augury", False)):
            try:
                count = int(sr.get("enhancement_advance_augury_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_advance_augury_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_advance_augury_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_advance_augury_source", "") or "Advance Augury")
                .strip()
                or "Advance Augury"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_guerrilla_honours", False)):
            try:
                count = int(sr.get("enhancement_guerrilla_honours_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_guerrilla_honours_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_guerrilla_honours_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_guerrilla_honours_source", "") or "Guerrilla Honours")
                .strip()
                or "Guerrilla Honours"
            )
            exclude_source_unit = bool(sr.get("enhancement_guerrilla_honours_exclude_source_unit", True))
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = True
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            self._ability_cache["redeploy_exclude_source_unit"] = bool(exclude_source_unit)
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_skitarii_veiled_hunter", False)):
            try:
                count = int(sr.get("enhancement_skitarii_veiled_hunter_max_units", 3) or 3)
            except (TypeError, ValueError):
                count = 3
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_skitarii_veiled_hunter_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_skitarii_veiled_hunter_filters", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_skitarii_veiled_hunter_source", "") or "Veiled Hunter")
                .strip()
                or "Veiled Hunter"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        if isinstance(sr, dict) and bool(sr.get("enhancement_castellans_mark", False)):
            try:
                count = int(sr.get("enhancement_castellans_mark_max_units", 2) or 2)
            except (TypeError, ValueError):
                count = 2
            if count <= 0:
                count = 1
            can_place_in_reserves = bool(sr.get("enhancement_castellans_mark_can_place_in_reserves", True))
            filters = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_castellans_mark_filters", []) or [])
                if str(v or "").strip()
            ]
            excluded_keywords = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_castellans_mark_excluded_keywords", []) or [])
                if str(v or "").strip()
            ]
            ability_name = (
                str(sr.get("enhancement_castellans_mark_source", "") or "Castellan's Mark")
                .strip()
                or "Castellan's Mark"
            )
            result = (True, int(count), bool(can_place_in_reserves))
            if not hasattr(self, "_ability_cache"):
                self._ability_cache = {}
            self._ability_cache["redeploy"] = result
            if filters:
                self._ability_cache["redeploy_filters"] = list(filters)
            if excluded_keywords:
                self._ability_cache["redeploy_excluded_keywords"] = list(excluded_keywords)
            self._ability_cache["redeploy_ability_name"] = ability_name
            self._ability_cache["redeploy_requires_source_on_battlefield"] = False
            self._ability_cache["redeploy_allow_embarked_transport_on_battlefield"] = False
            return result

        has_redeploy = False
        count = 0
        can_place_in_reserves = False

        # Normalize abilities list: abilities may be attached to models in unit
        abilities_to_check: list[tuple[str, str]] = []
        for model in getattr(self, 'models', []):
            for ability in getattr(model, 'abilities', []):
                if ability and hasattr(ability, 'description'):
                    try:
                        if not self._ability_is_active(ability):
                            continue
                    except Exception:
                        pass
                    abilities_to_check.append((getattr(ability, "name", "") or "", ability.description))

        # Also include unit-level possible_abilities if present
        for ability in self._iter_active_possible_abilities():
            if ability and hasattr(ability, 'description'):
                abilities_to_check.append((getattr(ability, "name", "") or "", ability.description))

        # Enhancement text applies to the enhancement bearer (unit-level for redeploy rules).
        try:
            enh = getattr(self, "enhancement", None)
            if enh is not None:
                desc = getattr(enh, "description", "") or ""
                if desc:
                    abilities_to_check.append((getattr(enh, "name", "") or "", desc))
        except Exception:
            pass

        redeploy_filters: list[str] = []
        redeploy_filter_any_groups: list[list[str]] = []
        ability_name = ""
        requires_source_on_battlefield = False
        allow_embarked_transport_on_battlefield = False
        must_include_source_unit = False
        require_exact_count = False
        army_once_per_ability = False

        def _apply_redeploy_count_token(raw_value: str) -> None:
            nonlocal count
            val = str(raw_value or "").strip().lower()
            if not val:
                return
            if val.startswith("d"):
                try:
                    expr = val.upper().replace(" ", "")
                    d = DiceCollection.from_string(expr)
                    total, rolls = d.roll_detailed()
                    count = max(count, total)
                    setattr(self, "_redeploy_d_roll", {"expr": expr, "total": total, "rolls": rolls})
                    logger.info(f"{self.name} Redeploy {expr} roll: {total} (rolled {rolls})")
                except Exception:
                    count = max(count, 1)
                return
            word_counts = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
            }
            if val in word_counts:
                count = max(count, int(word_counts[val]))
                return
            try:
                count = max(count, int(val))
            except Exception:
                return

        for name, desc in abilities_to_check:
            text = html.unescape(str(desc or ""))
            text = re.sub(r"<[^>]+>", " ", text)
            text = text.lower()
            text = text.replace("\u2019", "'").replace("\u2018", "'")
            text = re.sub(r"\s+", " ", text).strip()
            if ("after both players have deployed their armies" in text and "redeploy" in text):
                # Attempt to extract count from "select up to" phrases
                has_redeploy = True
                if name and not ability_name:
                    ability_name = str(name)
                if (
                    "if your army includes one or more units with this ability" in text
                    or "if your army contains one or more units with this ability" in text
                    or "if your army includes one or more models with this ability" in text
                    or "if your army contains one or more models with this ability" in text
                ):
                    army_once_per_ability = True
                if ("if this unit is on the battlefield" in text) or ("if the bearer is on the battlefield" in text):
                    requires_source_on_battlefield = True
                if "transport it is embarked within is on the battlefield" in text:
                    requires_source_on_battlefield = True
                    allow_embarked_transport_on_battlefield = True
                source_and_other_match = re.search(
                    r"redeploy this model'?s unit and one other friendly ([a-z0-9' ]+?) unit",
                    text,
                )
                if source_and_other_match:
                    count = max(count, 2)
                    other_filter = str(source_and_other_match.group(1) or "").strip().upper()
                    if other_filter:
                        redeploy_filters = [other_filter]
                    must_include_source_unit = True
                    require_exact_count = True
                count_match = re.search(
                    r"after both players have deployed their armies.*?select\s+(?:up\s*to\s+)?"
                    r"(?P<count>(?:\d+)|(?:d\d+(?:\s*\+\s*\d+)?)|one|two|three|four|five|six)"
                    r"\s+(?P<filter>.+?)\s+units?\s+from\s+your\s+army\s+and\s+redeploy"
                    r"(?:\s+all\s+of\s+those\s+units|\s+them|\s+it)?",
                    text,
                    flags=re.IGNORECASE,
                )
                filter_text = text
                if count_match:
                    _apply_redeploy_count_token(str(count_match.group("count") or ""))
                    filter_text = str(count_match.group("filter") or "").strip().lower()
                elif not source_and_other_match:
                    count = max(count, 3)  # default to 3 if unspecified
                if "strategic reserves" in text:
                    can_place_in_reserves = True
                if "imperium battleline" in filter_text:
                    redeploy_filters = ["IMPERIUM", "BATTLELINE"]
                if "agents of the imperium" in filter_text:
                    redeploy_filters = ["AGENTS OF THE IMPERIUM"]
                if (
                    "emperor's children" in filter_text
                    or "emperors children" in filter_text
                ):
                    redeploy_filters = ["EMPEROR'S CHILDREN"]
                if "harlequins" in filter_text:
                    redeploy_filters = ["HARLEQUINS"]
                if "adeptus astartes" in filter_text and "infantry" in filter_text:
                    redeploy_filters = ["ADEPTUS ASTARTES", "INFANTRY"]
                elif "adeptus astartes" in filter_text:
                    redeploy_filters = ["ADEPTUS ASTARTES"]
                if "aeldari" in filter_text and "vehicle" in filter_text:
                    redeploy_filters = ["AELDARI", "VEHICLE"]
                elif "aeldari" in filter_text:
                    redeploy_filters = ["AELDARI"]
                if "jakhals" in filter_text and "goremongers" in filter_text:
                    redeploy_filter_any_groups = [["JAKHALS"], ["GOREMONGERS"]]
                if (
                    "t'au empire" in filter_text
                    or "tau empire" in filter_text
                ):
                    redeploy_filters = ["T'AU EMPIRE"]
                if "thousand sons" in filter_text:
                    redeploy_filters = ["THOUSAND SONS"]
                if "tyranids" in filter_text:
                    redeploy_filters = ["TYRANIDS"]
                if "vanguard invader" in filter_text:
                    redeploy_filters = ["VANGUARD INVADER"]
                if (
                    "heretic astartes" in filter_text
                    or "<heretic astartes>" in filter_text
                ):
                    redeploy_filters = ["HERETIC ASTARTES"]
                if "drukhari" in filter_text:
                    redeploy_filters = ["DRUKHARI"]

        result = (has_redeploy, count, can_place_in_reserves)
        # Cache the result
        if not hasattr(self, '_ability_cache'):
            self._ability_cache = {}
        self._ability_cache['redeploy'] = result
        if redeploy_filters:
            self._ability_cache['redeploy_filters'] = list(redeploy_filters)
        if redeploy_filter_any_groups:
            self._ability_cache['redeploy_filter_any_groups'] = [list(group) for group in redeploy_filter_any_groups]
        if ability_name:
            self._ability_cache['redeploy_ability_name'] = ability_name
        self._ability_cache['redeploy_requires_source_on_battlefield'] = bool(requires_source_on_battlefield)
        self._ability_cache['redeploy_allow_embarked_transport_on_battlefield'] = bool(
            allow_embarked_transport_on_battlefield
        )
        self._ability_cache['redeploy_must_include_source_unit'] = bool(must_include_source_unit)
        self._ability_cache['redeploy_require_exact_count'] = bool(require_exact_count)
        self._ability_cache['redeploy_army_once_per_ability'] = bool(army_once_per_ability)
        return result
