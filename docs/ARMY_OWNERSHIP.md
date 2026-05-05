# Army Ownership Identity

Runtime ownership checks use an army identifier, not faction name, detachment name, or object equality. This matters for mirror matches, especially when both players use the same faction and the same detachment.

The shared helpers in `warhammer40k_ai.utility.army_ownership` define the canonical behavior:

- `same_army()` compares `Army.id` or `_id`; object identity is only a fallback when both references are the same object.
- `unit_parent_army()`, `units_share_army()`, and `units_are_enemies()` resolve attached-unit roots before comparing army ownership.
- `unit_owned_by_player()` prefers the player's army identifier, then falls back to the owning player identifier when no player army object is available.

Map friendly/enemy queries, aura model counts, and Chaos Space Marines detachment/stratagem owner checks use these helpers so two Chaos Space Marine armies with matching detachment labels remain separate armies for eligibility, aura effects, and enemy model counts.
