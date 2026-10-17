"""gamecmd.py - run Python inside the running game through claude_debug.rpy and print the result.
usage: python gamecmd.py "code"     or     python gamecmd.py -f file.py      [--wait SECONDS]
"""
import sys, os, time
GAME = (os.path.join(os.environ["TOM_GAME_DIR"], "game", "claude_debug") if os.environ.get("TOM_GAME_DIR") else
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game", "claude_debug")))

args = sys.argv[1:]
wait = 20.0
if "--wait" in args:
    i = args.index("--wait"); wait = float(args[i + 1]); del args[i:i + 2]
src = open(args[1], encoding="utf8").read() if args[0] == "-f" else args[0]
out = os.path.join(GAME, "out.txt")
if os.path.exists(out):
    os.remove(out)
with open(os.path.join(GAME, "cmd.py"), "w", encoding="utf8") as f:
    f.write(src)
t = time.time()
while time.time() - t < wait:
    if os.path.exists(out):
        time.sleep(0.2)
        print(open(out, encoding="utf8").read())
        sys.exit(0)
    time.sleep(0.25)
print("[no answer in %.0fs - is the game running with claude_debug.rpy?]" % wait)
sys.exit(1)
