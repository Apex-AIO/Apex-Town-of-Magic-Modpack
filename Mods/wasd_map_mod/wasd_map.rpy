# wasd_map.rpy  -  WASD Map Movement
#
# Moves around the map with W / A / S / D as well as the arrow keys (up, left, down, right).  The big purple arrows on the
# map border can still be clicked, and the arrow keys (or whatever you set in the game's key settings) keep working.
#
# How: the map arrows ask the game's get_button_keysymlist("MAP NORTH" / "MAP WEST" / "MAP SOUTH" / "MAP EAST") for their
# keys.  This mod adds W / A / S / D to those four answers.  Nothing is saved and no game setting is changed.
#
# Uninstall: delete wasd_map.rpy / wasd_map.rpyc.

init 998 python:
    WASD_OK = tom_mod_ok('wasd_map', hooks=['get_button_keysymlist'], needs=[])

init 1000 python:
    if WASD_OK:
        _wasd_keys = {"MAP NORTH": "K_w", "MAP WEST": "K_a", "MAP SOUTH": "K_s", "MAP EAST": "K_d"}
        _wasd_orig_keysymlist = get_button_keysymlist

        def get_button_keysymlist(action=""):
            keys = _wasd_orig_keysymlist(action)
            extra = _wasd_keys.get(action)
            if extra is not None and extra not in keys:
                return list(keys) + [extra]
            return keys
