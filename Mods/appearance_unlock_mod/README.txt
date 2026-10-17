APPEARANCE TAB UNLOCK for Town of Magic (made for 0.77.002)
==========================================================
What it does
  Opens the Equip > Appearance tab (clothes and outfits) right away, on a new game and on every save
  you load. Normally it only opens after the tailor, Walter Turner, unlocks it, or the first time Celica
  picks up a piece of clothing. It uses the game's own unlock, the same one the tailor uses.
  Handy together with the clothing remover mod (its six pieces live in the Appearance tab).

Install
  Copy appearance_unlock.rpy and tom_mod_guard.rpy into the game's  game  folder.

Uninstall
  Delete appearance_unlock.rpy and appearance_unlock.rpyc. The tab stays open in saves where it was
  opened. That's the same as the game's own unlock.

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
