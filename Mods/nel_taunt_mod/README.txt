NEL'S TAUNT MOD for Town of Magic (made for 0.77.002)
====================================================
What it does
  While Nel has possessed Celica and is auto-battling:
  * On each of her turns there is a 1 in 16 chance she TAUNTS the monsters. She strikes a teasing pose
    (turns around and touches her backside, lifts her skirt, or fondles herself), says a teasing line,
    goes back to her stance and ends her turn (that line is all she says that turn).
  * From then on every monster that can, grabs her on its turn, using its own grab moves. A monster that is
    already holding her molests her (its own h-animation and sounds), and in the same turn tears the clothing
    on that spot while any is left. Monsters that can't do anything to her just end their turn.
    Nel lets them (she reacts with her own lines from the game) and takes NO damage while this lasts.
  * When she climaxes, the game's own orgasm plays out. Afterwards, on her turn, she says
    "That's enough..." and throws every monster off her. This always works.
  * Then the normal auto-battle continues. She can't taunt again for her next 3 turns.
  * The more she climaxes in a day, the less it takes: 100% of the lust bar, then 60%, 40%, 30%, 20%.
    Resets every day.
  * While taunting she talks about 1/3 as much as the game normally has her talk.
  * While Nel is in control, Celica only gets 50% of the battle XP (Nel does the killing).
  * Nel never kills a monster with her first hit on it: it is left on 1 HP, the next hit kills it.
    (Gives the monsters a chance to get their hands on her.)
  * A climax while Nel possesses Celica raises Nel's body influence on her by 0.5 (the game normally gives 10).
  Monsters you switched off in the game's preferences are left alone. If no monster can grab her,
  she doesn't taunt.

Settings (open nel_taunt.rpy with Notepad, near the top)
  NT_CHANCE = 1.0 / 16           chance on each of her turns
  NT_TALK = 1.0 / 3              how often she says something while taunting
  NT_ORGASM_LUST = [100, 60, 40, 30, 20]   lust % needed to climax: 1st time today, 2nd, 3rd ...
  NT_XP_SHARE = 0.5              Celica's share of battle XP while Nel is in control
  NT_NO_ONE_SHOT = True          her first hit on a monster leaves it on 1 HP
  NT_ORGASM_INFLUENCE = 0.5      Nel's body influence per climax while possessing (game: 10)
  NT_COOLDOWN = 3      her turns without a taunt after one ends
  NT_MAX_TURNS = 40    safety: a taunt ends by itself after this many monster actions
  NT_LOG = False       True = writes game/nel_taunt_log.txt (for troubleshooting)
  NT_TEST_WEAK = False TESTING ONLY: Nel's hits do 1 damage so you can watch a taunt play out
  Settings are always read from this file (also when loading a save).

Install
  Copy nel_taunt.rpy and tom_mod_guard.rpy into the game's  game  folder.

Uninstall
  Delete nel_taunt.rpy and nel_taunt.rpyc. Saves are not affected.

Works with the other mods (h-scene loop, clothing remover, HD sprites, stutter fix).

Safety check (tom_mod_guard.rpy - included with every one of these mods, all copies identical)
  Copy tom_mod_guard.rpy into the game folder too (overwrite it if another mod already put it there).
  On every start it checks that the game functions this mod hooks into are exactly the ones it was made for
  (game 0.77.002). If a game update changed them, the mod switches itself OFF and the game runs normally,
  and game/tom_mod_report.txt lists exactly what changed - send that file to get the mod updated.
  Switches (create an empty file with this name in the game folder):
    tom_mods_off.txt        turns every mod off
    tom_mods_force_on.txt   keeps mods on even after a game update (at your own risk)
