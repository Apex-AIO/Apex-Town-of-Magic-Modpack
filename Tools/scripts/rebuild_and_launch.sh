#!/bin/sh
# dev helper: close the game, rebuild Apex_Modpack.rpa, start the game, wait for the main menu
cd "$(dirname "$0")"
python gamecmd.py "renpy.quit()" --wait 3 >/dev/null 2>&1; sleep 3
python ../build_modpack.py > build_last.log 2>&1; s=$?; tail -12 build_last.log; [ $s = 0 ] || exit 1
cd ../../.. && (nohup ./TownOfMagic.exe >/dev/null 2>&1 &)
cd "Claude Workspace/Tools/scripts" && sleep 8 && python gamewait.py "renpy.get_screen('main_menu') is not None" --timeout 90 --every 3
