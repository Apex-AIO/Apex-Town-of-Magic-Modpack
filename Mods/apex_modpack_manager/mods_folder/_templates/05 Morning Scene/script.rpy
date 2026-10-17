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
