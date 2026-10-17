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
