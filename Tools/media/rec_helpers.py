# Frame recorder for README GIFs - run INSIDE the game through the debug bridge:
#     python Tools/scripts/gamecmd.py -f Tools/media/rec_helpers.py
# then:  rec_start("name", seconds=6, fps=12)   -> game/claude_debug/rec/<name>/0000.png ... + times.txt
#        snap("name", i)                        -> one numbered frame now (for step-by-step GIFs)
# GIFs are made from the frames with Tools/media/make_gif.py.
import os, time

def _rec_dir(name):
    d = os.path.join(config.basedir, "game", "claude_debug", "rec", name)
    os.makedirs(d, exist_ok=True)
    return d

store._REC = {"on": False}

def _rec_tick():
    r = store._REC
    if not r.get("on"):
        return
    now = time.time()
    if now >= r["end"]:
        r["on"] = False
        with open(os.path.join(r["dir"], "times.txt"), "w") as f:
            f.write("\n".join("%.3f" % t for t in r["times"]))
        return
    if now - r["last"] < 1.0 / r["fps"]:
        return
    r["last"] = now
    data = renpy.screenshot_to_bytes(None)
    with open(os.path.join(r["dir"], "%04d.png" % len(r["times"])), "wb") as f:
        f.write(data)
    r["times"].append(now - r["t0"])

def rec_start(name, seconds=6.0, fps=12):
    d = _rec_dir(name)
    for fn in os.listdir(d):
        os.remove(os.path.join(d, fn))
    now = time.time()
    store._REC.update(on=True, dir=d, fps=fps, t0=now, last=0.0, end=now + seconds, times=[])

def snap(name, i):
    renpy.screenshot(os.path.join(_rec_dir(name), "%04d.png" % i))

# storyboard: run steps [(function or None, seconds to wait before the frame is taken), ...], one frame per step
store._STORY = {"steps": [], "i": 0, "next": 0.0, "name": "", "shot": False}

def _story_tick():
    s = store._STORY
    if not s["steps"] or time.time() < s["next"]:
        return
    if s["shot"]:
        snap(s["name"], s["i"])
        s["i"] += 1
        s["shot"] = False
        if s["i"] >= len(s["steps"]):
            s["steps"] = []
        return
    fn, wait = s["steps"][s["i"]]
    if fn is not None:
        try:
            fn()
        except Exception as e:
            open(os.path.join(_rec_dir(s["name"]), "error.txt"), "a").write("%d %r\n" % (s["i"], e))
        renpy.restart_interaction()
    s["shot"] = True
    s["next"] = time.time() + wait

def story(name, steps):
    d = _rec_dir(name)
    for fn in os.listdir(d):
        os.remove(os.path.join(d, fn))
    store._STORY.update(steps=list(steps), i=0, next=0.0, name=name, shot=False)

def story_done():
    return not store._STORY["steps"]

store.rec_start, store.snap, store.story, store.story_done = rec_start, snap, story, story_done
if not any(getattr(f, "__name__", "") == "_story_tick" for f in config.periodic_callbacks):
    config.periodic_callbacks.append(_story_tick)
if not any(getattr(f, "__name__", "") == "_rec_tick" for f in config.periodic_callbacks):
    config.periodic_callbacks.append(_rec_tick)
RESULT = "recorder ready"
