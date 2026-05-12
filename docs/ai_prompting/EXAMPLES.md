- Example prompt for developing detailed implementation plan for chatgpt
    ```
    Ensure AGENTS.md is in effect.
    I've merged dev branch into our branch.  Update your internal state to represent the new on disk state.
    Implement the following rule and rule text "Psychic Assassin:
    Each time you select a PSYKER unit as the target for this weapon, until those attacks are resolved, change the Attacks characteristic of this weapon to 6." Please create the same style of comprehensive issue checklist task oriented implementation plan with file-level targets as like the other implementation plans in `docs/implementation`.   Break development into a phased development plan for easier implementation. Main game rules are located in `docs/warhammer-community`.  Wargear rules specifically will likely only be found in the `wahapedia_data` folder. Create the implementation plan in docs/implementation/psychic_assassin_implementation_plan.md.  Include an explicit step to update the docs/WARGEAR_KEYWORD_SUPPORT_MATRIX.md file.
    ```

- Example prompt for augment code to implement:
    ```
    I've merged dev branch into our branch.  Update your internal state to represent the new on disk state.
    Ensure AGENTS.md is in effect.

    Implement the next phase of the detailed plan located at `docs/implementation/psychic_assassin_implementation_plan.md`.  Update and adjust the checklist oriented plan, and it's checklist steps, where needed.  For each task, record implementation results as additional child bullets below each implementation step and mark the task complete when it is finished.

    Stop after each phase so that feedback or approval for next phase can be given.
    ```

- Example prompt for asking for full implementation of a Detachment abililty with user-choices
    ```
    Implement support for the Grand Covent detachment ability `In your Command phase, you can select one of the abilities listed below to take effect until the start of your next Command phase. You can only select each of these abilities once per battle. Imbued Manifestation Add 6" to the Range characteristic of ranged Psychic weapons equipped by THOUSAND SONS models from your army. Psychic Maelstrom Each time a THOUSAND SONS model from your army makes an attack with a Psychic weapon , add 1 to the Wound roll . Wrath of the Immaterium Psychic weapons equipped by THOUSAND SONS models from your army have the [devastating wounds] ability.` - ensure proper LOCAL and REMOTE command support and use of selection dialogs for UI.
    ```

- Example prompt from prompting codex to do complete work
    ```
    USER>Implement support for all unsupported abilities of Pink Horrors and Blue Horrors datasheets. Note the unique UNIT COMPOSITION sections in both Datasheets and special rules in HORRORS ARE PINK. HORRORS ARE BLUE. WHEREONCE THERE WAS ONE, NOW THERE ARE TWO. of Pink Horrors. JSONs have full rules. Do not make any CODE CHANGES yet, process the abilities and describe how you would implement first.
    
    AI>It ask some questions
    
    USER> Answers:
    1) per-model selection
    2) explicit placement decision (that should also be true for reanimation placement heuristic - why does it use auto-place?)
    3) unit-name should change to indicate the other datasheet is used
    4) It cannot (see FAQ below)

    Here are a few more FAQ notes related to Pink and Blue Horrors:

    Q:    If a Pink Horror or a Blue Horror is destroyed as a result of its own weapon’s [HAZARDOUS] ability, can that model’s unit use its Split ability?
    A:        Yes.

    Q:    When I return models to a unit of Blue Horrors that began the battle as a unit of Pink Horrors, can I return Pink Horrors to that unit?
    A:        No.

    Q:    When I return models to a unit of Blue Horrors that began the battle as a unit of Pink Horrors, can I return models to that unit to bring it above the Starting Strength of that unit of Pink Horrors?
    A:        No.

    Q:    Do PINK HORRORS’ and BLUE HORRORS’ Split abilities trigger when the damage is dealt by something other than an attack?
    A:        No.

    Q:    If a unit of PINK HORRORS suffers casualties such that there are no Pink Horror models left, and it then uses the BLUE HORRORS datasheet, what is the Starting Strength of that Blue Horrors unit?
    A:        The Starting Strength of that BLUE HORRORS unit is the same as the Starting Strength of the original PINK HORRORS unit when it was added to your army list.
    
    AI>it asked for the following clarification (the AI)
    
    USER>Open Questions / Clarifications

    Exploding Horrors selection: do you want per-model selection (exact Brimstone models) or is a count-based selection acceptable? Per-model gives full rules fidelity but requires new multi-select UI/decision support.
    Placement for Split-spawned models: should we auto-place using the existing reanimation placement heuristic, or do you want explicit placement decisions (to align with “all player choices are explicit”)?
    Datasheet flip: do you want the unit name to change to “Blue Horrors” when Pink models are gone, or keep the original name for UI continuity?
    Should the unit be able to flip back to Pink if Pink models are later returned (e.g., Shadow of Chaos)? The rule implies “state depends on current composition,” but I can lock it one-way if you prefer.
    
    AI>it processed the FAQ stuff and had more questions
    Questions to confirm before coding
    Split wording: is Split mandatory on eligible attack damage, or “can”? If it’s optional, I’ll include a “None” option in the placement dialog for each destroyed model’s split event; if mandatory, I won’t.
    Reanimation placement: do you want explicit placement for all return‑models effects globally (e.g., Shadow of Chaos, other factions), or only for the Pink/Blue horrors‑related returns?
    Exploding Horrors timing: confirm you want it resolved before choosing a fight target, matching datasheet timing.
    Sources: are we treating the in‑repo JSON as the current/latest rules for these datasheets, or should I verify against the most recent official PDFs before implementation?
    
    USER>Answers
    Answers:
    1) split is mandatory, there is no "can" in description
    2) all return-model effects
    3) Yes — resolve Exploding Horrors before choosing a fight target, exactly as the datasheet timing indicates.
    4) in-repo JSON is latest
    
    AI>then it did it... but I didn't see document updated so I asked
    
    USER>Did you complete full implementation of all the abilities of PInk Horrors and Blue Horrors? I don't see markdown documetns updated
    
    AI>it replied:
    AGENTS.md processed.

    No — the implementation isn’t complete yet. The docs in docs/ haven’t been updated, and a few code tasks are still pending (notably the Exploding Horrors UI/decision flow integration, dialog registration, and cleanup of a remaining broad try/except). Tests haven’t been added or run either.

    If you want me to proceed, I’ll:

    Finish the remaining UI integration and cleanup.
    Update the required docs in docs/.
    Add pytest coverage for split/return-model rules.
    Run python -m pytest tests/ and report results.
    Want me to continue with those?
    
    USER>I replied:

    yes, continue until completion
    and then it completed it all
    as you can see, you have to work with it a bit sometimes
    ```

- Example prompt that just worked
    ```
    USER> Implement support for Rage-cursed Onslaught detachment's enhancements: Carmine Reliquary, Sanguinary Tear (Aura) and Angel's Fang.
    
    AI>it just did it
    When it was done it just said:
    AGENTS.md processed.

    Implemented the Rage-cursed Onslaught enhancements end-to-end: Carmine Reliquary now grants Scouts 6" to the bearer’s attached unit and offers Battle-shock re-rolls within 6", Sanguinary Tear (Aura) applies a +1 Strength weapon aura to nearby Death Company, and Angel’s Fang adds Sustained Hits 2 on qualifying melee targets. This is wired through enhancement.py, unit.py, wargear.py, and aura_effects.py, with documentation updated in space_marines.md and new coverage in test_rage_cursed_onslaught_enhancements.py.

    Tests run:

    uv run python -m pytest tests/ (pass)
    If you want any extra edge-case tests (e.g., multiple Sanguinary Tear sources or mixed Scout distances), tell me which scenarios to cover.
    ```

- Example prompt for Enhancements of a detachment that just worked
    ```
    Implement support for all 4 enhancements of Death Guard - Virulent Vectorium detachment: `Daemon Weapon of Nurgle`, `Furnance of Plagues`, `Arch Contaminator`, and `Revolting Regeneration`.
    ```