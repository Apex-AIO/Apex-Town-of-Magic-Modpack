CLOTHING REMOVER MOD for Town of Magic (made for 0.77.002)
=========================================================
What it does
  Adds six pieces to Celica's Equip > Appearance tab. They are added to your inventory
  automatically: on a new game, and every time you load a save.

    Shoes            Visually removes her shoes. (Shoes are cosmetic and don't affect combat.)
    Top/Bra          Removes her top and bra and puts her top in the 'exposed' state.
    Pants/Underwear  Removes her pants and panties and puts her bottom in the 'exposed' state.
                     Top/Bra and Pants/Underwear each give: Allure +25, Lewdness +25,
                     Willpower -25, Cooldown -25, Arcane -25, Speed -25.

    Combat Helper Green   Arcane/Speed/Luck/Cooldown +5,  Willpower +10,  HP + MP regen 1% per turn
    Combat Helper Orange  Arcane/Speed/Luck/Cooldown +25, Willpower +50,  HP + MP regen 5% per turn
    Combat Helper Red     Arcane/Speed/Luck/Cooldown +50, Willpower +100, HP + MP regen 10% per turn
                     You can wear one Combat Helper at a time. Equipping another swaps it. They don't use
                     the hat slot and aren't drawn on Celica. Regen is a % of max HP/MP each battle turn.

  'Exposed' works the same as when a monster has torn off the last layer: grabs on that spot
  use their h-animations right away, and there's nothing left to tear.
  The exposed state stays on after battles, at the tailor's "fix clothes" button, and with the
  garment guardian. While you wear a red X, those don't put clothes back on that spot.

  To swap back, equip any other top/bra/pants/panties/shoes. Or click the red X again to take it
  off, and her default clothes come back. Outfit sets can include the red X pieces.

Install
  Copy the  clothing_remover  folder and tom_mod_guard.rpy into the game's  game  folder, so you get
  game/clothing_remover/clothing_remover.rpy and game/tom_mod_guard.rpy. Then start the game.
  The Appearance tab unlocks through the story as normal. The mod doesn't unlock it early.

Uninstall
  Delete the game/clothing_remover folder. Your saves still load. If Celica was wearing a red X,
  equip other clothes.

Works with the h-scene loop mod and on the vanilla game.

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
