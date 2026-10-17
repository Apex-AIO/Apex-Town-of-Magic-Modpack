H-SCENE LOOP MOD for Town of Magic
==================================
What it does
  * While it is your turn in a fight, the monsters' grapple/molest animations keep looping on Celica
    instead of freezing on a still picture. Stripping is not looped.
  * With several monsters on her, it picks at random from every molest animation they have used,
    and switches every 4-8 seconds while you are idle.
  * The animation's sound plays quietly (30% volume), one sound at a time. A new one starts only
    when the last has finished, and it stops as soon as you act or a monster takes its turn.

Install (fresh game)
  1. Copy hscene_loop.rpy and tom_mod_guard.rpy into the game's  game  folder (next to options.rpyc, NOT inside images).
  2. Start the game. Ren'Py compiles it automatically.
  Uninstall: delete hscene_loop.rpy and hscene_loop.rpyc from the game folder.

Settings (top of hscene_loop.rpy, open with Notepad)
  HL_LOOP_ENABLED = True         False = mod off
  HL_LOOP_SOUND   = True         False = no idle sounds
  HL_SOUND_VOLUME = 0.30         idle sound volume (fraction of normal)
  HL_SWAP_SECONDS = (4.0, 8.0)   seconds between switching animations; (0, 0) = never switch
  HL_LOG          = False        True = writes game/hl_log.txt for troubleshooting

Independent of the HD sprite mod: works on the vanilla game, and together with HD sprites.

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
