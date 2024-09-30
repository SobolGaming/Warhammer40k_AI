import json
import os
import re
import unicodedata
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from types import SimpleNamespace

# Suppress the specific warnings at the module level
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class WahaHelper:
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
        self.load_data()

    def clean_data(self, data):
        if isinstance(data, dict):
            return {k: self.clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.clean_data(item) for item in data]
        elif isinstance(data, str):
            soup = BeautifulSoup(data, 'html.parser')
            text = soup.get_text(separator=' ')
            text = re.sub(r'\s+', ' ', text).strip()
            text = re.sub(r'\s+([,.])', r'\1', text)
            return text
        else:
            return data

    def load_data(self):
        if not os.path.exists(self.data_dir):
            print(f"Error: Directory '{self.data_dir}' does not exist.")
            return

        self.load_json_file('Abilities.json', self.abilities)
        self.load_json_file('Stratagems.json', self.stratagems)
        self.load_json_file('Enhancements.json', self.enhancements)
        self.load_json_file('Source.json', self.sources)
        self.load_json_file('Factions.json', self.factions)
        self.load_json_file('Detachment_abilities.json', self.detachment_abilities)

        self.load_datasheets_enhancements()

        datasheets_path = os.path.join(self.data_dir, 'Datasheets.json')
        if not os.path.exists(datasheets_path):
            print(f"Error: Datasheets.json not found in {self.data_dir}")
            return

        try:
            with open(datasheets_path, 'r', encoding='utf-8') as f:
                datasheets = json.load(f)
            self.datasheets = {sheet['id']: self.clean_data(sheet) for sheet in datasheets}
            self.merge_additional_data()
        except Exception as e:
            print(f"Error loading data: {str(e)}")

    def load_json_file(self, filename, target_dict):
        file_path = os.path.join(self.data_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            target_dict.update({item['id']: self.clean_data(item) for item in data})
        else:
            print(f"Warning: {filename} not found in {self.data_dir}")

    def load_datasheets_enhancements(self):
        file_path = os.path.join(self.data_dir, 'Datasheets_enhancements.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                datasheet_id = item['datasheet_id']
                if datasheet_id not in self.datasheets_enhancements:
                    self.datasheets_enhancements[datasheet_id] = []
                self.datasheets_enhancements[datasheet_id].append(item['enhancement_id'])
        else:
            print(f"Warning: Datasheets_enhancements.json not found in {self.data_dir}")

    def merge_additional_data(self):
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.json') and filename not in ['Datasheets.json', 'Abilities.json', 'Stratagems.json', 'Enhancements.json', 'Datasheets_enhancements.json', 'Source.json', 'Factions.json', 'Detachment_abilities.json']:
                file_path = os.path.join(self.data_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for item in data:
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

        # Add source data
        for datasheet in self.datasheets.values():
            if 'source_id' in datasheet and datasheet['source_id'] in self.sources:
                datasheet['source_data'] = self.sources[datasheet['source_id']]

        # Add faction data
        for datasheet in self.datasheets.values():
            if 'faction_id' in datasheet and datasheet['faction_id'] in self.factions:
                datasheet['faction_data'] = self.factions[datasheet['faction_id']]

    def strip_special_chars(self, text):
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        # Remove diacritics
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        # Remove all non-alphanumeric characters except spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Convert to lowercase and strip
        return text.lower().strip()

    def get_datasheet(self, name):
        """
        Returns a specific datasheet by name, using case-insensitive and partial matching.
        Also aggregates keywords and faction keywords.
        """
        normalized_name = self.strip_special_chars(name)
        
        for datasheet in self.datasheets.values():
            if 'name' in datasheet:
                normalized_datasheet_name = self.strip_special_chars(datasheet['name'])
                if normalized_name in normalized_datasheet_name:
                    result = SimpleNamespace(**datasheet)
                    if 'datasheets_keywords' in datasheet:
                        keywords, faction_keywords = self.aggregate_keywords(datasheet['datasheets_keywords'])
                        result.keywords = keywords
                        result.faction_keywords = faction_keywords
                    return result
        return None

    def get_full_datasheet_info_by_name(self, name):
        """
        Returns the full datasheet information for a given name.
        This method is an alias for get_datasheet to match the expected method name in the test.
        """
        return self.get_datasheet(name)

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

    def get_all_datasheet_names(self):
        return [datasheet['name'] for datasheet in self.datasheets.values()]

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

# Add this function outside of the WahaHelper class
def get_all_data():
    helper = WahaHelper()
    return helper.get_all_data()

def main():
    print("Starting main function...")
    
    # Create an instance of WahaHelper
    waha = WahaHelper()

    # Get a specific datasheet by name
    datasheet = waha.get_datasheet("Bloodletters")
    if datasheet:
        print(json.dumps(datasheet, indent=2, ensure_ascii=False))
    else:
        print("Datasheet not found")

    # If the above search fails, try a broader search
    if not datasheet:
        print("\nPerforming a broader search:")
        results = waha.search_datasheets("Bloodletters")
        print(f"Search results: {results}")

    print("Main function completed.")

if __name__ == "__main__":
    main()
