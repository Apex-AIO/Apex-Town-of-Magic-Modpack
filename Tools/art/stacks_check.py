"""stacks_check.py - compares the art catalog's context ("layers under this one") with the real layer stacks the game
builds, recorded by claude_debug.rpy into game/claude_debug/stacks.txt (play, or run a sweep from the bridge).

    python stacks_check.py              -> Catalog/stacks_check.txt + summary
    python stacks_check.py --import     also stores the stacks in art.db (table "stacks") for the atlas

For each layer in a recorded stack, the layers before it are what the game really draws under it.
  OK          every context layer the catalog chose is drawn under it in the game
  ABOVE       the catalog put a layer in its context that the game draws ON TOP of it (wrong context)
  ABSENT      a context layer the game didn't use in this stack (another outfit/head/mood - usually fine)
"""
import os, sys, json, sqlite3, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import DB, CAT, GAME

STACKS = os.path.join(GAME, "claude_debug", "stacks.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--import", dest="imp", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(DB)
    ctx = {r: json.loads(c) for r, c in db.execute("select rel, context from roles")}
    role = dict(db.execute("select rel, role from roles"))
    stacks = []
    for line in open(STACKS, encoding="utf8"):
        parts = [p for p in line.rstrip("\n").split("\t") if p]
        if len(parts) > 1:
            stacks.append(parts)
    verdict = collections.Counter()
    problems = collections.defaultdict(set)
    order = collections.Counter()                       # (role below, role above) pairs seen
    for st in stacks:
        pos = {}
        for i, p in enumerate(st):
            pos.setdefault(p, i)
        for i, p in enumerate(st):
            if p not in ctx:
                continue
            for q in st[:i]:
                if q in role and q != p:
                    order[(role[q], role[p])] += 1
            for c in ctx[p]:
                if c not in pos:
                    verdict["ABSENT"] += 1
                elif pos[c] > pos[p]:
                    verdict["ABOVE"] += 1
                    problems["ABOVE"].add("%s  <- context %s is drawn above it" % (p.split("/")[-1], c.split("/")[-1]))
                else:
                    verdict["OK"] += 1
    with open(os.path.join(CAT, "stacks_check.txt"), "w", encoding="utf8") as f:
        f.write("%d recorded stacks\n%s\n\n" % (len(stacks), dict(verdict)))
        for k, v in problems.items():
            f.write("== %s (%d)\n" % (k, len(v)) + "\n".join("   " + x for x in sorted(v)) + "\n\n")
        f.write("== drawing order seen (role below -> role above: times)\n")
        for (lo, hi), n in order.most_common():
            back = order.get((hi, lo), 0)
            f.write("   %-12s -> %-12s %6d%s\n" % (lo, hi, n, ("   (also the other way round %d times)" % back) if back else ""))
    print("recorded stacks:", len(stacks), " context checks:", dict(verdict))
    for k, v in problems.items():
        print(" ", k, len(v), "e.g.", sorted(v)[:3])
    if a.imp:
        db.execute("DROP TABLE IF EXISTS stacks")
        db.execute("CREATE TABLE stacks(id INTEGER PRIMARY KEY, base TEXT, layers TEXT)")
        db.executemany("INSERT INTO stacks(base, layers) VALUES (?,?)", [(s[0], json.dumps(s[1:])) for s in stacks])
        db.commit()
        print("stacks stored in art.db")


if __name__ == "__main__":
    main()
