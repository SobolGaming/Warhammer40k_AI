# Optional wargear support matrix (Wahapedia)

Generated from `wahapedia_data/Datasheets_options.json` (optional wargear allowances/replacements).

## Legend

- **Green**: Supported
- **Yellow**: Partial
- **Red**: Not implemented

## Summary

- Option lines: 2758
- Supported (parser + simple apply): 2699
- Partial (parsed, but constraints not fully enforced): 0
- Not implemented (unparsed): 59

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
<td bgcolor="#d4edda"><code>Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">589</td>
<td bgcolor="#d4edda">Acastus Knight Porphyrion (`000000860`): This model's Acastus ironstorm missile pod can be replaced with 1 helios defence missiles.<br/>Acolyte Hybrids With Autopistols (`000000511`): One Acolyte Hybrid's autopistol can be replaced with 1 cult icon.<br/>Acolyte Hybrids With Autopistols (`000000511`): The Acolyte Leader's cult claws and knife can be replaced with 1 Leader's bio-weapons.</td>
<td bgcolor="#d4edda">Breakdown: Supported=589.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">473</td>
<td bgcolor="#d4edda">Acastus Knight Porphyrion (`000000860`): This model's 2 Acastus autocannons can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;2 lascannons&lt;/li&gt;&lt;li&gt;1 A…<br/>Ancient In Terminator Armour (`000002677`): This model's power fist can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 chainfist&lt;/li&gt;&lt;li&gt;1 close combat …<br/>Ancient In Terminator Armour (`000002677`): This model's storm bolter and power fist can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 twin lightning c…</td>
<td bgcolor="#d4edda">Breakdown: Supported=473.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">454</td>
<td bgcolor="#d4edda">Anathema Psykana Rhino (`000002524`): This model can be equipped with 1 hunter-killer missile.<br/>Arkurian Stormhammer (`000000764`): This model can be equipped with 1 hunter-killer missile.<br/>Arkurian Stormhammer (`000003994`): This model can be equipped with 1 hunter-killer missile.</td>
<td bgcolor="#d4edda">Breakdown: Supported=437, Not implemented=17.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">284</td>
<td bgcolor="#d4edda">Arkurian Stormhammer (`000000764`): This model can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 heavy stubber&lt;/li&gt;&lt;li&gt;1 storm bolter&lt;/li&gt;&lt;/ul&gt;<br/>Arkurian Stormhammer (`000003994`): This model can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 heavy stubber&lt;/li&gt;&lt;li&gt;1 storm bolter&lt;/li&gt;&lt;/ul&gt;<br/>Armageddon-pattern Medusa (`000000739`): This model can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 storm bolter&lt;/li&gt;&lt;li&gt;1 heavy stubber&lt;/li&gt;&lt;/ul&gt;</td>
<td bgcolor="#d4edda">Breakdown: Supported=284.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>None</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">276</td>
<td bgcolor="#d4edda">Acastus Knight Asterius (`000001664`): None<br/>Aegis Defence Line (`000002619`): None<br/>Aegis Defence Line (`000003955`): None</td>
<td bgcolor="#d4edda">Breakdown: Supported=276.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Any number + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">116</td>
<td bgcolor="#d4edda">Allarus Custodians (`000001453`): Any number of models can each have their guardian spear replaced with 1 castellan axe.<br/>Aquilon Custodians (`000001558`): Any number of models can each have their solerite power gauntlet replaced with 1 solerite power talon.<br/>Attack Bike Squad (`000002076`): Any number of models can each have their heavy bolter replaced with 1 multi-melta.</td>
<td bgcolor="#d4edda">Breakdown: Supported=116.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>For every N models + Replacement + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">73</td>
<td bgcolor="#d4edda">Assault Intercessors With Jump Packs (`000002776`): For every 5 models in this unit, 1 Assault Intercessor with Jump Pack's heavy bolt pistol can be replaced with 1 plasma pistol.<br/>Assault Squad (`000000061`): For every 5 models in this unit, 1 model's Astartes chainsword can be replaced with 1 eviscerator.<br/>Assault Squad with Jump Packs (`000000064`): For every 5 models in this unit, 1 model's Astartes chainsword can be replaced with 1 eviscerator.</td>
<td bgcolor="#d4edda">Breakdown: Supported=73.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">70</td>
<td bgcolor="#d4edda">Achilles Ridgerunners (`000001573`): Any number of models can each have their heavy mining laser replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 achi…<br/>Achilles Ridgerunners (`000001573`): Any number of models can each have their flare launcher replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 spotter&lt;…<br/>Agamatus Custodians (`000001560`): Any number of models can each have their lastrum bolt cannon replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 adr…</td>
<td bgcolor="#d4edda">Breakdown: Supported=70.</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>Other / unclassified</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">70</td>
<td bgcolor="#f8d7da">Brotherhood Terminator Squad (`000000382`): * That model's storm bolter cannot be replaced.<br/>Cadian Shock Troops (`000002612`): * You cannot select the same weapon more than once per unit unless it contains 20 models, in which case you cannot select the same weapon mo…<br/>Cadian Shock Troops (`000003948`): * You cannot select the same weapon more than once per unit unless it contains 20 models, in which case you cannot select the same weapon mo…</td>
<td bgcolor="#f8d7da">Breakdown: Supported=29, Not implemented=41.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + For every N models + Replacement + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">30</td>
<td bgcolor="#d4edda">Boyz (`000000016`): For every 10 models in this unit, 1 Boy's choppa and slugga can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li…<br/>Brotherhood Terminator Squad (`000000382`): For every 5 models in this unit, 1 Terminator's storm bolter can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;l…<br/>Chaos Terminator Squad (`000000947`): For every 5 models in this unit, 1 Terminator's combi-bolter can be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;l…</td>
<td bgcolor="#d4edda">Breakdown: Supported=30.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Up to N + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">30</td>
<td bgcolor="#d4edda">Assault Squad (`000000061`): Up to 2 Assault Marines can each have their bolt pistol and Astartes chainsword replaced with one of the following:&lt;ul style="list-style-typ…<br/>Assault Squad with Jump Packs (`000000064`): Up to 2 Assault Marines with Jump Packs can each have their bolt pistol and Astartes chainsword replaced with one of the following:&lt;ul style…<br/>Astartes Servitors (`000000134`): Up to 2 models can each have their Servitor servo-arm replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 heavy bolt…</td>
<td bgcolor="#d4edda">Breakdown: Supported=30.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">23</td>
<td bgcolor="#d4edda">Aggressor Squad (`000002099`): All models in this unit can each have their flamestorm gauntlets replaced with 1 auto boltstorm gauntlets and 1 fragstorm grenade launcher.<br/>Brôkhyr Thunderkyn (`000002603`): All models in this unit can each have their bolt cannon replaced with 1 graviton blast cannon.<br/>Brôkhyr Thunderkyn (`000002603`): All models in this unit can each have their bolt cannon replaced with 1 SP conversion beamer.</td>
<td bgcolor="#d4edda">Breakdown: Supported=23.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>For every N models + Additional + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">22</td>
<td bgcolor="#d4edda">Cadian Shock Troops (`000002612`): For every 10 models in this unit, 1 Shock Trooper equipped with a lasgun can be equipped with 1 vox-caster (that model's lasgun cannot be re…<br/>Cadian Shock Troops (`000003948`): For every 10 models in this unit, 1 Shock Trooper equipped with a lasgun can be equipped with 1 vox-caster (that model's lasgun cannot be re…<br/>Catachan Jungle Fighters (`000002614`): For every 10 models in this unit, 1 Jungle Fighter equipped with a lasgun can be equipped with 1 vox-caster (that model's lasgun cannot be r…</td>
<td bgcolor="#d4edda">Breakdown: Supported=22.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">21</td>
<td bgcolor="#d4edda">Captain In Gravis Armour (`000001172`): This model's master-crafted heavy bolt rifle and master-crafted power weapon can be replaced with:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 b…<br/>Crusader Squad (Legendary) (`000004154`): The Sword Brother's bolt pistol and boltgun can be replaced with 1 twin lightning claws or two different weapons from the following list*:&lt;b…<br/>Dark Reapers (`000000607`): The Dark Reaper Exarch's Reaper launcher can be replaced with 1 of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 missile launcher&lt;/…</td>
<td bgcolor="#d4edda">Breakdown: Supported=21.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Any number + Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">20</td>
<td bgcolor="#d4edda">Armoured Sentinels (`000000691`): Any number of models can each be equipped with 1 Sentinel chainsaw.<br/>Armoured Sentinels (`000000691`): Any number of models can each be equipped with 1 hunter-killer missile.<br/>Armoured Sentinels (`000003960`): Any number of models can each be equipped with 1 Sentinel chainsaw.</td>
<td bgcolor="#d4edda">Breakdown: Supported=20.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">20</td>
<td bgcolor="#d4edda">AX-1-0 Tiger Shark (`000000455`): This model can be equipped with up to 6 seeker missiles.<br/>Barracuda (`000000453`): This model can be equipped with up to 4 seeker missiles.<br/>Battlewagon (`000000039`): This model can be equipped with up to 4 big shootas.</td>
<td bgcolor="#d4edda">Breakdown: Supported=20.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + For every N models + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">20</td>
<td bgcolor="#d4edda">Acolyte Hybrids With Autopistols (`000000511`): For every 5 models in this unit, up to 3 Acolyte Hybrids can each have their autopistol and cult claws and knife replaced with 1 heavy minin…<br/>Acolyte Hybrids With Hand Flamers (`000003716`): For every 5 models in this unit, up to 2 Acolyte Hybrids can each have their hand flamer replaced with 1 demolition charges<br/>Atalan Jackals (`000001574`): For every 4 Atalan Jackals in this unit, up to 2 Atalan Jackals' close combat weapons can each be replaced with 1 Atalan power weapon.</td>
<td bgcolor="#d4edda">Breakdown: Supported=20.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Up to N + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">19</td>
<td bgcolor="#d4edda">Breacher Team (`000000412`): The Breacher Fire Warrior Shas'ui can be equipped with up to two of the following, and can take duplicates:&lt;ul style="list-style-type:circle…<br/>Cadre Fireblade (`000000405`): This model can be equipped with up to two of the following, and can take duplicates:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 &lt;span class="to…<br/>Castellum Stronghold (`000002807`): This model can be equipped with up to three of the following (but cannot be equipped with duplicates of the same weapon):&lt;ul style="list-sty…</td>
<td bgcolor="#d4edda">Breakdown: Supported=19.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Up to N + For every N models + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">15</td>
<td bgcolor="#d4edda">Cadian Shock Troops (`000002612`): For every 10 models in this unit, up to 2 Shock Troopers can each have their lasgun replaced with one of the following*:&lt;ul style="list-styl…<br/>Cadian Shock Troops (`000003948`): For every 10 models in this unit, up to 2 Shock Troopers can each have their lasgun replaced with one of the following*:&lt;ul style="list-styl…<br/>Crusader Squad (`000002799`): For every 10 models in this unit, up to 2 Initiates can each have their bolt rifle replaced with one of the following:&lt;br&gt;&lt;ul style="list-st…</td>
<td bgcolor="#d4edda">Breakdown: Supported=15.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>For every N models + Other / unclassified + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">13</td>
<td bgcolor="#d4edda">Dark Reapers (`000000607`): For every 5 models in this unit, it can have 1 Aspect Shrine token.<br/>Dire Avengers (`000000593`): For every 5 models in this unit, it can have 1 Aspect Shrine token.<br/>Fire Dragons (`000000596`): For every 5 models in this unit, it can have 1 Aspect Shrine token.</td>
<td bgcolor="#d4edda">Breakdown: Supported=13.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Any number + Other / unclassified + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">10</td>
<td bgcolor="#d4edda">Death Korps Of Krieg (`000002613`): Any number of Death Korps Watchmasters can each replace their laspistol and chainsword with 1 boltgun and 1 close combat weapon.<br/>Death Korps Of Krieg (`000002613`): Any number of Death Korps Watchmasters can each replace their chainsword with 1 power weapon.<br/>Death Korps Of Krieg (`000003950`): Any number of Death Korps Watchmasters can each replace their laspistol and chainsword with 1 boltgun and 1 close combat weapon.</td>
<td bgcolor="#d4edda">Breakdown: Supported=10.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">10</td>
<td bgcolor="#d4edda">Chaos Terminators (`000004081`): Up to 3 models can each have their accursed weapon replaced with 1 power fist.<br/>Hearthkyn Warriors (`000002598`): Up to 2 Hearthkyn Warriors can each have their Autoch-pattern bolter or ion blaster replaced with 1 plasma knife.<br/>Kommandos (`000000025`): Up to 2 Kommandos can each have their slugga and choppa replaced with 1 speshul Kommando shoota and 1 close combat weapon.</td>
<td bgcolor="#d4edda">Breakdown: Supported=10.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Other / unclassified + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">8</td>
<td bgcolor="#d4edda">Death Korps Of Krieg (`000002613`): Any number of Death Korps Watchmasters can each replace their laspistol with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 b…<br/>Death Korps Of Krieg (`000003950`): Any number of Death Korps Watchmasters can each replace their laspistol with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 b…<br/>Scourges with Heavy Weapons (`000000662`): Any number of Scourges can each replace their splinter cannon with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 blaster&lt;/li…</td>
<td bgcolor="#d4edda">Breakdown: Supported=8.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Other / unclassified</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">8</td>
<td bgcolor="#d4edda">Fortis Kill Team (`000002780`): The Kill Team Sergeant can replace its Deathwatch bolt rifle with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 Astartes cha…<br/>Fortis Kill Team (`000002780`): The Kill Team Sergeant can replace its close combat weapon with one of the following:&lt;br&gt;&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 Astartes c…<br/>Fortis Kill Team (`000003825`): 1 model equipped with a bolt rifle can replace its close combat weapon with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 As…</td>
<td bgcolor="#d4edda">Breakdown: Supported=8.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Additional + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">7</td>
<td bgcolor="#d4edda">Deathwing Command Squad (`000002302`): This unit can be equipped with 1 Watcher in the Dark.*<br/>Deathwing Knights (`000000231`): This unit can be equipped with 1 Watcher in the Dark.<br/>Deathwing Terminator Squad (`000000230`): This unit can be equipped with 1 Watcher in the Dark.</td>
<td bgcolor="#d4edda">Breakdown: Supported=7.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>If unit contains N models + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">7</td>
<td bgcolor="#d4edda">Blightlord Terminators (`000001372`): If this unit contains only 3 models, 1 Blightlord Terminator's combi-bolter and bubotic blade can be replaced with 1 plague spewer and 1 clo…<br/>Corsair Voidscarred (`000002532`): If this unit contains 10 models, 1 Corsair Voidscarred's shuriken rifle can be replaced with 1 long rifle.<br/>Corsair Voidscarred (`000002532`): If this unit contains 10 models, 1 Corsair Voidscarred's power sword can be replaced with 1 fusion pistol.</td>
<td bgcolor="#d4edda">Breakdown: Supported=7.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">6</td>
<td bgcolor="#d4edda">Battlewagon (`000000039`): This model can be equipped with:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 lobba&lt;/li&gt;&lt;/ul&gt;<br/>Battlewagon (`000000039`): This model can be equipped with any of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 'ard case&lt;/li&gt;&lt;li&gt;1 grabbin' klaw&lt;/li&gt;&lt;li&gt;1 wr…<br/>Canoness (`000000899`): If this model is equipped with a plasma pistol and a power weapon, it can be equipped with:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 rod of o…</td>
<td bgcolor="#d4edda">Breakdown: Supported=6.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">6</td>
<td bgcolor="#d4edda">Chaos Acastus Knight Porphyrion (`000001099`): This model's 2 Acastus autocannons can each be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;2 lascannons&lt;/li&gt;&lt;l…<br/>Deff Dread (`000000040`): This model's big shootas can each be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 dread klaw&lt;/li&gt;&lt;li&gt;1 kustom…<br/>Deff Dread (`000000040`): This model's dread klaws can each be replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 big shoota&lt;/li&gt;&lt;li&gt;1 kustom…</td>
<td bgcolor="#d4edda">Breakdown: Supported=6.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + For every N models + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">6</td>
<td bgcolor="#d4edda">Aquila Kill Team (`000004174`): For every 5 models in the unit, up to 1 model's heavy thunder hammer can be replaced with 1 power weapon and 1 Astartes shield.<br/>Aquila Kill Team (`000004174`): For every 5 models in the unit, up to 1 model's stalker bolt rifle can be replaced with 1 plasma incinerator.<br/>Aquila Kill Team (`000004174`): For every 5 models in the unit, up to 1 model's Deathwatch marksman bolt carbine can be replaced with 1 combat knife.</td>
<td bgcolor="#d4edda">Breakdown: Supported=6.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + If unit contains N models + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">5</td>
<td bgcolor="#d4edda">Corsair Voidreavers (`000002531`): If this unit contains 10 models, 1 Corsair Voidreaver's shuriken rifle can be replaced with one of the following:&lt;ul style="list-style-type:…<br/>Corsair Voidreavers (`000004168`): If this unit contains 10 models, 1 Corsair Voidreaver's shuriken rifle can be replaced with one of the following:&lt;ul style="list-style-type:…<br/>Corsair Voidscarred (`000002532`): If this unit contains 10 models, 1 Corsair Voidscarred's shuriken rifle can be replaced with one of the following:&lt;ul style="list-style-type…</td>
<td bgcolor="#d4edda">Breakdown: Supported=5.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + For every N models + Additional + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">4</td>
<td bgcolor="#d4edda">Grot Tanks (`000000049`): For every four models in this unit, one model can be equipped with one of the following in addition to any other weapons:&lt;ul style="list-sty…<br/>Hernkyn Pioneers (`000002601`): For every 3 models in this unit, 1 model can be equipped with one of the following::&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 HYLas rotary ca…<br/>Reavers (`000000658`): For every 3 models in this unit, 1 model can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 cluster caltrops…</td>
<td bgcolor="#d4edda">Breakdown: Supported=4.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Up to N + Any number + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">4</td>
<td bgcolor="#d4edda">Crisis Battlesuits (`000000418`): Any number of models can be equipped with up to two of the following, and can take duplicate&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 &lt;span c…<br/>Crisis Fireknife Battlesuits (`000003700`): Any number of models can be equipped with up to two of the following, but cannot take duplicates&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 &lt;sp…<br/>Crisis Starscythe Battlesuits (`000003701`): Any number of models can be equipped with up to two of the following, but cannot take duplicates&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 &lt;sp…</td>
<td bgcolor="#d4edda">Breakdown: Supported=4.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Up to N + Any number + Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">4</td>
<td bgcolor="#d4edda">Broadside Battlesuits (`000000433`): Any number of models can each be equipped with up to two of the following, but cannot take duplicates:&lt;ul style="list-style-type:circle"&gt;&lt;li…<br/>Broadside Battlesuits (`000000433`): Any number of models can each be equipped with up to two of the following, and can take duplicates:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 …<br/>Crisis Battlesuits (`000000418`): Any number of models can each be equipped with up to three of the following, and can take duplicates**:&lt;ul style="list-style-type:circle"&gt;&lt;l…</td>
<td bgcolor="#d4edda">Breakdown: Supported=4.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Up to N + If unit contains N models + Replacement + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">4</td>
<td bgcolor="#d4edda">Troupe (`000002536`): If this unit contains 9 or fewer models:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;Up to 2 models can each have their shuriken pistol replaced w…<br/>Troupe (`000002536`): If this unit contains 10 or more models:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;Up to 4 models can each have their shuriken pistol replaced w…<br/>Troupe (`000004164`): If this unit contains 9 or fewer models:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;Up to 2 models can each have their shuriken pistol replaced w…</td>
<td bgcolor="#d4edda">Breakdown: Supported=4.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">3</td>
<td bgcolor="#d4edda">Reiver Squad (`000002718`): All models in this unit can each be equipped with 1 Reiver grav-chute.<br/>Reiver Squad (`000002718`): All models in this unit can each be equipped with 1 grapnel launcher.<br/>Ripper Swarms (`000000470`): All models in this unit can each be equipped with 1 spinemaws.</td>
<td bgcolor="#d4edda">Breakdown: Supported=3.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>For every N models + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">3</td>
<td bgcolor="#d4edda">Death Guard Cultists (`000001043`): For every 10 models in the unit, 1 Death Guard Cultist's Cultist firearm can be replaced with 1 flamer.<br/>Death Guard Cultists (`000001043`): For every 10 models in the unit, 1 Death Guard Cultist's Cultist firearm can be replaced with 1 heavy stubber.<br/>Death Guard Cultists (`000001043`): For every 10 models in the unit, 1 Death Guard Cultist's Cultist firearm can be replaced with 1 grenade launcher.</td>
<td bgcolor="#d4edda">Breakdown: Supported=3.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">3</td>
<td bgcolor="#d4edda">Canoptek Wraiths (`000000546`): Any number of models can each be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 particle caster&lt;/li&gt;&lt;li&gt;1 trans…<br/>Tomb Blades (`000000548`): Any number of models can each be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 nebuloscope&lt;/li&gt;&lt;li&gt;1 shadowloo…<br/>Xv9 Hazard Battlesuits (`000000443`): Any number of models can each be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 battlesuit support system&lt;/li&gt;&lt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=3.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Griffon Mortar Carrier (`000000744`): This model can each be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 heavy stubber&lt;/li&gt;&lt;li&gt;1 storm bolter&lt;/li&gt;…<br/>Griffon Mortar Carrier (`000004007`): This model can each be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 heavy stubber&lt;/li&gt;&lt;li&gt;1 storm bolter&lt;/li&gt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + For every N models + Other / unclassified + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Deathwing Command Squad (`000002302`): For every 5 models in this unit, 1 Deathwing Command Terminator can replace its storm bolter with one of the following:&lt;ul style="list-style…<br/>Deathwing Terminator Squad (`000000230`): For every 5 models in this unit, 1 Deathwing Terminator can replace its storm bolter with one of the following:&lt;ul style="list-style-type:ci…</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Up to N + For every N models + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Aquila Kill Team (`000004174`): For every 5 models in the unit, up to 1 model's infernus heavy bolter can be replaced with one of the following:&lt;ul style="list-style-type:c…<br/>Decimus Kill Team (`000004175`): For every 5 models in the unit, up to 1 model's infernus heavy bolter can be replaced with one of the following:&lt;ul style="list-style-type:c…</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>If unit contains N models + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Ratlings (`000000724`): If this unit contains 10 models, one model can be equipped with demolition gear.<br/>Ratlings (`000000724`): If this unit contains 10 models, it can be equipped with one Ratling Battlemutt.</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + For every N models + Other / unclassified + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Proteus Kill Team (`000003824`): For every 5 models in this unit, up to 2 models can replace their boltgun and Long Vigil melee weapon with 1 Deathwatch thunder hammer.<br/>Proteus Kill Team (`000003824`): For every 5 models in this unit, up to 2 models can replace their boltgun and Long Vigil melee weapon with 1 Deathwatch thunder hammer.</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + Other / unclassified + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">2</td>
<td bgcolor="#d4edda">Noise Marines (`000004088`): Up to 2 Noise Marines can each replace their sonic blaster with 1 blastmaster.<br/>Noise Marines (`000004099`): Up to 2 Noise Marines can each replace their sonic blaster with 1 blastmaster.</td>
<td bgcolor="#d4edda">Breakdown: Supported=2.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + Any number + Other / unclassified</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Proteus Kill Team (`000003824`): Any number of Kill Team Veterans can replace their boltgun and Long Vigil melee weapon with:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 Long Vi…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + For every N models + Replacement + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Wracks (`000000650`): For every 5 models in this unit:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 model's twin torturer's tools can be replaced with 1 hexrifle and 1…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + If unit contains N models + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Vespid Stingwings (`000000427`): If this unit contains 10 models:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;The Vespid Strain Leader can be equipped with 1 Oversight Drone.&lt;/li&gt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Additional + Unit-wide / scaling</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Tomb Citadel Walls (`000002362`): This unit can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 gauss exterminator and 1 twin tesla destructor&lt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Additional</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Proteus Kill Team (`000003824`): Any number of Kill Team Biker models can be equipped with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 bolt pistol&lt;/li&gt;&lt;li&gt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Other / unclassified</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Proteus Kill Team (`000003824`): Any number of Kill Team Terminator models can replace their power fist and storm bolter with one of the following:&lt;ul style="list-style-type…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Any number + Replacement</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Wolf Guard (`000000315`): Any number of models can have their bolt pistol replaced with one of the following:&lt;ul style="list-style-type:circle"&gt;&lt;li&gt;1 boltgun&lt;/li&gt;&lt;li&gt;…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>HTML list + One-of list + Up to N + For every N models + Other / unclassified</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Proteus Kill Team (`000003824`): For every 5 models in the unit, up to 2 models can replace their boltgun and Long Vigil melee weapon with one of the following:&lt;ul style="li…</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
<tr>
<td bgcolor="#f8d7da"><code>Other / unclassified + Unit-wide / scaling</code></td>
<td bgcolor="#f8d7da"><b>🟥 Not implemented</b></td>
<td bgcolor="#f8d7da">1</td>
<td bgcolor="#f8d7da">Neophyte Hybrids (`000000512`): * To a maximum of 1 per 10 models in this unit.</td>
<td bgcolor="#f8d7da">Breakdown: Not implemented=1.</td>
</tr>
<tr>
<td bgcolor="#d4edda"><code>Up to N + Any number + Additional + Per-model</code></td>
<td bgcolor="#d4edda"><b>🟩 Supported</b></td>
<td bgcolor="#d4edda">1</td>
<td bgcolor="#d4edda">Piranhas (`000000423`): Any number of models can each be equipped with up to 2 seeker missiles.</td>
<td bgcolor="#d4edda">Breakdown: Supported=1.</td>
</tr>
</tbody>
</table>

## Notes

- Many options include unit-wide constraints (e.g. “cannot select the same weapon more than once per unit”). These are reported as **Partial** until enforced in UI/validation.
- This matrix is pattern-based; a single datasheet may contain multiple option lines across different patterns.
