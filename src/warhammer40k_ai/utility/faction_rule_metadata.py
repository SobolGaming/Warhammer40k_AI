from __future__ import annotations

FACTION_RULE_METADATA: dict[str, dict[str, object]] = {
    "AS": {
        "faction_name": "Adepta Sororitas",
        "army_rules": ["Acts of Faith"],
        "restrictions": [],
    },
    "AC": {
        "faction_name": "Adeptus Custodes",
        "army_rules": ["Martial Ka'tah"],
        "restrictions": [],
    },
    "ADM": {
        "faction_name": "Adeptus Mechanicus",
        "army_rules": ["Doctrina Imperatives"],
        "restrictions": [],
    },
    "AM": {
        "faction_name": "Astra Militarum",
        "army_rules": ["Voice of Command"],
        "restrictions": [],
    },
    "GK": {
        "faction_name": "Grey Knights",
        "army_rules": ["Gate of Infinity"],
        "restrictions": [],
    },
    "AOI": {
        "faction_name": "Imperial Agents",
        "army_rules": ["Assigned Agents"],
        "restrictions": [],
    },
    "QI": {
        "faction_name": "Imperial Knights",
        "army_rules": ["Code Chivalric", "Bondsman", "Super-heavy Walker"],
        "restrictions": ["Freeblades"],
    },
    "AE": {
        "faction_name": "Aeldari",
        "army_rules": ["Battle Focus"],
        "restrictions": ["Disparate Paths"],
    },
    "DRU": {
        "faction_name": "Drukhari",
        "army_rules": ["Power from Pain"],
        "restrictions": ["Corsairs and Travelling Players"],
    },
    "GC": {
        "faction_name": "Genestealer Cults",
        "army_rules": ["Cult Ambush"],
        "restrictions": [],
    },
    "LOV": {
        "faction_name": "Leagues of Votann",
        "army_rules": ["Prioritised Efficiency"],
        "restrictions": [],
    },
    "NEC": {
        "faction_name": "Necrons",
        "army_rules": ["Reanimation Protocols"],
        "restrictions": [],
    },
    "ORK": {
        "faction_name": "Orks",
        "army_rules": ["Waaagh!"],
        "restrictions": [],
    },
    "TAU": {
        "faction_name": "T'au Empire",
        "army_rules": ["For the Greater Good"],
        "restrictions": [],
    },
    "TYR": {
        "faction_name": "Tyranids",
        "army_rules": ["Synapse", "Shadow in the Warp"],
        "restrictions": [],
    },
    "CD": {
        "faction_name": "Chaos Daemons",
        "army_rules": ["The Shadow of Chaos"],
        "restrictions": ["Daemonic Pact"],
    },
    "QT": {
        "faction_name": "Chaos Knights",
        "army_rules": ["Harbingers of Dread", "Super-heavy Walker"],
        "restrictions": ["Dreadblades"],
    },
    "CSM": {
        "faction_name": "Chaos Space Marines",
        "army_rules": ["Dark Pacts"],
        "restrictions": ["Cult of the Dark Gods"],
    },
    "DG": {
        "faction_name": "Death Guard",
        "army_rules": ["Nurgle's Gift (Aura)"],
        "restrictions": ["Pact of Decay"],
    },
    "EC": {
        "faction_name": "Emperor's Children",
        "army_rules": ["Thrill Seekers"],
        "restrictions": ["Pact of Excess"],
    },
    "TS": {
        "faction_name": "Thousand Sons",
        "army_rules": ["Cabal of Sorcerers"],
        "restrictions": ["Pact of Sorcery"],
    },
    "WE": {
        "faction_name": "World Eaters",
        "army_rules": ["Blessings of Khorne"],
        "restrictions": ["Pact of Blood"],
    },
    "SM": {
        "faction_name": "Space Marines",
        "army_rules": ["Oath of Moment", "Templar Vows"],
        "restrictions": ["Space Marine Chapters", "Deathwatch"],
    },
}
