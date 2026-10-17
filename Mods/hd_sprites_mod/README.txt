HD SPRITES MOD for Town of Magic (made for 0.77.002)  -  TEST BUILD
=================================================================
What it does
  Replaces sprites with high-resolution redraws. They look sharper and smoother when the game window is
  bigger than its base 1066x600 size, which is nearly always the case.
  This test build covers Celica standing in her starting outfit: Bra, Panties, Tank Top, Mini Skirt,
  Ankle Boots, plus her body, face and hair.

  The HD pictures were made with 4x-ReboutBlend (x8), color-matched back to the original colors,
  lightly detailed with SDXL (denoise 0.28), then saved at 2x (@2) and 4x (@4).
  The game picks the right size for your window by itself:
    window up to 2x the base size (1920x1080 and smaller)  ->  @2 files
    bigger windows (2560x1440, 4K)                          ->  @4 files

Install
  Copy hd_sprites.rpy, tom_mod_guard.rpy and the images folder into the game's  game  folder.
  You should end up with game/hd_sprites.rpy and game/images/CHAR/celica/...@2.png / @4.png.

Uninstall
  Delete game/hd_sprites.rpy and the @2 / @4 files. Saves are not affected.

Works with the clothing remover and h-scene loop mods.

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
