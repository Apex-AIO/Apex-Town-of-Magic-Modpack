# New game bonus - runs once when a new game starts.

init python:

    def starting_bonus():
        apex_give_gold(apex_setting("gold", 250))
        apex_log("gave the starting gold")          # writes to log.txt in this mod's folder

    apex_on_new_game(starting_bonus)
