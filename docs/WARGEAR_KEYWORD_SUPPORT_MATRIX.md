# Wargear keyword support matrix (Wahapedia)

Generated from `wahapedia_data/Datasheets_wargear.json` (`description` field).

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
<tr style="background-color: #d4edda;">
<td><code>anti</code></td>
<td><b>Supported</b></td>
<td>562</td>
<td>ANTI-FLY 2+<br/>ANTI-FLY 4+<br/>ANTI-INFANTRY 2+</td>
<td>Critical wound threshold vs matching target keyword (e.g. Anti-Infantry 4+).</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>assault</code></td>
<td><b>Supported</b></td>
<td>300</td>
<td>ASSAULT<br/>assault</td>
<td>Shooting after Advance is allowed for Assault profiles.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>blast</code></td>
<td><b>Supported</b></td>
<td>634</td>
<td>BLAST<br/>Blast<br/>blast</td>
<td>Adds attacks based on target unit size.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>bubblechukka</code></td>
<td><b>Not implemented</b></td>
<td>3</td>
<td>bubblechukka</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>c'tan power</code></td>
<td><b>Not implemented</b></td>
<td>3</td>
<td>c'tan power</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>conversion</code></td>
<td><b>Not implemented</b></td>
<td>11</td>
<td>conversion</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>dead choppy</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>dead choppy</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>devastating wounds</code></td>
<td><b>Supported</b></td>
<td>537</td>
<td>DEVASTATING WOUNDS<br/>devastating wounds</td>
<td>Critical wounds become mortal wounds.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>extra attacks</code></td>
<td><b>Not implemented</b></td>
<td>134</td>
<td>EXTRA ATTACKS<br/>extra attacks</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>harpooned</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>harpooned</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>hazardous</code></td>
<td><b>Supported</b></td>
<td>318</td>
<td>HAZARDOUS<br/>HAzARDOUS<br/>hazardous</td>
<td>Hazardous test after attacking; on 1 suffer mortal wounds.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>heavy</code></td>
<td><b>Supported</b></td>
<td>314</td>
<td>HEAVY<br/>heavy</td>
<td>+1 to hit if the firing unit Remained Stationary.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>hooked</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>hooked</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>ignores cover</code></td>
<td><b>Supported</b></td>
<td>463</td>
<td>IGNORES COVER<br/>IGNORES COvER<br/>Ignores Cover</td>
<td>Cancels Benefit of Cover from terrain and Indirect Fire.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>impaled</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>impaled</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>indirect fire</code></td>
<td><b>Supported</b></td>
<td>101</td>
<td>indirect fire</td>
<td>No-LOS penalties and grants target Benefit of Cover (unless Ignores Cover).</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>lance</code></td>
<td><b>Not implemented</b></td>
<td>40</td>
<td>Lance<br/>lance</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>lethal hits</code></td>
<td><b>Supported</b></td>
<td>193</td>
<td>LETHAL HITS<br/>lethal Hits<br/>lethal hits</td>
<td>Critical hits auto-wound.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>linked fire</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>linked fire</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #fff3cd;">
<td><code>melta</code></td>
<td><b>Partial</b></td>
<td>261</td>
<td>MELTA 2<br/>MElTA 2<br/>melta 1</td>
<td>Melta is implemented, but non-integer values are not supported.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>one shot</code></td>
<td><b>Not implemented</b></td>
<td>123</td>
<td>one shot</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #fff3cd;">
<td><code>pistol</code></td>
<td><b>Partial</b></td>
<td>862</td>
<td>PISTOL<br/>PISTOl<br/>Pistol</td>
<td>Used for fall back + shoot gating; full PISTOL targeting/engagement rules are not fully enforced.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>plasma warhead</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>plasma warhead</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>precision</code></td>
<td><b>Not implemented</b></td>
<td>156</td>
<td>PRECISION<br/>Precision<br/>precision</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #fff3cd;">
<td><code>psychic</code></td>
<td><b>Partial</b></td>
<td>281</td>
<td>PSYCHIC<br/>psychic</td>
<td>Used for conditional FNP parsing (e.g. 'against psychic attacks'); no other special handling.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>psychic assassin</code></td>
<td><b>Not implemented</b></td>
<td>1</td>
<td>psychic assassin</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #fff3cd;">
<td><code>rapid fire</code></td>
<td><b>Partial</b></td>
<td>695</td>
<td>RAPID FIRE 1<br/>RAPID FIRE 2<br/>RAPID FIRE 3</td>
<td>Rapid Fire is implemented, but non-integer values (e.g. D3) are not supported.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>reverberating summons</code></td>
<td><b>Not implemented</b></td>
<td>2</td>
<td>Reverberating summons</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>snagged</code></td>
<td><b>Not implemented</b></td>
<td>2</td>
<td>snagged</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
<tr style="background-color: #fff3cd;">
<td><code>sustained hits</code></td>
<td><b>Partial</b></td>
<td>479</td>
<td>SUSTAINED HITS 1<br/>SUSTAINED HITS 2<br/>SUSTAINED HITS 3</td>
<td>Sustained Hits is implemented, but non-integer values (e.g. D3) are not supported.</td>
</tr>
<tr style="background-color: #d4edda;">
<td><code>torrent</code></td>
<td><b>Supported</b></td>
<td>438</td>
<td>TORRENT<br/>torrent</td>
<td>Auto-hits (also works under Overwatch restriction).</td>
</tr>
<tr style="background-color: #f8d7da;">
<td><code>twin-linked</code></td>
<td><b>Not implemented</b></td>
<td>595</td>
<td>TWIN-LINKED<br/>TwIN-lINkED<br/>twin-linked</td>
<td>No explicit gameplay effect currently wired for this keyword.</td>
</tr>
</tbody>
</table>

## Notes

- This is keyword-level support only. Many faction/unit abilities interact with attacks outside these keywords.
- This matrix groups parameterized keywords (e.g. `anti-infantry 4+`, `anti-vehicle 3+`) under a single canonical row (`anti`).
