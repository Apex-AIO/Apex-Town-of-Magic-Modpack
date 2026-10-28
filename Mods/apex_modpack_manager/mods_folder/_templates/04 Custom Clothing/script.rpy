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

    # Same thing with the game's own fields (use these instead of area= when you need more control):
    #   equip_area=["top|0", "sleeves|1"]   areas it is worn on (first = main area); slots: top, bottom, feet, head, sleeves; levels |0 / |1
    #   block_area=["top|1"]                areas it covers, so nothing else fits there
    #   order=2500, properties=[...], stripable=True, molestable=True, extra={"extra_cost": 0}
