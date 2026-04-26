import json
import os
import re
import unicodedata
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from types import SimpleNamespace
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.ability import Ability
import logging
from ..utility.text_normalization import normalize_display_text
logger = logging.getLogger(__name__)

# Suppress the specific warnings at the module level
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


class WahaDataError(RuntimeError):
    """Raised when structured Wahapedia data cannot be loaded or parsed."""


class WahaHelper:
    _DATA_CACHE: dict[str, dict] = {}
    _MANDATORY_JSON_FILES = (
        "Abilities.json",
        "Stratagems.json",
        "Enhancements.json",
        "Source.json",
        "Factions.json",
        "Detachment_abilities.json",
        "Datasheets_leader.json",
        "Datasheets_enhancements.json",
        "Datasheets.json",
    )

    def __init__(self, data_dir='wahapedia_data'):
        self.data_dir = data_dir
        self.datasheets = {}
        self.abilities = {}
        self.stratagems = {}
        self.enhancements = {}
        self.datasheets_enhancements = {}
        self.sources = {}
        self.factions = {}
        self.detachment_abilities = {}
        self.datasheets_leaders = {}
        cache_key = os.path.abspath(str(self.data_dir or "wahapedia_data"))
        cached = WahaHelper._DATA_CACHE.get(cache_key)
        if isinstance(cached, dict):
            self._apply_cached_payload(cached)
            return
        self.load_data()
        WahaHelper._DATA_CACHE[cache_key] = self._cache_payload()

    def _cache_payload(self) -> dict:
        return {
            "datasheets": self.datasheets,
            "abilities": self.abilities,
            "stratagems": self.stratagems,
            "enhancements": self.enhancements,
            "datasheets_enhancements": self.datasheets_enhancements,
            "sources": self.sources,
            "factions": self.factions,
            "detachment_abilities": self.detachment_abilities,
            "datasheets_leaders": self.datasheets_leaders,
        }

    def _apply_cached_payload(self, payload: dict) -> None:
        self.datasheets = dict(payload.get("datasheets", {}) or {})
        self.abilities = dict(payload.get("abilities", {}) or {})
        self.stratagems = dict(payload.get("stratagems", {}) or {})
        self.enhancements = dict(payload.get("enhancements", {}) or {})
        self.datasheets_enhancements = dict(payload.get("datasheets_enhancements", {}) or {})
        self.sources = dict(payload.get("sources", {}) or {})
        self.factions = dict(payload.get("factions", {}) or {})
        self.detachment_abilities = dict(payload.get("detachment_abilities", {}) or {})
        self.datasheets_leaders = dict(payload.get("datasheets_leaders", {}) or {})

    def clean_data(self, data):
        if isinstance(data, dict):
            return {k: self.clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.clean_data(item) for item in data]
        elif isinstance(data, str):
            # Only process with BeautifulSoup if the string contains HTML tags
            if '<' in data and '>' in data:
                data = data.replace("</li>", ";")
                soup = BeautifulSoup(data, 'html.parser')
                text = soup.get_text(separator=' ')
                return normalize_display_text(text)
            else:
                # For plain text strings, just clean up whitespace
                return normalize_display_text(data)
        else:
            return data

    def load_data(self):
        if not os.path.isdir(self.data_dir):
            raise WahaDataError(f"Wahapedia data directory does not exist: {self.data_dir}")

        for filename in self._MANDATORY_JSON_FILES:
            file_path = os.path.join(self.data_dir, filename)
            if not os.path.isfile(file_path):
                raise WahaDataError(f"Mandatory Wahapedia data file is missing: {file_path}")

        self.load_json_file('Abilities.json', self.abilities, 'id')
        self.load_json_file('Stratagems.json', self.stratagems, 'id')
        self.load_json_file('Enhancements.json', self.enhancements, 'id')
        self.load_json_file('Source.json', self.sources, 'id')
        self.load_json_file('Factions.json', self.factions, 'id')
        self.load_json_file('Detachment_abilities.json', self.detachment_abilities, 'id')
        # Datasheets_leader.json is a many-to-one relationship (leader_id -> many attached_id),
        # so it must be aggregated (not overwritten by key).
        self.load_datasheets_leaders()
        self.load_datasheets_enhancements()

        datasheets = self._load_json_list('Datasheets.json')
        filtered_datasheets: dict[str, dict] = {}
        for index, sheet in enumerate(datasheets):
            if not isinstance(sheet, dict):
                raise WahaDataError(f"Datasheets.json row {index} must be an object")
            cleaned_sheet = self.clean_data(sheet)
            source_id = str(cleaned_sheet.get("source_id", "") or "").strip()
            source_row = self.sources.get(source_id) if source_id else None
            if self._source_is_excluded(source_row):
                continue
            ds_id = str(cleaned_sheet.get("id", "") or "").strip()
            if not ds_id:
                raise WahaDataError(f"Datasheets.json row {index} is missing required id")
            filtered_datasheets[ds_id] = cleaned_sheet
        self.datasheets = filtered_datasheets
        self.merge_additional_data()

    @staticmethod
    def _source_is_excluded(source_row) -> bool:
        if not isinstance(source_row, dict):
            return False
        source_name = str(source_row.get("name", "") or "").strip().lower()
        source_type = str(source_row.get("type", "") or "").strip().lower()
        if "(forge world)" in source_name or "legends" in source_name or "warhammer 40,000:" in source_name:
            return True
        if source_type == "boarding actions" or source_name == "boarding actions":
            return True
        return False

    def get_stratagems_for_faction(self, faction_id: str | None = None, detachment: str | None = None) -> list[dict]:
        """
        Return a list of stratagem dicts that apply to the provided faction_id and detachment.

        - Global stratagems have empty "faction_id" in source data and always apply.
        - Faction-specific stratagems require faction_id to match; if a detachment string is
          present on the stratagem, it must match the provided detachment.
        - Matching is case-insensitive and whitespace-normalized to handle mixed-casing IDs
          present in source data (e.g. AoI, LoV, AdM).
        """
        def _norm_token(value: str | None) -> str:
            return str(value or "").strip().upper()

        def _norm_text(value: str | None) -> str:
            return re.sub(r"\s+", " ", str(value or "").strip()).upper()

        wanted_faction = _norm_token(faction_id)
        wanted_detachment = _norm_text(detachment)
        results: list[dict] = []
        for s in self.stratagems.values():
            try:
                s_faction = _norm_token(s.get('faction_id', '') or '')
                s_det = _norm_text(s.get('detachment', '') or '')
                is_global = s_faction == ''
                if is_global:
                    results.append(s)
                    continue
                if wanted_faction and s_faction == wanted_faction:
                    if s_det:
                        if not wanted_detachment or s_det == wanted_detachment:
                            results.append(s)
                    else:
                        results.append(s)
            except Exception:
                continue
        return results

    def _load_json_list(self, filename: str) -> list:
        file_path = os.path.join(self.data_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise WahaDataError(f"Invalid JSON in {file_path}: {exc.msg}") from exc
        except OSError as exc:
            raise WahaDataError(f"Unable to read Wahapedia data file {file_path}: {exc}") from exc
        if not isinstance(data, list):
            raise WahaDataError(f"{filename} must contain a JSON list")
        return data

    def load_json_file(self, filename, target_dict, key):
        data = self._load_json_list(filename)
        loaded = {}
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise WahaDataError(f"{filename} row {index} must be an object")
            if key not in item or str(item.get(key, "") or "").strip() == "":
                raise WahaDataError(f"{filename} row {index} is missing required {key!r}")
            loaded[item[key]] = self.clean_data(item)
        target_dict.update(loaded)

    def load_datasheets_leaders(self) -> None:
        """Load leader->bodyguard relationships (many attached_id per leader_id)."""
        data = self._load_json_list('Datasheets_leader.json')

        self.datasheets_leaders = {}
        for index, item in enumerate(data or []):
            if not isinstance(item, dict):
                raise WahaDataError(f"Datasheets_leader.json row {index} must be an object")
            if 'leader_id' not in item or 'attached_id' not in item:
                raise WahaDataError(f"Datasheets_leader.json row {index} must contain leader_id and attached_id")
            leader_id = self.clean_data(item.get('leader_id'))
            attached_id = self.clean_data(item.get('attached_id'))
            if not leader_id or not attached_id:
                raise WahaDataError(f"Datasheets_leader.json row {index} has blank leader_id or attached_id")
            self.datasheets_leaders.setdefault(leader_id, []).append(attached_id)

        # Deduplicate while preserving order
        for leader_id, attached_ids in list(self.datasheets_leaders.items()):
            seen = set()
            deduped = []
            for aid in attached_ids:
                if aid in seen:
                    continue
                seen.add(aid)
                deduped.append(aid)
            self.datasheets_leaders[leader_id] = deduped

    def load_datasheets_enhancements(self):
        data = self._load_json_list('Datasheets_enhancements.json')
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise WahaDataError(f"Datasheets_enhancements.json row {index} must be an object")
            if 'datasheet_id' not in item or 'enhancement_id' not in item:
                raise WahaDataError(
                    f"Datasheets_enhancements.json row {index} must contain datasheet_id and enhancement_id"
                )
            datasheet_id = self.clean_data(item['datasheet_id'])
            enhancement_id = self.clean_data(item['enhancement_id'])
            if not datasheet_id or not enhancement_id:
                raise WahaDataError(
                    f"Datasheets_enhancements.json row {index} has blank datasheet_id or enhancement_id"
                )
            if datasheet_id not in self.datasheets_enhancements:
                self.datasheets_enhancements[datasheet_id] = []
            self.datasheets_enhancements[datasheet_id].append(enhancement_id)

    def merge_additional_data(self):
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.json') and filename not in ['Datasheets.json', 'Abilities.json', 'Stratagems.json', 'Enhancements.json', 'Datasheets_enhancements.json', 'Source.json', 'Factions.json', 'Detachment_abilities.json']:
                data = self._load_json_list(filename)
                
                for index, item in enumerate(data):
                    if not isinstance(item, dict):
                        raise WahaDataError(f"{filename} row {index} must be an object")
                    if 'datasheet_id' in item and item['datasheet_id'] in self.datasheets:
                        datasheet = self.datasheets[item['datasheet_id']]
                        key = filename[:-5].lower()
                        if key not in datasheet:
                            datasheet[key] = []
                        cleaned_item = self.clean_data(item)
                        
                        if key == 'datasheets_abilities' and 'ability_id' in cleaned_item:
                            ability_id = cleaned_item['ability_id']
                            if ability_id in self.abilities:
                                cleaned_item['ability_data'] = self.abilities[ability_id]
                        
                        if key == 'datasheets_stratagems' and 'stratagem_id' in cleaned_item:
                            stratagem_id = cleaned_item['stratagem_id']
                            if stratagem_id in self.stratagems:
                                cleaned_item['stratagem_data'] = self.stratagems[stratagem_id]
                        
                        if key == 'datasheets_detachment_abilities' and 'detachment_ability_id' in cleaned_item:
                            detachment_ability_id = cleaned_item['detachment_ability_id']
                            if detachment_ability_id in self.detachment_abilities:
                                cleaned_item['detachment_ability_data'] = self.detachment_abilities[detachment_ability_id]
                        
                        datasheet[key].append(cleaned_item)

        for datasheet_id, enhancement_ids in self.datasheets_enhancements.items():
            if datasheet_id in self.datasheets:
                datasheet = self.datasheets[datasheet_id]
                datasheet['enhancements'] = []
                for enhancement_id in enhancement_ids:
                    if enhancement_id in self.enhancements:
                        datasheet['enhancements'].append(self.enhancements[enhancement_id])

        # Add source and faction data
        for datasheet in self.datasheets.values():
            if 'source_id' in datasheet and datasheet['source_id'] in self.sources:
                datasheet['source_data'] = self.sources[datasheet['source_id']]
            if 'faction_id' in datasheet and datasheet['faction_id'] in self.factions:
                datasheet['faction_data'] = self.factions[datasheet['faction_id']]
            if 'id' in datasheet and datasheet['id'] in self.datasheets_leaders:
                attached_ids = [
                    aid for aid in list(self.datasheets_leaders[datasheet['id']])
                    if aid in self.datasheets
                ]
                datasheet['attached_to'] = attached_ids
                attached_names = []
                seen_names = set()
                for aid in attached_ids:
                    name = self.datasheets.get(aid, {}).get('name')
                    if not name:
                        continue
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    attached_names.append(name)
                datasheet['attached_to_names'] = attached_names

    def strip_special_chars(self, text: str) -> str:
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        # Remove diacritics
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        # Remove all non-alphanumeric characters except spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Convert to lowercase and strip
        return text.lower().strip()

    def get_datasheet(self, name: str, datasheet_id: str = None, faction_id: str = None):
        """
        Returns a specific datasheet by name, using case-insensitive and partial matching.
        Also aggregates keywords and faction keywords.
        
        Args:
            name: The name of the datasheet to search for
            datasheet_id: Optional specific datasheet ID to match
            faction_id: Optional faction ID to ensure correct faction match
        """
        normalized_name = self.strip_special_chars(name)
        
        matches = []
        for datasheet in self.datasheets.values():
            if 'name' in datasheet:
                normalized_datasheet_name = self.strip_special_chars(datasheet['name'])
                name_matches = normalized_name in normalized_datasheet_name
                id_matches = datasheet_id is None or datasheet['id'] == datasheet_id
                faction_matches = faction_id is None or datasheet.get('faction_id') == faction_id
                
                if name_matches and id_matches and faction_matches:
                    matches.append((datasheet, normalized_datasheet_name))
        if matches:
            requested_legendary = "legendary" in normalized_name or "legends" in normalized_name
            non_legend_matches = [
                item
                for item in matches
                if "legendary" not in item[1] and "legends" not in item[1]
            ]
            if datasheet_id is None and not requested_legendary and non_legend_matches:
                matches = non_legend_matches
            matches.sort(
                key=lambda item: (
                    0 if item[1] == normalized_name else 1,
                    1 if ("legendary" in item[1] or "legends" in item[1]) else 0,
                    str(item[0].get("id", "")),
                )
            )
            datasheet = matches[0][0]
            result = SimpleNamespace(**datasheet)
            if 'datasheets_keywords' in datasheet:
                keywords, faction_keywords = self.aggregate_keywords(datasheet['datasheets_keywords'])
                result.keywords = keywords
                result.faction_keywords = faction_keywords
            return result
        return None

    def get_full_datasheet_info_by_name(self, name: str, datasheet_id: str = None, faction_id: str = None):
        """
        Returns the full datasheet information for a given name.
        This method is an alias for get_datasheet to match the expected method name in the test.
        """
        return self.get_datasheet(name, datasheet_id, faction_id)

    def search_datasheets(self, query):
        """
        Searches for datasheets containing the query string.
        """
        query = self.strip_special_chars(query)
        results = []
        for datasheet in self.datasheets.values():
            if 'name' in datasheet:
                normalized_name = self.strip_special_chars(datasheet['name'])
                if query in normalized_name:
                    results.append(datasheet['name'])
        return results

    def get_datasheets_by_name(self, name: str):
        """
        Returns all datasheets with the given name, grouped by faction.
        Useful for debugging when multiple datasheets exist with the same name.
        """
        normalized_name = self.strip_special_chars(name)
        results = {}
        
        for datasheet in self.datasheets.values():
            if 'name' in datasheet:
                normalized_datasheet_name = self.strip_special_chars(datasheet['name'])
                if normalized_name in normalized_datasheet_name:
                    faction_id = datasheet.get('faction_id', 'Unknown')
                    if faction_id not in results:
                        results[faction_id] = []
                    results[faction_id].append({
                        'id': datasheet['id'],
                        'name': datasheet['name'],
                        'faction_id': faction_id,
                        'source_id': datasheet.get('source_id', ''),
                        'role': datasheet.get('role', '')
                    })
        
        return results

    def get_all_datasheet_names(self):
        return [(datasheet['name'], datasheet['id']) for datasheet in self.datasheets.values()]

    def get_all_data(self):
        """
        Returns all datasheets.
        """
        return self.datasheets

    def aggregate_keywords(self, keywords_list):
        keywords = []
        faction_keywords = []
        for keyword in keywords_list:
            if isinstance(keyword, dict) and 'keyword' in keyword and 'is_faction_keyword' in keyword:
                if keyword['is_faction_keyword'] == "true":
                    faction_keywords.append(keyword['keyword'])
                else:
                    keywords.append(keyword['keyword'])
        return keywords, faction_keywords

    def get_enhancement(self, enhancement_id: str) -> Enhancement:
        """
        Returns an Enhancement object for the given enhancement name.
        """
        if enhancement_id in self.enhancements:
            enhancement_data = self.enhancements[enhancement_id]
            try:
                return Enhancement.from_waha_dict(enhancement_data)
            except (KeyError, TypeError, ValueError) as exc:
                raise WahaDataError(f"Error parsing enhancement id {enhancement_id}: {exc}") from exc
        return None

    def get_enhancement_by_name(self, name: str) -> Enhancement:
        """
        Returns an Enhancement object for the given enhancement name.
        """
        for enhancement in self.enhancements.values():
            if self.strip_special_chars(enhancement['name']) == self.strip_special_chars(name):
                try:
                    return Enhancement.from_waha_dict(enhancement)
                except (KeyError, TypeError, ValueError) as exc:
                    enh_name = enhancement.get("name", "") or name
                    raise WahaDataError(f"Error parsing enhancement {enh_name}: {exc}") from exc
        return None

    def get_ability(self, ability_id: str) -> Ability:
        """
        Returns an Ability object for the given ability name.
        """
        if ability_id in self.abilities:
            ability_data = self.abilities[ability_id]
            return Ability(
                name=ability_data['name'],
                legend=ability_data.get('legend', ''),
                description=ability_data.get('description', ''),
                type=ability_data.get('type', ''),
                parameter=ability_data.get('parameter', '')
            )
        return None

# Add this function outside of the WahaHelper class
def get_all_data():
    helper = WahaHelper()
    return helper.get_all_data()

def main():
    logger.info("Starting main function...")
    
    # Create an instance of WahaHelper
    waha = WahaHelper()

    # Get a specific datasheet by name
    datasheet = waha.get_datasheet("Bloodletters")
    if datasheet:
        logger.info(json.dumps(datasheet, indent=2, ensure_ascii=False))
    else:
        logger.info("Datasheet not found")

    # If the above search fails, try a broader search
    if not datasheet:
        logger.info("\nPerforming a broader search:")
        results = waha.search_datasheets("Bloodletters")
        logger.info(f"Search results: {results}")

    logger.info("Main function completed.")

if __name__ == "__main__":
    main()
