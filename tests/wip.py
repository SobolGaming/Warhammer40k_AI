import re

def parse_wargear_replacement(description):
    description = description.replace("’", "'")
    pattern = re.compile(
        # Modified condition pattern to better handle both conditional cases
        r"(?:(?P<condition>(?:For every \d+ models in this unit|If this unit contains \d+ models),?\s*))*"
        # Modified model pattern to handle numbered models
        r"(?P<model>(?:This model|The [\w\s\u00C0-\u017F]+|[\w\s\u00C0-\u017F]+ model|(?:\d+ )?[\w\s\u00C0-\u017F]+))"
        # Made the possessive 's optional and separated from the plural s
        r"(?:'s)?(?:\s+)(?P<original_item>[\w \-]+) can be replaced with "  # Original item
        r"(?:"  # Start of replacement options group
            r"(?P<single_replacement>(?:\d+ )?[\w \-]+)(?:$|\.)|"  # Single replacement option
            r"(?:(?P<first_replacement>(?:\d+ )?[\w \-]+) and )?one of the following:\s*"  # Optional first replacement
            r"(?P<replacement_options>(?:(?:\d+ )?[\w \-]+(?:;|,|\.)(?:\s*(?:\d+ )?[\w \-]+(?:;|,|\.)*)*))"  # List of options
        r")"  # End of replacement options group
    )
    
    # Match the pattern in the description
    match = pattern.search(description)
    
    if not match:
        return None
    
    # Extract the components
    condition = match.group("condition") or ""
    model = match.group("model")
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
    options = [opt.strip().rstrip('.') for opt in options if opt]
    
    return {
        "condition": condition.strip(),
        "model": model.strip(),
        "original_item": original_item.strip(),
        "replacement_options": options
    }

# Example usage
descriptions = [
    "This model’s shuriken cannon can be replaced with one of the following: 1 Aeldari missile launcher; 1 bright lance; 1 scatter laser; 1 starcannon.",
    "This model’s Phantom pulsar can be replaced with one of the following: 1 D-bombard; 2 Phantom starcannons and 1 wraith glaive; 1 Phantom starcannon, 1 pulse laser and 1 wraith glaive; 2 pulse lasers and 1 wraith glaive.",
    "The Tempestor Prime’s bolt pistol can be replaced with one of the following: 1 plasma pistol; 1 command rod.",
    "The Mukaali Rider Sergeant’s laspistol can be replaced with 1 plasma pistol.",
    "For every 5 models in this unit, 1 model’s hunting lance can be replaced with 1 goad lance.",
    "If this unit contains 10 models, 1 Corsair Voidscarred’s Aeldari power sword can be replaced with 1 fusion pistol.",
    "This model’s great axe of Khorne can be replaced with 1 axe of Khorne and one of the following: 1 bloodflail; 1 lash of Khorne;"
]

for description in descriptions:
    result = parse_wargear_replacement(description)
    print(result)
