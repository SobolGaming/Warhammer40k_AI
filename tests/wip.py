import re

def parse_option_string(option: str, unit_ref: str):
    original_option = option
    model_name_1 = unit_ref.rstrip('s')
    model_name_2 = unit_ref.rstrip('s') + "asdf"
    if any(x in option for x in [" can be equipped with ", " can each be equipped with "]):
        parts = option.split(" be equipped with ")
        if len(parts) != 2:
            print(f"Invalid wargear option format: {option}")
            return
        parts[0] = parts[0].replace("can each", "").replace("can", "")

        model_description, item_description = parts
        model_count = None  # Changed to None as default
        
        # Handle "Any number of models" case
        if model_description.lower().startswith("any number of"):
            model_count = "any"
            model_description = "model"
        # Extract model count if specified
        elif model_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            model_count = int(model_description.split()[0])
            model_description = ' '.join(model_description.split()[1:])

        item_count = 1 # Default to 1 item
        # Extract item count if specified
        if item_description.startswith(('1 ', '2 ', '3 ', '4 ', '5 ', '6 ', '7 ', '8 ', '9 ')):
            item_count = int(item_description.split()[0])
            item_description = ' '.join(item_description.split()[1:]).strip().replace('.', '')

        # Parse "not equipped with" condition
        not_equipped_with = ''
        if "that is not equipped with" in model_description:
            model_parts = model_description.split("that is not equipped with")
            model_description = model_parts[0].strip()
            not_equipped_with = model_parts[1].strip()
            # Remove leading "a" or "an" from not_equipped_with
            if not_equipped_with.startswith("a "):
                not_equipped_with = not_equipped_with[2:].strip()
            elif not_equipped_with.startswith("an "):
                not_equipped_with = not_equipped_with[3:].strip()
        #print(f"{option}")
        parsed_result = {
            "condition": not_equipped_with,  # Now the condition will be properly included
            "model": model_description.strip(),
            "model_count": 100 if model_count == "any" else int(model_count) if model_count else 0,
            "original_item": [],
            "replacement_options": [item_description]
        }
        print(f" PARSED ADDITIONAL RESULT: {parsed_result}")
        #return WargearOption(WargearOptionType.ADDITIONAL, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])

    elif any(x in option for x in [" can be replaced with", " can each be replaced with", " can each have their "]):
        # Add handling for "Any number of models" at the start of pattern
        model = "model"
        if option.startswith("Any number of "):
            count = "any"
            option = option.replace("Any number of ", "")
            # Clean up the option string to match our expected format
            if " can each have their " in option:
                option = option.replace(" can each have their ", " ").replace(" replaced with ", " can be replaced with ")
        else:
            count = None  # Default count to None

        # Improved condition extraction
        condition = ""
        if option.startswith("If this unit"):
            condition_end = option.find(",")
            if condition_end != -1:
                condition = option[:condition_end].strip()
                option = option[condition_end + 1:].strip()
        elif option.startswith("For every"):  # Handle mid-sentence conditions
            condition_start = option.find("For every")
            condition_end = option.find(",", condition_start)
            if condition_end != -1:
                condition = option[condition_start:condition_end].strip()
                option = option[:condition_start].strip() + " " + option[condition_end + 1:].strip()
        elif option.startswith("Up to"):
            count_match = re.match(r"Up to (\d+)", option)
            if count_match:
                count = int(count_match.group(1))
                # Remove "Up to" and clean up the option string
                option = re.sub(r"^Up to \d+ models", f"{count} models", option)
                # Also handle the "can each have their" case
                if " can each have their " in option:
                    option = option.replace(" can each have their ", " ").replace(" replaced with ", " can be replaced with ")

        # some pre-pattern cleaning
        description = option.replace("’s", "'s").replace(",", " and")

        pattern = re.compile(
            r"(?P<model>(?:This model|The " + re.escape(model_name_1) + r"|The " + re.escape(model_name_2) + 
            r"|" + re.escape(model_name_1) + r" model|" + re.escape(model_name_2) + r" model|(?:\d+ )?(?:model|models|" + 
            re.escape(model_name_1) + r"s?|" + re.escape(model_name_2) + r"s?)))"
            # Modified to handle possessive cases with apostrophes
            r"(?:'s|\s+)(?P<original_item>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*) can(?:\s+each)? be replaced with(?:\s*:)?\s*"
            r"(?:"
                r"(?P<single_replacement>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:$|\.|\;))|"
                r"(?:(?P<first_replacement>(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*) and )?one of the following:\s*"
                r"(?P<replacement_options>(?:(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:;|,|\.)(?:\s*(?:\d+ )?[\w '\-]+(?:\s+and\s+(?:\d+ )?[\w '\-]+)*(?:;|,|\.)*)*))"
            r")"
        )
        
        # Match the pattern in the description
        match = pattern.search(description)
        
        if not match:
            print(f"DESCRIPTION: {description}, {model_name_1} {model_name_2}")
            print(f"REPLACEMENT MATCH FAILED - INVALID WARGEAR OPTION: {original_option}")
            return None
        
        # Extract the components and include condition in parsed_result
        model = match.group("model") or model
        original_item = match.group("original_item")
        single_replacement = match.group("single_replacement")
        replacement_options_str = match.group("replacement_options")
        
        # Process replacement options
        if single_replacement:
            options = [single_replacement]
        elif replacement_options_str:
            first_replacement = match.group("first_replacement")
            # Split by semicolon or comma followed by optional whitespace
            parts = re.split(r'[;,]\s*', replacement_options_str)
            options = [part.strip().rstrip('.') for part in parts if part.strip()]
            
            # If there's a first replacement, combine it with all other options
            if first_replacement:
                options = [f"{first_replacement} and {opt}" for opt in options]
        else:
            options = []
        
        # Clean up options
        options = [opt.strip().rstrip('.').replace(",", " and ") for opt in options if opt]
        replacement_options = []
        for specific_option in options:
            opt_lines = [item.strip() for item in specific_option.split(" and ")]
            results = []
            for opt in opt_lines:
                # Extract count if present, default to 1
                count_match = re.match(r'^(\d+)\s+(.+)$', opt)
                if count_match:
                    item_count, item_name = count_match.groups()
                    item_count = int(item_count)
                else:
                    item_count = 1
                    item_name = opt
                results.append(f"({item_count}) ({item_name.strip().lower()})")
            replacement_options.append(results)

        original_items = [item.strip() for item in original_item.split(" and ")]
        results = []
        for item in original_items:
            # Extract count if present, default to 1
            count_match = re.match(r'^(\d+)\s+(.+)$', item)
            if count_match:
                item_count, item_name = count_match.groups()
                item_count = int(item_count)
            else:
                item_count = 1
                item_name = item
            # Remove "number of models" from item name if present
            item_name = item_name.replace("number of models ", "")
            results.append(f"({item_count}) ({item_name.strip().lower()})")
        original_item = [results]

        parsed_result = {
            "condition": condition,  # Now the condition will be properly included
            "model": model.strip(),
            "model_count": 100 if count == "any" else int(count) if count else 1,
            "original_item": original_item,
            "replacement_options": replacement_options
        }
        #print(f"NOT IMPLEMENTED - WARGEAR ITEM REPLACEMENT: FULL STRING '{option}'")
        print(f"PARSED REPLACEMENT RESULT: {parsed_result}")
        #return WargearOption(WargearOptionType.REPLACEMENT, parsed_result["original_item"], parsed_result["replacement_options"], parsed_result["model"], parsed_result["model_count"], 1, parsed_result["condition"])
    else:
        print(f"INVALID WARGEAR OPTION: {original_option}")
        return None


# Example usage
descriptions = [
    ("This model’s shuriken cannon can be replaced with one of the following: 1 Aeldari missile launcher; 1 bright lance; 1 scatter laser; 1 starcannon.", ""),
    ("This model’s Phantom pulsar can be replaced with one of the following: 1 D-bombard; 2 Phantom starcannons and 1 wraith glaive; 1 Phantom starcannon, 1 pulse laser and 1 wraith glaive; 2 pulse lasers and 1 wraith glaive.", ""),
    ("The Tempestor Prime’s bolt pistol can be replaced with one of the following: 1 plasma pistol; 1 command rod.", "Tempestor Prime"),
    ("The Mukaali Rider Sergeant’s laspistol can be replaced with 1 plasma pistol.", "Mukaali Rider Sergeant"),
    ("For every 5 models in this unit, 1 model’s hunting lance can be replaced with 1 goad lance.", ""),
    ("If this unit contains 10 models, 1 Corsair Voidscarred’s Aeldari power sword can be replaced with 1 fusion pistol.", "Corsair Voidscarred"),
    ("This model’s great axe of Khorne can be replaced with 1 axe of Khorne and one of the following: 1 bloodflail; 1 lash of Khorne;", "Great Axe of Khorne", ""),
    ("This model’s big shootas can each be replaced with one of the following: 1 dread klaw; 1 kustom-mega blasta; 1 rokkit launcha; 1 skorcha;", ""),
    ("Any number of models can each be equipped with 1 killsaw.", ""),
    ("Any number of models can each have their twin big shoota replaced with one of the following: 1 kopta rockets; 1 kustom mega-blasta;", ""),
    ("This model’s 2 shieldbreaker missile launchers and twin siegebreaker cannon can be replaced with: 1 shieldbreaker missile launcher and 2 twin siegebreaker cannons;", ""),
    ("Any number of models can each have their guardian spear replaced with 1 sentinel blade and 1 praesidium shield.", "asdfasdf"),
    ("1 model’s guardian spear can be replaced with one of the following: 1 vexilla and 1 misericordia; 1 vexilla, 1 misericordia and 1 praesidium shield;", "asdfasdf"),
    ("Up to 2 models can each have their Servitor’s servo-arm replaced with one of the following: 1 heavy bolter and 1 Servitor’s tools; 1 multi-melta and 1 Servitor’s tools; 1 plasma cannon and 1 Servitor’s tools;", "SDFSDF"),
    ("1 Skitarii Ranger’s galvanic rifle can be replaced with 1 arc rifle.", "Skitarii Rangers"),
    ("Any number of Sicarian Ruststalkers can each have their transonic razor and chordclaw replaced with 1 transonic blades.", "Sicarian Ruststalkers"),
    ("For every 10 models in this unit, 1 Guardsman’s lasgun can be replaced with one of the following: 1 flamer; 1 grenade launcher; 1 meltagun; 1 plasma gun; 1 sniper rifle;", "Guardsman"),
    ("For every 5 models in this unit, up to 2 models can each have their boltgun and power weapon replaced with 1 Deathwatch thunder hammer.", "adasdfadsf"),
    ("1 skitarii ranger equipped with a galvanic rifle can be equipped with one of the following: 1 enhanced data-tether*; 1 omnispex*;", ""),
    ("the sicarian ruststalker princeps' transonic razor and chordclaw can be replaced with 1 transonic blades and chordclaw.", ""),
    ("this model can be equipped with one of the following: 1 howling banshee mask; 1 mandiblasters;", ""),
    ("up to 2 storm guardians can each have their shuriken pistol replaced with 1 guardian fusion gun.", ""),
    ("if this unit's dire avenger exarch is equipped with 1 avenger shuriken catapult, it can be equipped with 1 additional avenger shuriken catapult.", ""),
    ("all of the models in this unit can each have their wraithcannon replaced with 1 d-scythe.", ""),
    ("each model can have each shuriken cannon it is equipped with replaced with one of the following: 1 aeldari missile launcher; 1 bright lance; 1 scatter laser; 1 starcannon;", ""),
    ("each of this model's shuriken catapults can be replaced with 1 aeldari flamer.", ""),
    ("this model can be equipped with up to two of the following: 1 scatter laser; 1 shuriken cannon; 1 starcannon;", ""),
    ("2 of this model's heavy bolters can be replaced with one of the following: 2 autocannons; 2 lascannons;", ""),
    ("this model can be equipped with one of the following: 2 meltaguns; 2 additional heavy stubbers;", ""),
    ("if this model is equipped with 1 psychic gifts, its storm bolter can be replaced with 1 psycannon.", ""),
    ("1 pox rider that is not equipped with an instrument of chaos can be equipped with 1 daemonic icon.", ""),
    ("for each helbrute fist this model is equipped with, it can be equipped with one of the following: 1 combi-bolter; 1 heavy flamer;", ""),
    ("chaplain cassius is equipped with: artificer crozius; bolt pistol.", ""),
    ("this model can be equipped with 1 havoc launcher or can replace 1 combi-bolter with 1 havoc launcher.", ""),
]

def parse_alternate(description):
    description = description.replace("’", "'").lower()
    print(f"\nDESCRIPTION: {description}")

    condition = ""
    model_limit = ""
    item_limit = ""
    actor = ""
    base_wargear_qualifier = ""

    if description.startswith("the "):
        marker = description.find("'s ")
        if marker == -1:
            marker = description.find("' ")
        if marker != -1:
            actor = description[4:marker].strip()
            model_limit = "1"
            description = description[marker+3:].strip()

    if description.startswith("for every"):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("for each "):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
        if "model" in condition:
            actor = "model"

    if description.startswith("all of the models in this unit"):
        condition = "all or none"
        model_limit = "100"
        actor = "model"
        description = description[30:].strip()

    if description.startswith("if this unit contains"):
        marker = description.find(",")
        if marker != -1:
            condition = description[:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("if this unit's "):
        marker = description.find(",")
        start_marker = 0
        if marker != -1:
            model_marker = description.find("is equipped ")
            if model_marker != -1:
                actor = description[15:model_marker].strip()
                start_marker = model_marker
            condition = description[start_marker:marker].strip()
            description = description[marker+1:].strip()
    elif description.startswith("if this model is equipped with "):
        actor = "model"
        marker = description.find(",")
        if marker != -1:
            condition = description[17:marker].strip()
            description = description[marker+1:].strip()

    if description.startswith("up to "):
        marker = description.find("models")
        if marker != -1:
            parts = description[:marker+6].replace("up to ", "").split(" ")
            model_limit = parts[0]
            actor = parts[1]
            if actor[-1] == "s":
                actor = actor[:-1]
            description = description[marker+6:].strip()
        else:
            marker = description.find("can ")
            if marker != -1:
                model_limit, actor = description[5:marker].replace("up to ", "").strip().split(" ", 1)
                description = description[marker:].strip()
    if description.startswith("this model's"):
        actor = "model"
        model_limit = "1"
        description = description[13:].strip()
    if description.startswith("any number of") or description.startswith("any numbers of"):
        # address inconsistency
        if description.startswith("any numbers of"):
            description = description.replace("any numbers of", "any number of")
        marker = description.find("models")
        if marker != -1:
            model_limit = "any number of"
            actor = "model"
            if description[marker+6] == "'":
                description = description[marker+7:].strip()
            else:
                description = description[marker+6:].strip()
        else:
            marker = description.find("can each")
            if marker != -1:
                model_limit = "any number of"
                actor = description[14:marker].strip()
                description = description[marker+8:].strip()
    if "model's" in description:
        marker = description.find("model's")
        if marker != -1:
            actor = "model"
            if description.startswith("each of this "):
                condition = "per base wargear"
            elif " of this " in description[:marker]:
                base_wargear_qualifier = description[:marker].split(" of this ")[0].strip()
                model_limit = "1"
            else:
                model_limit = description[:marker].strip()
            description = description[marker+7:].strip()
    elif description.startswith("each model ") and "it is equipped with" in description:
        condition = "per base wargear"
        actor = "model"
        description = description[11:].strip()
        description = description.replace("it is equipped with", "")

    if not actor:
        marker = description.find("'")
        if marker != -1:
            parts = description[:marker].split(" ")
            model_limit = parts[0]
            if model_limit == "each":
                model_limit = "1"
                condition = "per model"
            actor = ' '.join(parts[1:]).strip()
            description = description[marker+2:].strip()

    replacement_options = []
    if "replaced with" in description:
        parts = description.split("replaced with")
        base_wargear = [parts[0].replace("can have each", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").replace("its ", "").strip()]
        replacement_options = parts[1].strip().replace(".", "")
    elif "is equipped with: " in description:
        actor, replacement_options = description.split("is equipped with")
        base_wargear = ""
        model_limit = "1"
    elif "equipped with" in description:
        what, replacement_options = description.rsplit("equipped with", 1)
        two_equipped_with = False
        if "not equipped with" in what:
            two_equipped_with = True
            what = what.replace("not equipped with an", "not equipped with a")
            who, what = what.rsplit("not equipped with a", 1)
            what = what.replace("can have each", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").replace("its ", "").strip()
            condition = "not equipped with [" + what + "]"
            what = ""
            model_limit, actor = who.split(" ", 1)
            actor = actor.replace("that is", "")
        elif "equipped with" in what:
            two_equipped_with = True
            what = what.replace("equipped with an", "equipped with a")
            who, what = what.rsplit("equipped with a", 1)
            model_limit, actor = who.split(" ", 1)
        elif "this model can be" in what:
            actor = "model"
            model_limit = "1"
            what = what.replace("this model can be", "").strip()
        elif what.startswith("the "):
            marker = what.find("can be ")
            if marker != -1:
                actor = what[4:marker].strip()
                what = what[marker+7:].strip()
        what = what.replace("it can be ", "").replace("can be ", "").replace("can each be ", "").replace("can each ", "").replace("have their ", "").strip()
        if what == "1 model":
            what = ""
            model_limit = "1"
            actor = "model"
        base_wargear = [what] if what else []
        if " additional " in replacement_options and two_equipped_with:
            model_limit, replacement_options = replacement_options.split(" additional ", 1)
        replacement_options = replacement_options.strip().replace(".", "").replace("additional ", "")

    if not replacement_options:
        return {}

    # adjust for inconsistency
    replacement_options = replacement_options.replace("1 of the following: ", "one of the following: ")
    replacement_options = replacement_options.replace("2 of the following: ", "two of the following: ")
    model_limit = model_limit.replace("one", "1").replace("two", "2")

    if "one of the following: " in replacement_options:
        item_limit = "1"
        marker = replacement_options.find("one of the following: ")
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1 and and_marker < marker:
            replacement_option_and = replacement_options[:and_marker]
            print(f"REPLACEMENT OPTION AND: {replacement_option_and}")
        replacement_options = replacement_options[marker+22:].rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options
    elif "two of the following: " in replacement_options:
        item_limit = "2"
        marker = replacement_options.find("two of the following: ")
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1 and and_marker < marker:
            replacement_option_and = replacement_options[:and_marker]
        replacement_options = replacement_options[marker+22:].rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options
    else:
        if replacement_options.startswith(":"):
            replacement_options = replacement_options[1:].replace(".",  "").strip()
        if replacement_options[-1] == ";":
            replacement_options = replacement_options[:-1]
        and_marker = replacement_options.find(" and ")
        replacement_option_and = None
        if and_marker != -1:
            replacement_option_and = replacement_options[:and_marker]
        replacement_options = replacement_options.rstrip(";")
        replacement_options = [item.replace(",", " and").strip() for item in replacement_options.split(";")]
        if replacement_option_and:
            new_replacement_options = []
            for item in replacement_options:
                new_replacement_options.append(replacement_option_and + " and " + item)
            replacement_options = new_replacement_options

    if base_wargear_qualifier:
        adjusted_base_wargear = []
        for base_wargear_item in base_wargear:
            adjusted_base_wargear.append(base_wargear_qualifier + " " + base_wargear_item)
        base_wargear = adjusted_base_wargear

    base_wargear = parse_wargear_item(base_wargear)
    replacement_options = parse_wargear_item(replacement_options)

    print(f"CONDITION: {condition}")
    print(f"MODEL LIMIT: {model_limit}")
    print(f"ACTOR: {actor}")
    print(f"BASE WARGEAR: {base_wargear}")
    print(f"ITEM LIMIT: {item_limit}")
    print(f"REPLACEMENT OPTIONS: {replacement_options}\n")

    parsed_result = {
        "condition": condition,  # Now the condition will be properly included
        "model": actor,
        "model_count": 100 if model_limit == "any number of" else int(model_limit) if model_limit else 1,
        "item_count": 100 if item_limit == "any number of" else int(item_limit) if item_limit else 1,
        "original_item": base_wargear,
        "replacement_options": replacement_options
    }

    return parsed_result

def parse_wargear_item(item_str: str):
    full_result = []
    for specific_option in item_str:
        opt_lines = [item.strip() for item in specific_option.split(" and ")]
        results = []
        for opt in opt_lines:
            # Extract count if present, default to 1
            count_match = re.match(r'^(\d+)\s+(.+)$', opt)
            if count_match:
                item_count, item_name = count_match.groups()
                item_count = int(item_count)
            else:
                item_count = 1
                item_name = opt
            results.append(f"({item_count}) ({item_name.strip().lower()})")
        full_result.append(results)
    return full_result

def parse_alternate_2():
    from collections import defaultdict
    starts_with_dict = defaultdict(list)
    with open("tmp.log", "r") as f:
        for line in f:
            description = line.replace("’", "'").replace(".", "").replace('model"s', "model's").replace("for every four models", "for every 4 models").lower()

            #if description.startswith("each of this model's"):
            #    starts_with_dict["each of this model's"].append(description)
            if description.startswith("this model's"):
                starts_with_dict["this model's"].append(description)
            elif description.startswith("1 model's") or description.startswith("one model's"):
                starts_with_dict["1 model's"].append(description)
            elif description.startswith("this model can be"):
                starts_with_dict["this model can be"].append(description)
            elif description.startswith("1 model can be") or description.startswith("one model can be:"):
                starts_with_dict["1 model can be"].append(description)
            elif description.startswith("1 model in this unit"):
                starts_with_dict["1 model in this unit"].append(description)
            elif description.startswith("this unit can be"):
                starts_with_dict["this unit can be"].append(description)
            #elif description.startswith("any number of models can each have their"):
            #    starts_with_dict["any number of models can each have their"].append(description)
            #elif description.startswith("any number of models can each be"):
            #    starts_with_dict["any number of models can each be"].append(description)
            #elif description.startswith("any number of models can each"):
            #    starts_with_dict["any number of models can each"].append(description)
            #elif description.startswith("any number of models can be"):
            #    starts_with_dict["any number of models can be"].append(description)
            #elif description.startswith("any number of models'") or description.startswith("any numbers of models'"):
            #    starts_with_dict["any number of models'"].append(description)
            elif description.startswith("all models in this unit can each have their"):
                starts_with_dict["all models in this unit can each have their"].append(description)
            elif description.startswith("all models in this unit can each be"):
                starts_with_dict["all models in this unit can each be"].append(description)
            elif description.startswith("all of the models in this unit can each have"):
                starts_with_dict["all of the models in this unit can each have"].append(description)
            elif description.startswith("one model equipped with a") or description.startswith("1 model equipped with a"):
                starts_with_dict["1 model equipped with a"].append(description)
            elif description.startswith("if this model is equipped with"):
                starts_with_dict["if this model is equipped with"].append(description)
            elif description.startswith("if this model is not equipped with"):
                starts_with_dict["if this model is not equipped with"].append(description)
            elif description.startswith("this model can each be equipped with"):
                starts_with_dict["this model can each be equipped with"].append(description)
            elif description.startswith("one model can replace its"):
                starts_with_dict["one model can replace its"].append(description)
            elif description.startswith("this model can do one of the following"):
                starts_with_dict["this model can do one of the following"].append(description)
            elif description.startswith("this model must be equipped with one of the following"):
                starts_with_dict["this model must be equipped with one of the following"].append(description)
            elif description.startswith("this unit's"):
                starts_with_dict["this unit's"].append(description)
            elif description.startswith("*") or description.startswith("this weapon cannot be replaced") or description.startswith("to a maximum of"):
                starts_with_dict["*"].append(description)
            elif re.match(r"^for every \d+ models in th[ei]s? unit[,:]", description):
                starts_with_dict["for every X models in this unit"].append(description)
            elif re.match(r"^for every \d+ [\w\s']+ in th[ei]s? unit[,:]", description):
                starts_with_dict["for every X Y in this unit"].append(description)
            elif re.match(r"^the [\w\s'-]+ can be", description):
                starts_with_dict["the X can be"].append(description)
            elif re.match(r"^the [\w\s'-]+ can replace its", description):
                starts_with_dict["the X can replace its"].append(description)
            elif re.match(r"^up to \d+ models can each", description):
                starts_with_dict["up to X models can each"].append(description)
            elif re.match(r"^up to \d+ [\w\s']+ can each have their", description):
                starts_with_dict["up to X Y can each have their"].append(description)
            elif re.match(r"^any number of [\w\s']+ can each have their", description):
                starts_with_dict["any number of X can each have their"].append(description)
            elif re.match(r"^any numbers? of [\w\s'-]+ can", description):
                #print(f"ANY NUMBER OF X CAN: {description}")
                starts_with_dict["any number of X can"].append(description)
            elif re.match(r"^[\w\s']+ is equipped with:", description):
                starts_with_dict["X is equipped with:"].append(description)
            elif re.match(r"^1 [\w\s'-]+ can be equipped with", description):
                starts_with_dict["1 X can be equipped with"].append(description)
            elif re.match(r"^one [\w\s'-]+ equipped with", description):
                starts_with_dict["one X equipped with"].append(description)
            elif re.match(r"^1 [\w\s'-]+ can be replaced with", description) or re.match(r"^one [\w\s'-]+ can be replaced with", description):
                starts_with_dict["1 X can be replaced with"].append(description)
            elif re.match(r"^each [\w\s'-]+ can be", description):
                starts_with_dict["each X can be"].append(description)
            elif re.match(r"^\d+ [\w\s']+ can have its", description):
                starts_with_dict["X can have its"].append(description)
            elif re.match(r"^if this unit's [\w\s'-]+ is equipped with", description):
                starts_with_dict["if this unit's X is equipped with"].append(description)
            elif re.match(r"^if this unit contains \d+ models,", description):
                starts_with_dict["if this unit contains X models"].append(description)
            elif re.match(r"^\d+ of this model's", description):
                starts_with_dict["X of this model's"].append(description)
            elif re.match(r"^all [\w\s'-]+ in this unit can each have their", description):
                starts_with_dict["all X in this unit can each have their"].append(description)
            elif re.match(r"^for each [\w\s'-]+ this model is equipped with", description):
                starts_with_dict["for each X this model is equipped with"].append(description)
            elif re.match(r"^the [\w\s'-]+ can do one of the following:", description):
                starts_with_dict["the X can do one of the following:"].append(description)
            elif re.match(r"^an [\w\s'-]+ can be replaced with", description):
                starts_with_dict["an X can be replaced with"].append(description)
            elif re.match(r"^each model can have each [\w\s'-]+ it is equipped with replaced with", description):
                starts_with_dict["each model can have each X it is equipped with replaced with"].append(description)
            elif re.match(r"^if this unit contains \d+ or fewer models", description):
                starts_with_dict["if this unit contains X or fewer models"].append(description)
            elif re.match(r"^if this unit contains \d+ or more models", description):
                starts_with_dict["if this unit contains X or more models"].append(description)
            elif re.match(r"^if the [\w\s'-]+ is equipped with [\w\s'-]+, it can be equipped with", description):
                starts_with_dict["if the X is equipped with Y, it can be equipped with"].append(description)
            elif re.match(r"^up to \d+ different models that are not equipped with either an?", description):
                starts_with_dict["up to X different models that are not equipped with either an?"].append(description)
            elif re.match(r"^up to \d+ different [\w\s'-]+ equipped with either an?", description):
                starts_with_dict["up to X different Y equipped with either an?"].append(description)
            elif re.match(r"^up to \d+ [\w\s'-]+ can each replace their", description):
                starts_with_dict["up to X Y can each replace their"].append(description)
            elif re.match(r"^both of this model's [\w\s'-]+ can be replaced with", description):
                starts_with_dict["both of this model's X can be replaced with"].append(description)
            else:
                print(f"UNKNOWN: {description}")
                starts_with_dict["unknown"].append(description)

    for key, value in sorted(starts_with_dict.items()):
        print(f"{key}: {len(value)}")

for description in descriptions:
    #parse_option_string(description[0], description[1])
    pass

parse_alternate_2()
