# Wargear keyword support matrix (Wahapedia)

Generated from `wahapedia_data/Datasheets_wargear.json` (`description` field).

> Note: Boarding Actions detachment filtering is not applicable here (wargear keywords are not detachment-scoped in Wahapedia data).

## Legend

- **Green**: Supported
- **Yellow**: Partial
- **Red**: Not implemented

## Matrix

<table>
<thead>
<tr>
<th>Keyword (canonical)</th>
<th>Status</th>
<th>Occurrences</th>
<th>Examples</th>
<th>Notes</th>
</tr>
</thead>
<tbody>
<tr>
<td bgcolor="#d4edda"><code>anti</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">706</td>
<td bgcolor="#d4edda">ANTI-FLY 2+<br/>ANTI-FLY 4+<br/>ANTI-INFANTRY 2+</td>
<td bgcolor="#d4edda">Critical wound threshold vs matching target keyword (e.g. Anti-Infantry 4+).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>assault</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">362</td>
<td bgcolor="#d4edda">ASSAULT<br/>assault</td>
<td bgcolor="#d4edda">Shooting after Advance is allowed for Assault profiles.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>blast</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">839</td>
<td bgcolor="#d4edda">BLAST<br/>Blast<br/>blast</td>
<td bgcolor="#d4edda">Adds attacks based on target unit size.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>bubblechukka</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">3</td>
<td bgcolor="#d4edda">bubblechukka</td>
<td bgcolor="#d4edda">Random profile selection via D6 roll (1-2: big bubble, 3-4: wobbly bubble, 5-6: dense bubble).</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>c'tan power</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">3</td>
<td bgcolor="#f8d7da">c'tan power</td>
<td bgcolor="#f8d7da">No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>conversion</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">16</td>
<td bgcolor="#d4edda">conversion</td>
<td bgcolor="#d4edda">Unmodified successful hits of 4+ become critical hits when the target is beyond the Conversion distance.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>dead choppy</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">dead choppy</td>
<td bgcolor="#d4edda">+1 Attacks for each additional dread klaw equipped.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>devastating wounds</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">673</td>
<td bgcolor="#d4edda">DEVASTATING WOUNDS<br/>devastating wounds</td>
<td bgcolor="#d4edda">Critical wounds become mortal wounds.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>extra attacks</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">148</td>
<td bgcolor="#d4edda">EXTRA ATTACKS<br/>extra attacks</td>
<td bgcolor="#d4edda">Melee selection supports 1 primary weapon plus all [EXTRA ATTACKS] weapons.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>harpooned</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">harpooned</td>
<td bgcolor="#d4edda">Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>hazardous</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">400</td>
<td bgcolor="#d4edda">HAZARDOUS<br/>HAzARDOUS<br/>hazardous</td>
<td bgcolor="#d4edda">Hazardous test after attacking; on 1 suffer mortal wounds.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>heavy</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">451</td>
<td bgcolor="#d4edda">HEAVY<br/>heavy</td>
<td bgcolor="#d4edda">+1 to hit if the firing unit Remained Stationary.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>hooked</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">hooked</td>
<td bgcolor="#d4edda">Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>ignores cover</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">624</td>
<td bgcolor="#d4edda">IGNORES COVER<br/>IGNORES COvER<br/>Ignores Cover</td>
<td bgcolor="#d4edda">Cancels Benefit of Cover from terrain and Indirect Fire.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>impaled</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">impaled</td>
<td bgcolor="#d4edda">Tracks hits against MONSTER/VEHICLE units for +2 charge bonus.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>indirect fire</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">139</td>
<td bgcolor="#d4edda">indirect fire</td>
<td bgcolor="#d4edda">No-LOS penalties and grants target Benefit of Cover (unless Ignores Cover).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>lance</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">51</td>
<td bgcolor="#d4edda">Lance<br/>lance</td>
<td bgcolor="#d4edda">If the bearer charged this turn, +1 to wound rolls for this weapon.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>lethal hits</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">257</td>
<td bgcolor="#d4edda">LETHAL HITS<br/>lethal Hits<br/>lethal hits</td>
<td bgcolor="#d4edda">Critical hits auto-wound.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>linked fire</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">linked fire</td>
<td bgcolor="#d4edda">Allows measuring range and visibility from another friendly FIRE PRISM unit. When used, weapon Attacks characteristic becomes 1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>melta</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">357</td>
<td bgcolor="#d4edda">MELTA 2<br/>MElTA 2<br/>melta 1</td>
<td bgcolor="#d4edda">Adds damage at half range (supports dice values like D3/D6+X).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>one shot</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">200</td>
<td bgcolor="#d4edda">one shot</td>
<td bgcolor="#d4edda">Enforced: each model can use a ONE SHOT weapon once per battle.</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>overcharge</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">1</td>
<td bgcolor="#f8d7da">overcharge</td>
<td bgcolor="#f8d7da">No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>pistol</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1043</td>
<td bgcolor="#d4edda">PISTOL<br/>PISTOl<br/>Pistol</td>
<td bgcolor="#d4edda">Engaged shooting + pistol-vs-other-ranged choice enforced (10e).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>plasma warhead</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">plasma warhead</td>
<td bgcolor="#d4edda">Requires Remained Stationary, Deathstrike marker placed, no Designate/Adjust this phase. Hits all units within 6" of marker (3D distance). ONE SHOT.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>precision</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">194</td>
<td bgcolor="#d4edda">PRECISION<br/>Precision<br/>precision</td>
<td bgcolor="#d4edda">Allows allocating a successful wound to a visible CHARACTER in an Attached unit.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>psychic</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">337</td>
<td bgcolor="#d4edda">PSYCHIC<br/>psychic</td>
<td bgcolor="#d4edda">Tags Psychic attacks; conditional defenses (FNP/Invulnerable) check this keyword.</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>psychic assassin</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">1</td>
<td bgcolor="#f8d7da">psychic assassin</td>
<td bgcolor="#f8d7da">No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>rapid fire</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">944</td>
<td bgcolor="#d4edda">RAPID FIRE 1<br/>RAPID FIRE 2<br/>RAPID FIRE 3</td>
<td bgcolor="#d4edda">Adds attacks at half range (supports dice values like D3/D6+X).</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>reverberating summons</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">2</td>
<td bgcolor="#f8d7da">Reverberating summons</td>
<td bgcolor="#f8d7da">No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>snagged</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">snagged</td>
<td bgcolor="#d4edda">Tracks hits against MONSTER/VEHICLE units for +2 charge bonus and prevents Overwatch.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>sustained hits</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">664</td>
<td bgcolor="#d4edda">SUSTAINED HITS 1<br/>SUSTAINED HITS 2<br/>SUSTAINED HITS 3</td>
<td bgcolor="#d4edda">Critical hits generate extra hits (supports dice values like D3/D6+X; rolled per critical hit).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>torrent</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">593</td>
<td bgcolor="#d4edda">TORRENT<br/>torrent</td>
<td bgcolor="#d4edda">Auto-hits (also works under Overwatch restriction).</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>twin-linked</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">842</td>
<td bgcolor="#d4edda">TWIN-LINKED<br/>TwIN-lINkED<br/>twin-linked</td>
<td bgcolor="#d4edda">Re-roll failed wound rolls for attacks made with this weapon.</td>
</tr>
</tbody>
</table>

## Notes

- This is keyword-level support only. Many faction/unit abilities interact with attacks outside these keywords.
- This matrix groups parameterized keywords (e.g. `anti-infantry 4+`, `anti-vehicle 3+`) under a single canonical row (`anti`).
