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
