BATTLE STUTTER FIX for Town of Magic (made for 0.77.002)
=======================================================
What it does
  Removes the short freezes (about 0.3-0.4 seconds) in battle when Celica changes pose: grabs, h-scenes,
  getting hit, struggling.

  Cause: every time her pose changes, the game prepares the next pictures by searching its whole list of
  about 33,000 files roughly 20 times with a slow pattern match. The list never changes while you play,
  so the mod remembers each answer and skips names that can't match. You get the same results, about
  10x faster the first time and instantly every time after.

Install
  Copy stutter_fix.rpy and tom_mod_guard.rpy into the game's  game  folder.

Uninstall
  Delete stutter_fix.rpy and stutter_fix.rpyc from the game folder.

Works with every other mod, and with the vanilla game.

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
