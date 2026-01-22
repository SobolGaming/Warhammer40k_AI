from __future__ import annotations

from dataclasses import dataclass
import re

from ..utility.aura_utils import distance_between_models_bases_3d
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class CommandPhaseBearerTargetSpec:
    ability_name: str
    target_label: str
    range_inches: float
    keyword_groups: tuple[tuple[str, ...], ...]
    exclude_keywords: tuple[str, ...]
    effect_key: str
    effect_value: int = 0


class NecronsDetachmentManager(DetachmentManagerBase):
    faction_id = "NEC"

    _COMMAND_PHASE_SELECT_FRIENDLY_RE = re.compile(
        r"in your command phase, select one friendly (?P<target>.+?) unit(?:,|\s)*"
        r"(?:\((?P<exclude>[^)]+)\)\s*)?"
        r"within (?P<range>\d+)\s*\"?\s*of (?:the bearer|this model)",
        flags=re.IGNORECASE,
    )
    _COMMAND_PHASE_FELL_BACK_SHOOT_RE = re.compile(
        r"eligible to shoot in a turn in which it fell back",
        flags=re.IGNORECASE,
    )
    _COMMAND_PHASE_DAMAGE_REDUCTION_RE = re.compile(
        r"each time an attack is allocated to a model in that unit,\s*subtract\s+(?P<val>\d+)\s+from\s+the\s+damage\s+characteristic\s+of\s+that\s+attack",
        flags=re.IGNORECASE,
    )

    def is_starshatter_arsenal(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Starshatter Arsenal")

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        kw = (keyword or "").strip()
        if not kw:
            return False
        try:
            return bool(unit.has_any_keyword(kw))
        except Exception:
            pass
        try:
            raw = [str(k or "") for k in (getattr(unit, "keywords", []) or [])]
            raw += [str(k or "") for k in (getattr(unit, "faction_keywords", []) or [])]
            return kw.lower() in {k.lower() for k in raw if str(k).strip()}
        except Exception:
            return False

    def unit_is_necrons(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "NECRONS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def unit_is_vehicle_or_mounted(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "VEHICLE") or self._unit_has_keyword(unit, "MOUNTED")

    def unit_is_titanic(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "is_titanic", False)):
                return True
        except Exception:
            pass
        return self._unit_has_keyword(unit, "TITANIC")

    def relentless_onslaught_applies(self, unit) -> bool:
        if not self.is_starshatter_arsenal():
            return False
        return self.unit_is_necrons(unit)

    def relentless_onslaught_hit_bonus(self, attacker_unit, target_unit, *, game=None) -> tuple[int, str]:
        if not self.relentless_onslaught_applies(attacker_unit):
            return 0, ""
        if attacker_unit is None or target_unit is None:
            return 0, ""
        game_map = getattr(game, "map", None) if game is not None else None
        try:
            if bool(attacker_unit._target_within_objective_range(target_unit, game_map)):
                return 1, "Relentless Onslaught (+1 to hit vs objective)"
        except Exception:
            pass
        return 0, ""

    def relentless_onslaught_assault_applies(self, unit) -> bool:
        if not self.relentless_onslaught_applies(unit):
            return False
        if self.unit_is_titanic(unit):
            return False
        return self.unit_is_vehicle_or_mounted(unit)

    def _normalize_rules_text(self, text: str) -> str:
        if not text:
            return ""
        try:
            text = re.sub(r"<[^>]+>", " ", text)
        except Exception:
            pass
        text = text.replace("\n", " ").replace("\r", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _strip_eligibility_prefix(self, text: str) -> str:
        t = str(text or "")
        low = t.lower()
        for marker in (" model only.", " models only."):
            idx = low.find(marker)
            if idx != -1:
                return t[idx + len(marker):].strip()
        return t

    def _parse_keyword_groups(self, target_desc: str) -> tuple[tuple[str, ...], ...]:
        if not target_desc:
            return ()
        desc = re.sub(r"\s+", " ", str(target_desc)).strip()
        parts = [p.strip() for p in re.split(r"\s+or\s+", desc, flags=re.IGNORECASE) if p.strip()]
        groups: list[tuple[str, ...]] = []
        for part in parts:
            tokens = part.split()
            if not tokens:
                continue
            last = tokens[-1]
            rest = tokens[:-1]
            group: list[str] = []
            if rest:
                group.append(" ".join(rest))
            group.append(last)
            groups.append(tuple(group))
        return tuple(groups)

    def _parse_exclude_keywords(self, text: str) -> tuple[str, ...]:
        if not text:
            return ()
        low = str(text).lower()
        out: list[str] = []
        if "titanic" in low:
            out.append("TITANIC")
        if "monster" in low:
            out.append("MONSTER")
        if "vehicle" in low and "mounted" in low and "excluding" in low:
            # If a rule explicitly excludes VEHICLE/MOUNTED, respect it.
            out.append("VEHICLE")
            out.append("MOUNTED")
        return tuple(out)

    def _unit_matches_keyword_groups(self, unit, groups: tuple[tuple[str, ...], ...]) -> bool:
        if unit is None:
            return False
        if not groups:
            return True
        for group in groups:
            if all(self._unit_has_keyword(unit, kw) for kw in group):
                return True
        return False

    def _unit_has_any_excluded_keyword(self, unit, exclude: tuple[str, ...]) -> bool:
        if unit is None:
            return False
        for kw in exclude:
            if self._unit_has_keyword(unit, kw):
                return True
        return False

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_active_for_rules", None)
        if callable(fn):
            return bool(fn())
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        try:
            if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                return False
        except Exception:
            pass
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        return True

    def _source_in_range_of_target(self, source_unit, target_unit, range_inches: float) -> bool:
        try:
            r = float(range_inches)
        except Exception:
            return False
        if source_unit is None or target_unit is None or r < 0:
            return False
        try:
            source_models = list(getattr(source_unit, "models", []) or [])
        except Exception:
            source_models = []
        source_models = [m for m in source_models if getattr(m, "is_alive", True)]
        if not source_models:
            return False
        try:
            target_models = list(target_unit.get_attached_unit_models() or [])
        except Exception:
            target_models = list(getattr(target_unit, "models", []) or [])
        target_models = [m for m in target_models if getattr(m, "is_alive", True)]
        if not target_models:
            return False
        for sm in source_models:
            for tm in target_models:
                if distance_between_models_bases_3d(sm, tm) <= r + 1e-6:
                    return True
        return False

    def _iter_command_phase_bearer_specs(self, unit) -> list[CommandPhaseBearerTargetSpec]:
        specs: list[CommandPhaseBearerTargetSpec] = []
        if unit is None:
            return specs
        iter_fn = getattr(unit, "_iter_ability_entries_for_rules", None)
        if not callable(iter_fn):
            return specs
        for name, desc in iter_fn(model=None):
            text = self._normalize_rules_text(desc or name or "")
            if not text:
                continue
            text = text.replace("\u2019", "'")
            text = self._strip_eligibility_prefix(text)
            if not text:
                continue
            m = self._COMMAND_PHASE_SELECT_FRIENDLY_RE.search(text)
            if not m:
                continue
            target_desc = str(m.group("target") or "").strip()
            exclude_raw = str(m.group("exclude") or "").strip()
            try:
                range_inches = float(m.group("range"))
            except Exception:
                range_inches = 0.0
            keyword_groups = self._parse_keyword_groups(target_desc)
            exclude_keywords = self._parse_exclude_keywords(exclude_raw)
            target_label = target_desc or "unit"

            if self._COMMAND_PHASE_FELL_BACK_SHOOT_RE.search(text):
                specs.append(
                    CommandPhaseBearerTargetSpec(
                        ability_name=str(name or "Command Phase Ability"),
                        target_label=target_label,
                        range_inches=range_inches,
                        keyword_groups=keyword_groups,
                        exclude_keywords=exclude_keywords,
                        effect_key="fell_back_shoot",
                        effect_value=1,
                    )
                )

            dmg = self._COMMAND_PHASE_DAMAGE_REDUCTION_RE.search(text)
            if dmg:
                try:
                    val = int(dmg.group("val"))
                except Exception:
                    val = 0
                if val:
                    specs.append(
                        CommandPhaseBearerTargetSpec(
                            ability_name=str(name or "Command Phase Ability"),
                            target_label=target_label,
                            range_inches=range_inches,
                            keyword_groups=keyword_groups,
                            exclude_keywords=exclude_keywords,
                            effect_key="damage_reduction",
                            effect_value=int(val),
                        )
                    )
        return specs

    def spec_from_context(self, ctx: dict | None) -> CommandPhaseBearerTargetSpec | None:
        if not isinstance(ctx, dict):
            return None
        if not bool(ctx.get("necrons_command_phase_enhancement")):
            return None
        ability_name = str(ctx.get("ability") or ctx.get("ability_name") or "").strip()
        target_label = str(ctx.get("target_label") or "unit").strip() or "unit"
        try:
            range_inches = float(ctx.get("range", 0) or 0.0)
        except Exception:
            range_inches = 0.0
        effect_key = str(ctx.get("effect_key") or "").strip()
        try:
            effect_value = int(ctx.get("effect_value", 0) or 0)
        except Exception:
            effect_value = 0
        raw_groups = list(ctx.get("keyword_groups", []) or [])
        keyword_groups: list[tuple[str, ...]] = []
        for group in raw_groups:
            if not group:
                continue
            if isinstance(group, (tuple, list)):
                cleaned = tuple(str(k or "").strip() for k in group if str(k or "").strip())
            else:
                cleaned = (str(group).strip(),)
            if cleaned:
                keyword_groups.append(cleaned)
        exclude = tuple(str(k or "").strip() for k in (ctx.get("exclude_keywords", []) or []) if str(k or "").strip())
        if not ability_name or not effect_key:
            return None
        return CommandPhaseBearerTargetSpec(
            ability_name=ability_name,
            target_label=target_label,
            range_inches=range_inches,
            keyword_groups=tuple(keyword_groups),
            exclude_keywords=exclude,
            effect_key=effect_key,
            effect_value=effect_value,
        )

    def _pending_request_for_source_spec(self, game, source_unit, spec: CommandPhaseBearerTargetSpec):
        if game is None or source_unit is None or spec is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        source_id = str(get_entity_id(source_unit) or "")
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = getattr(req, "context", {}) or {}
            if not bool(ctx.get("necrons_command_phase_enhancement")):
                continue
            if str(ctx.get("source_unit_id", "")) != source_id:
                continue
            if str(ctx.get("effect_key", "")) != str(spec.effect_key):
                continue
            if str(ctx.get("ability", "")) != str(spec.ability_name):
                continue
            return req
        return None

    def build_command_phase_bearer_request(self, game, player, source_unit, spec: CommandPhaseBearerTargetSpec, targets: list):
        if game is None or source_unit is None or spec is None or not targets:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = []
        for target in targets:
            options.append(
                DecisionOption.create(
                    getattr(target, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(target)},
                )
            )
        ctx = {
            "necrons_command_phase_enhancement": True,
            "source_unit_id": get_entity_id(source_unit),
            "ability": getattr(spec, "ability_name", ""),
            "effect_key": getattr(spec, "effect_key", ""),
            "effect_value": int(getattr(spec, "effect_value", 0) or 0),
            "range": float(getattr(spec, "range_inches", 0.0) or 0.0),
            "target_label": getattr(spec, "target_label", ""),
            "keyword_groups": [list(group) for group in (spec.keyword_groups or [])],
            "exclude_keywords": list(spec.exclude_keywords or ()),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select command phase enhancement target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def get_command_phase_bearer_sources(self) -> list[dict]:
        sources: list[dict] = []
        army = self.army
        if army is None:
            return sources
        for unit in list(getattr(army, "units", []) or []):
            if not self._unit_is_active(unit):
                continue
            specs = self._iter_command_phase_bearer_specs(unit)
            for spec in specs:
                sources.append({"source": unit, "spec": spec})
        return sources

    def get_command_phase_bearer_targets(self, source_unit, spec: CommandPhaseBearerTargetSpec) -> list:
        army = self.army
        if army is None or source_unit is None or spec is None:
            return []
        eligible: list = []
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                key = getattr(root, "_id", None) or id(root)
            except Exception:
                key = id(root)
            if key in seen:
                continue
            seen.add(key)
            if not self._unit_is_active(root):
                continue
            if not self._unit_matches_keyword_groups(root, spec.keyword_groups):
                continue
            if self._unit_has_any_excluded_keyword(root, spec.exclude_keywords):
                continue
            if not self._source_in_range_of_target(source_unit, root, spec.range_inches):
                continue
            eligible.append(root)
        eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        return eligible

    def clear_command_phase_bearer_effects(self) -> None:
        army = self.army
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            for key in (
                "command_phase_fell_back_and_shoot_active",
                "command_phase_fell_back_and_shoot_source",
            ):
                sr.pop(key, None)
            entries = list(sr.get("allocated_damage_reductions", []) or [])
            kept = []
            for entry in entries:
                tag = str(entry.get("tag", "") or "")
                if tag.startswith("command_phase_bearer_damage_reduction"):
                    continue
                kept.append(entry)
            if kept:
                sr["allocated_damage_reductions"] = kept
            elif "allocated_damage_reductions" in sr:
                sr.pop("allocated_damage_reductions", None)
            unit.special_rules = sr

    def apply_command_phase_bearer_effect(self, source_unit, target_unit, spec: CommandPhaseBearerTargetSpec) -> bool:
        if source_unit is None or target_unit is None or spec is None:
            return False
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if spec.effect_key == "fell_back_shoot":
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["command_phase_fell_back_and_shoot_active"] = True
                sr["command_phase_fell_back_and_shoot_source"] = str(spec.ability_name or "")
                member.special_rules = sr
            return True
        if spec.effect_key == "damage_reduction":
            tag = f"command_phase_bearer_damage_reduction:{get_entity_id(source_unit)}:{spec.ability_name}"
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                entries = list(sr.get("allocated_damage_reductions", []) or [])
                kept = []
                for entry in entries:
                    if str(entry.get("tag", "") or "") == tag:
                        continue
                    kept.append(entry)
                kept.append(
                    {
                        "value": int(spec.effect_value),
                        "attack_type": "any",
                        "source": str(spec.ability_name or "Command phase effect"),
                        "op": "sub",
                        "tag": tag,
                    }
                )
                sr["allocated_damage_reductions"] = kept
                member.special_rules = sr
            return True
        return False

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_command_phase_bearer_effects()
        if self.army is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        sources = self.get_command_phase_bearer_sources()
        if not sources:
            return
        for entry in sources:
            source_unit = entry.get("source")
            spec = entry.get("spec")
            targets = self.get_command_phase_bearer_targets(source_unit, spec)
            if not targets:
                continue
            if len(targets) == 1:
                self.apply_command_phase_bearer_effect(source_unit, targets[0], spec)
                continue
            pending = self._pending_request_for_source_spec(game, source_unit, spec)
            if pending is None and game is not None:
                self.build_command_phase_bearer_request(game, player, source_unit, spec, targets)
                continue
            if pending is not None:
                continue
            choice = None
            try:
                ctx = {
                    "source": getattr(source_unit, "name", "") or "",
                    "ability": getattr(spec, "ability_name", "") or "",
                    "options": [getattr(t, "name", "") for t in targets],
                }
                choice = player._choose_optional_value("COMMAND_PHASE_BEARER_TARGET", list(targets), ctx)
            except Exception:
                choice = None
            if choice in targets:
                self.apply_command_phase_bearer_effect(source_unit, choice, spec)
            elif isinstance(choice, str):
                wanted = choice.strip().lower()
                for target in targets:
                    if str(getattr(target, "name", "") or "").strip().lower() == wanted:
                        self.apply_command_phase_bearer_effect(source_unit, target, spec)
                        break
