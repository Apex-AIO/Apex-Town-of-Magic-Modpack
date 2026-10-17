"""gamewait.py - wait (with a hard time limit) until a condition is true inside the running game.

usage: python gamewait.py "<python expression>" [--timeout 90] [--every 2] [--tick "<python run each poll>"]
Exit codes: 0 = condition became true, 1 = timed out, 2 = THE GAME IS NOT ANSWERING (closed/crashed) -> stop at once.
Prints one line per poll so progress is visible.
"""
import sys, os, time, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("expr")
ap.add_argument("--timeout", type=float, default=90)
ap.add_argument("--every", type=float, default=2)
ap.add_argument("--tick", default="")
a = ap.parse_args()
t0, misses = time.time(), 0
while time.time() - t0 < a.timeout:
    code = (a.tick + "\n" if a.tick else "") + "RESULT = bool(%s)" % a.expr
    r = subprocess.run([sys.executable, os.path.join(HERE, "gamecmd.py"), code, "--wait", "4"], capture_output=True, text=True)
    out = r.stdout.strip()
    if "no answer" in out:
        misses += 1
        print("[%3.0fs] game not answering (%d)" % (time.time() - t0, misses), flush=True)
        if misses >= 2:
            print("GAME NOT RUNNING - stopping")
            sys.exit(2)
    else:
        misses = 0
        val = out.splitlines()[0] if out else ""
        print("[%3.0fs] %s" % (time.time() - t0, val), flush=True)
        if val == "true":
            sys.exit(0)
    time.sleep(a.every)
print("timed out after %.0fs" % a.timeout)
sys.exit(1)
