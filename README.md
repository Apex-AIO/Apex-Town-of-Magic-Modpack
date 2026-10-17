# Apex's Town of Magic Modpack + Mod Manager

An all-in-one, drag-and-drop modpack for **Town of Magic** (by Deimus), with an in-game **Modpack Manager**: switch every module on or off, tweak its settings, and stay safe when the game updates.

**Made for:** Town of Magic **0.77.002**

## ⬇️ Download

**[Latest release](../../releases/latest)**: download `Apex_Modpack_v<version>.zip` from the release's *Assets*.

### Install
1. Open your Town of Magic folder (the one with `TownOfMagic.exe`).
2. Drag the `game` folder from the zip into it and choose merge / replace.
3. Start the game: **Apex's Modpack Manager** is at the top of the main menu.

**Uninstall:** delete `game\Apex_Modpack.rpa`. Saves keep working either way.

## 📦 Modules

| Module | What it does |
|---|---|
| **Nel's Auto Battler Sex Autonomy Mod** | Nel sometimes taunts the monsters during her auto-battles. Includes a climax ladder and the sub-modules *Half XP* and *Never One-Shots*. |
| **Game Engine Stutter Fix** | Removes the short battle freezes when a pose changes. |
| **Appearance Menu Insta Unlock** | Equip > Appearance is open from the start. |
| **Celica's Autonomy Dildo Events** | On quiet mornings Celica sometimes uses the dildo by herself. |
| **Clothing Remover & Combat Helpers** | Red-X Shoes / Top / Pants items and Combat Helper accessories. |
| **H-Scene Idle Loop** | Grope and H-scene animations keep looping on your turn. |
| **HD x8 Upscale Project** *(very early WIP)* | AI-upscaled HD sprites for big windows. |

Every module has an ON/OFF switch, and most have a ⚙️ gear with settings, all in the in-game manager.

## 🛡️ Game updates
At start-up, each module checks the game code it changes. If an update changed it, that module switches itself off and the game runs normally. If the game is newer than the modpack, every module stays off until you choose **Test modpack? → Yes** in the manager. Each start writes `game/tom_mod_report.txt`; please attach it to bug reports.

## 🧩 For modders: building from source
- `Mods/`: one folder per module (`.rpy` sources), plus `modpack.json`, which lists the modules, revisions, settings and files.
- `Mods/_shared/tom_mod_guard.rpy`: the shared safety guard (fingerprints, version check, settings).
- `Mods/apex_modpack_manager/`: the manager screens.
- `Tools/build_modpack.py`: compiles everything with the game's own Ren'Py and packs it into one `Apex_Modpack.rpa`, plus the release zip. Put this repository's folder inside your Town of Magic folder and run it with the game closed.
- `Tools/upscale/`: the HD upscale pipeline (ComfyUI). The HD sprites themselves only ship in the release zip.

## ☕ Support
Please support the game's developer, Deimus, first. If you'd still like to support the modpack's future development: **[buymeacoffee.com/apex_modding](https://buymeacoffee.com/apex_modding)**

*Fan-made mod; not affiliated with Deimus. Town of Magic and its assets belong to their creator.*
