# Celica's Smart Auto Battle (smart_auto) - spec

Request (2026-10-21), decisions marked **D**.

## Button
- "Auto Battle Mode: On/Off", centered under the Attributes/Relations frame (left panel).
- Shown only while the game offers `<<Explore>>` (checked through `action_btn_list`) **or** while the mode is on (so it can be
  switched off in a fight).  **D**: it is also hidden while another window (shop, Equip, map, question) is open.
- Switching it off at any moment gives the player the controls back, also in the middle of a fight.

## Control (D: same mechanism as Nel's auto-battle)
- The game already runs a computer-controlled Celica through `enemy_decides(e_celica)` (Nel's possession,
  debug "CPU player").  While the mode is on and a battle runs, `enemy_is_playable(e_celica)` answers False and
  `enemy_decides` is wrapped, so every game rule (cooldowns, MP, grabs, statuses) still applies (`enemy_decides_append_move`).
- Nel's own possession always wins: nothing changes while Nel is in control.

## Fight logic
- Targets: the foe with the lowest HP; all equal -> random; the choice is kept until it dies (focus kill).
- Spell: expected damage from the game's own formulas (level damage, element table, weakness/strength list, arcane bonus),
  capped by the target's HP (no overkill credit).  Highest wins; a spell that kills is chosen by lowest MP cost; area spells are
  scored over all foes.  Cooldown/MP/requirements come from the game (`can_execute_move`).
- Struggle only when every living foe is holding Celica (or nothing castable is left): `unbound_grab` / `unbound_status`.
- Potions (**D**, not asked but needed): Health Potion under the HP limit (setting, 35%), Magic Potion when MP is nearly out,
  `_cleanse` or the matching Anti-potion for a bad status.

## Exploring
- Idle + Explore offered -> press it (the same actions as the button).  Dialogs are clicked through, got-item pop-ups closed.
- Chests are collected by the game itself during the explore.  Anything that needs a decision (choice menu, question) ->
  the mode stops and says why.
- Stops by itself: Explore not offered any more (energy 0, wrong place, night...), HP low with no potion, stuck for 90 s.
- Before an explore (**D**): craft Health/Magic potions up to a stock (setting) and one Anti-potion per status the region's
  monsters can inflict (read from `get_location_enemies` for every hour); best known tier; crafting is limited per round.
  There are no stat-buff potions in this game, so "active buffs" = stock already held.

## Report
- Reuses Nel's Battle Report (nel_report): it records while the mode is on and opens when the mode ends, if there is anything.

## Not done on purpose
- Energy potions are not drunk (the request says to stop at 0% energy).
