# Damaged profile support matrix (Wahapedia)

Generated from `wahapedia_data/Datasheets.json` (`damaged_w` + `damaged_description`).

## Legend

- **Green**: Supported
- **Yellow**: Partial
- **Red**: Not implemented

## Summary

- Datasheets with damaged profiles: 356
- Supported (by current parser): 356

## Matrix

<table>
<thead>
<tr>
<th>Canonical pattern</th>
<th>Status</th>
<th>Count</th>
<th>Examples</th>
<th>Notes</th>
</tr>
</thead>
<tbody>
<tr>
<td bgcolor="#d4edda"><code>Hit roll -N</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">261</td>
<td bgcolor="#d4edda">Aetaos'rau'keres (`000001333`) [1-8]<br/>An'ggrath the Unbound (`000001329`) [1-8]<br/>Angron (`000002621`) [1-6]</td>
<td bgcolor="#d4edda">Implemented: applies a damaged-profile to-hit modifier (-N) with normal +/-1 cap handling.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Hit roll -N + OC -N</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">90</td>
<td bgcolor="#d4edda">Acastus Knight Asterius (`000001664`) [1-10]<br/>Acastus Knight Porphyrion (`000000860`) [1-10]<br/>Arkurian Stormhammer (`000000764`) [1-8]</td>
<td bgcolor="#d4edda">Implemented: applies both -N to hit and OC penalty while damaged.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Halve Attacks</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Triumph Of Saint Katherine (`000002063`) [1-6]</td>
<td bgcolor="#d4edda">Implemented: halves the weapon's attacks characteristic while damaged (round up).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Hit roll -N + Halve Attacks</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">The Silent King (`000002360`) [1-6]</td>
<td bgcolor="#d4edda">Implemented: applies both -N to hit and halved attacks while damaged.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Melee Attacks +N</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Skarbrand (`000004104`) [1-7]</td>
<td bgcolor="#d4edda">Implemented: adds +N attacks for melee weapons while damaged (as written on datasheet).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>OC -N</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Tesseract Vault (`000000556`) [1-8]</td>
<td bgcolor="#d4edda">Implemented: applies an additive Objective Control penalty while damaged.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Specific weapon Attacks +N</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Skarbrand (`000001105`) [1-7]</td>
<td bgcolor="#d4edda">Implemented: adds +N attacks for a specific named weapon while damaged (best-effort name match).</td>
</tr>
</tbody>
</table>

## Notes

- This matrix reports common *text patterns* in degraded/damaged profiles, not per-faction rules.
- Some damaged profiles reference a specific model in a unit (e.g. named character inside a multi-model unit). The engine currently applies damaged profile effects at the unit level (best-effort).
