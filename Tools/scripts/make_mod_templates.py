"""make_mod_templates.py - writes the modder templates + their example pictures into
Mods/apex_modpack_manager/mods_folder/_templates/ (shipped as <Town of Magic>/mods/_templates).

    python make_mod_templates.py
Pictures are made from the game's own art (recoloured), read straight from the archives.
"""
import os, sys, io
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(WS, "Tools", "art"))
from catalog import read_index, read_bytes, ARCHIVES

OUT = os.path.join(WS, "Mods", "apex_modpack_manager", "mods_folder", "_templates")
GAME_VERSION = "0.77.002"
_idx = {}


def game_png(name):
    if not _idx:
        for a in ARCHIVES:
            _idx.update({k: (a, v) for k, v in read_index(a).items()})
    a, e = _idx[name]
    return Image.open(io.BytesIO(read_bytes(a, e))).convert("RGBA")


def redden(im):
    """hue-shift towards red, keep shading"""
    import colorsys
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, al = px[x, y]
            if al == 0:
                continue
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            r2, g2, b2 = colorsys.hls_to_rgb(0.99, l, max(s, 0.55))
            px[x, y] = (int(r2 * 255), int(g2 * 255), int(b2 * 255), al)
    return im


def write(folder, files):
    d = os.path.join(OUT, folder)
    os.makedirs(d, exist_ok=True)
    for name, content in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if isinstance(content, Image.Image):
            content.save(p)
        else:
            with open(p, "w", encoding="utf8", newline="\n") as f:
                f.write(content.strip("\n") + "\n")


def info(name, desc, settings=()):
    lines = ["# mod_info.txt - tells the Mod Manager about your mod. Lines starting with # are notes.",
             "name = %s" % name, "author = Your Name", "version = 1.0", "description = %s" % desc,
             "made_for_game = %s" % GAME_VERSION]
    if settings:
        lines += ["", "# Settings the player can change with the gear in the Mod Manager:",
                  "#   setting = key | type | default | min | max | label",
                  "#   types: on/off, number, percent, 1 in n, seconds, decimal"]
        lines += ["setting = " + s for s in settings]
    return "\n".join(lines)


def main():
    # 1 ---------------------------------------------------------------- hello world
    write("01 Hello World", {
        "mod_info.txt": info("Hello World", "The smallest possible mod: says hello when you load a save.",
                             ["greet | on/off | on | | | Say hello when a save is loaded"]),
        "script.rpy": '''
# Hello World - the smallest possible mod.
# "init python:" runs once when the game starts. Inside it, plain Python.

init python:

    def say_hello():
        # apex_setting reads the player's choice from the gear (or the default from mod_info.txt)
        if apex_setting("greet", True):
            apex_notify("Hello from my first mod!")

    # run say_hello every time a save is loaded, and when a new game starts
    apex_on_load(say_hello)
    apex_on_new_game(say_hello)
''',
        "READ ME.txt": '''
HELLO WORLD
-----------
What it does: shows "Hello from my first mod!" when you load a save.

Try it:
1. Restart the game. The mod is listed in Apex's Modpack Manager -> Your Mods.
2. Load a save - the message appears.
3. Change the text in script.rpy, restart, load again.

Files:
  mod_info.txt   name, author, version, description and one setting (on/off)
  script.rpy     the code
''',
    })

    # 2 ---------------------------------------------------------------- retexture (replace a picture)
    top = redden(game_png("images/CHAR/celica/celica_top_normal-530-530-1.png"))
    write("02 Replace a Picture", {
        "mod_info.txt": info("Red Tank Top (picture swap)", "Replaces the picture of Celica's tank top when she stands. No code needed."),
        "images/CHAR/celica/celica_top_normal-530-530-1.png": top,
        "READ ME.txt": '''
REPLACE A PICTURE (no code)
---------------------------
What it does: Celica's normal tank top is red when she stands.

How it works: any picture in your mod's folder that has the SAME path and name as a game picture is used
instead of the game's picture.
  game picture:  images/CHAR/celica/celica_top_normal-530-530-1.png
  your picture:  mods/<your mod>/images/CHAR/celica/celica_top_normal-530-530-1.png

Rules:
  * Same name, same folders, same picture size (here 530 x 530). A different size looks shifted.
  * Names end in  -WIDTH-HEIGHT-FRAMES.png : "-530-530-6" is an animation with 6 frames side by side.
  * Every pose is its own picture: celica_top_normal-... is standing, celica_squat_top_normal-... is squatting.

Get the game's pictures to edit:
  Mod Manager -> Mod Tools -> Export game pictures, type part of a name (e.g. celica_top_normal), Export.
  They land in mods/_exported with the right folders. Edit a copy, put it in your mod.

Check your mod: Mod Tools -> Check my mods (it warns about wrong sizes).
''',
    })

    # 3 ---------------------------------------------------------------- accessory with stats
    charm = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    dr = ImageDraw.Draw(charm)
    dr.ellipse((9, 13, 31, 35), fill=(255, 201, 77, 255), outline=(90, 50, 10, 255), width=2)
    dr.polygon([(20, 17), (23, 23), (29, 24), (24, 28), (26, 33), (20, 30), (14, 33), (16, 28), (11, 24), (17, 23)],
               fill=(255, 245, 200, 255))
    dr.line((20, 4, 20, 13), fill=(200, 200, 210, 255), width=2)
    write("03 Accessory with Stats", {
        "mod_info.txt": info("Lucky Charm", "Adds a Lucky Charm accessory to Celica's inventory. Wear it for extra luck.",
                             ["luck | number | 10 | 0 | 100 | Luck bonus", "speed | number | 0 | 0 | 100 | Speed bonus"]),
        "charm.png": charm,
        "script.rpy": '''
# Accessory with stats - an item Celica can wear (Equip -> Appearance -> Accessories).
# It doesn't change her picture, only her stats.

init python:

    apex_add_accessory(
        "lucky_charm",                      # a short id, unique inside your mod
        "Lucky Charm",                      # the name shown in the game
        icon="charm.png",                   # a picture in your mod folder (40 x 40 works well)
        description="A small charm that brings luck.",
        stats={                             # 0-100 scale, like the game shows them.
            "luck": apex_setting("luck", 10),       # stats: allure, lewdness, willpower, cooldown,
            "speed": apex_setting("speed", 0),      #        arcane, speed, luck   (minus numbers lower them)
        },
        regen=0,                            # HP and MP back per battle turn, in % (0 = none)
    )
    # The item is given once per save. To give it again: apex_give("lucky_charm")
''',
        "READ ME.txt": '''
ACCESSORY WITH STATS
--------------------
What it does: puts a Lucky Charm in Celica's inventory (once per save). Wear it in Equip -> Appearance.
The player changes its bonus with the gear in the Mod Manager (settings in mod_info.txt).

Make your own: copy apex_add_accessory(...) in script.rpy, give it a new id and name, change the stats.
Stats: allure, lewdness, willpower, cooldown, arcane, speed, luck.
''',
    })

    # 4 ---------------------------------------------------------------- custom clothing
    icon = redden(game_png("images/ICON/attire_tanktop.png"))
    write("04 Custom Clothing", {
        "mod_info.txt": info("Red Top (new clothing)", "Adds a new piece of clothing: a red top Celica can wear.",
                             ["allure | number | 5 | 0 | 100 | Allure bonus"]),
        "icon_redtop.png": icon,
        "images/CHAR/celica/celica_top_redtop-530-530-1.png": top,
        "script.rpy": '''
# Custom clothing - a NEW piece of clothing (it doesn't replace anything).

init python:

    apex_add_clothing(
        "red_top",                 # a short id, unique inside your mod
        "Red Top",                 # the name shown in the game
        area="top",                # where it's worn: top, bra, bottom, panties or shoes
        picture="redtop",          # the word used in the picture names (see READ ME)
        icon="icon_redtop.png",    # inventory picture in your mod folder
        description="A bright red top.",
        stats={"allure": apex_setting("allure", 5)},
    )
''',
        "READ ME.txt": '''
CUSTOM CLOTHING
---------------
What it does: adds "Red Top" to Celica's inventory. Equip it in Equip -> Appearance.

The pictures: the game draws clothing as its own picture on top of Celica, one picture per pose.
For a top with picture="redtop" the names are:
  standing:   images/CHAR/celica/celica_top_redtop-530-530-1.png        (this template has it)
  any pose:   images/CHAR/celica/<pose>_top_redtop-<size>.png
              e.g. celica_squat_top_redtop-530-530-1.png
Area words in the names: top/bra -> "top", bottom/panties -> "bottom", shoes -> "feet".

Poses without your picture show Celica without that piece (nothing breaks).
To cover more poses: Mod Tools -> Export game pictures -> type  _top_normal  -> you get the normal top in
EVERY pose, with the right names and sizes. Recolor or redraw them, rename "normal" to your word.

Check your mod: Mod Tools -> Check my mods.
''',
    })

    # 5 ---------------------------------------------------------------- morning scene
    write("05 Morning Scene", {
        "mod_info.txt": info("Morning Stretch", "A short scene that sometimes plays when Celica wakes up.",
                             ["chance | 1 in n | 5 | 1 | 50 | Chance each quiet morning"]),
        "script.rpy": '''
# Morning scene - your own little scene on some quiet mornings (when the game planned nothing).

init python:
    # 1 in 5 mornings by default - the player changes it with the gear
    apex_wakeup_scene("morning_stretch_scene", chance=1.0 / apex_setting("chance", 5))


# A label is a scene. Lines in quotes are said by the narrator; "celica" makes Celica say them.
label morning_stretch_scene:
    "Celica stretches as the morning sun warms the room."
    celica "Mmm... today feels like a good day."
    $ apex_give_gold(10)
    "She finds 10 gold under her pillow."
    return
''',
        "READ ME.txt": '''
MORNING SCENE
-------------
What it does: on quiet mornings, 1 in 5 by default, plays a short scene and gives 10 gold.

Write your own: change the lines under "label morning_stretch_scene:". Every line is indented by 4 spaces.
  "text"            the narrator says it
  celica "text"     Celica says it
  $ apex_give_gold(10)   a line of Python (gives gold)
  return            the scene ends (always keep it last)
''',
    })

    # 6 ---------------------------------------------------------------- starting bonus / tweak
    write("06 New Game Bonus", {
        "mod_info.txt": info("Starting Gold", "Gives Celica extra gold when you start a new game.",
                             ["gold | number | 250 | 0 | 10000 | Gold at the start"]),
        "script.rpy": '''
# New game bonus - runs once when a new game starts.

init python:

    def starting_bonus():
        apex_give_gold(apex_setting("gold", 250))
        apex_log("gave the starting gold")          # writes to log.txt in this mod's folder

    apex_on_new_game(starting_bonus)
''',
        "READ ME.txt": '''
NEW GAME BONUS
--------------
What it does: gives extra gold once, when a new game starts. The amount is a setting (gear in the Mod Manager).

Other things you can do the same way, inside the function:
  apex_give_gold(100)             gold
  apex_give("my_item_id")         one of your own items again
  apex_notify("text")             a small message on screen
  apex_log("text")                a line in log.txt (to see what your mod did)
''',
    })
    print("templates written to", OUT)


if __name__ == "__main__":
    main()
