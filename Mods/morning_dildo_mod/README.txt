MORNING DILDO MOD for Town of Magic (made for 0.77.002)
======================================================
What it does
  When Celica wakes up at home and nothing else is planned for the morning, there is a 1 in 9 chance
  she starts the day with the dildo Nel gave her. The game's own scene plays, and like in the game,
  Nel joins in if she is in the room. "Nothing else planned" means: no night or morning visit or scene
  the game queued, nothing scheduled where she is, and no possession pending.
  It only happens when:
    - she has the dildo (Nel gives it to you in her story),
    - it's her own body (not possessed),
    - her Lewdness is at least 30 (the game's own rule for using it),
    - she hasn't used it yet that day.

Settings (open morning_dildo.rpy with Notepad, near the top)
  MD_CHANCE = 1.0 / 9      chance each morning
  MD_MIN_LEWDNESS = 30     the game's own minimum to use it
  MD_LOG = False           True = writes game/morning_dildo_log.txt (shows why it did or didn't happen)
  Settings are always read from this file (also when loading a save).

Install
  Copy morning_dildo.rpy and tom_mod_guard.rpy into the game's  game  folder.

Uninstall
  Delete morning_dildo.rpy and morning_dildo.rpyc. Saves are not affected.


Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
