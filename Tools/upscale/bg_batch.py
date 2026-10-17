"""bg_batch.py - HD (@2 / @4) backgrounds with the locked background recipe B.  Needs ComfyUI running.

    python bg_batch.py               seen-in-game backgrounds first, then every other one (skips finished files)
    python bg_batch.py --seen-only   only the ones you have seen in game
    python bg_batch.py --only l_home --force

Recipe B (locked 2026-10-18): 4x-ReboutBlend x8 + colour match -> x4 -> SDXL detailer 0.30, tile ControlNet 0.80,
DetailerILv2 0.6, scenery prompt, 14 steps -> @4 (x4) and @2 (x2, shrunk from the @4).
Glow overlays and animation frames (fire glow, sea, portal glow ...) get no AI pass (upscale only): the AI would make
every frame a little different and they would flicker.
Every file the game loads is done on its own (base picture, _day/_evening/_night window views, _lights ...).
The background list comes from the art catalog (Tools/art/bg_catalog.py); identical files are rendered once.
Output: Mods/hd_sprites_mod/images/BG|BGANIM|EVENT/<name>@2.png / @4.png, copied into game/images (--no-install skips).
"""
import os, sys, io, time, shutil, sqlite3, argparse
from collections import deque
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "art"))
import hd_batch as H
from compare_upscalers import upscale4, MODEL_DIR, ALPHA_MODEL, DEV
from refine_compare import color_match
from catalog import read_index, read_bytes, ARCHIVES, DB
import spandrel

POS_BG = ("masterpiece, best quality, scenery, no humans, detailed background, game background art, clean lineart, "
          "smooth blended shading, soft gradients, detailed textures")
NEG_BG = "1girl, person, people, character, text, watermark, signature, blurry, jpeg artifacts, noise, grain, deformed"
RECIPE_B = dict(denoise=0.30, loras=[("DetailerILv2-000008.safetensors", 0.6)], cn=(H.CN_TILE, 0.80), steps=14,
                pos=POS_BG, neg=NEG_BG, seed=7)
QUEUE = 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seen-only", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()
    try:
        H.comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first, then run this again." % H.COMFY)
    if not os.path.exists(DB):
        sys.exit("No art catalog - run Tools/art/catalog.py and Tools/art/bg_catalog.py first.")
    db = sqlite3.connect(DB)
    rows = db.execute("""select rel, anim, dup_of, seen from backgrounds where rel not like '%/debug%'
                         order by seen desc, rel""").fetchall()
    if a.seen_only:
        rows = [r for r in rows if r[3]]
    if a.only:
        rows = [r for r in rows if a.only in r[0]]

    def out_path(rel, s):
        return os.path.join(H.MOD, rel.replace("/", os.sep))[:-4] + "@%d.png" % s

    def done(rel):
        return all(os.path.exists(out_path(rel, s)) for s in (2, 4))

    def install(p):
        if not a.no_install:
            dst = os.path.join(H.GAME, os.path.relpath(p, H.MOD))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)

    def save(rel, img4):
        w, h = img4.width // 4, img4.height // 4
        for s, im in ((4, img4), (2, img4.resize((w * 2, h * 2), Image.LANCZOS))):
            p = out_path(rel, s)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            H.clean_alpha(im).save(p, compress_level=1)
            install(p)

    def copy(src, dst):
        for s in (2, 4):
            os.makedirs(os.path.dirname(out_path(dst, s)), exist_ok=True)
            shutil.copy2(out_path(src, s), out_path(dst, s))
            install(out_path(dst, s))

    todo = [r for r in rows if a.force or not done(r[0])]
    print("%d backgrounds, %d to make (%d seen in game first)" % (len(rows), len(todo), sum(1 for r in todo if r[3])),
          flush=True)
    if not todo:
        return
    idx = {}
    for arch in ARCHIVES:
        idx.update({k: (arch, v) for k, v in read_index(arch).items()})
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, H.MODEL)).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    def up4(img):
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)
        H.free_vram()                                            # leave the VRAM to ComfyUI (stalls otherwise)
        return x8.resize((w * 4, h * 4), Image.LANCZOS)

    t0, n, waiting, later = time.time(), 0, deque(), []
    for rel, anim, dup_of, seen in todo:
        if dup_of and (done(dup_of) or any(dup_of == x[0] for x in todo)):
            later.append((dup_of, rel))                 # identical file: copied when its twin is done
            continue
        arch, e = idx[rel]
        img = Image.open(io.BytesIO(read_bytes(arch, e))).convert("RGBA")
        big = up4(img)
        name = os.path.basename(rel)
        if anim or "glow" in name:
            save(rel, big)                              # no AI: animation frames / glows must not flicker
            n += 1
            print("[%d/%d] %s  (upscale only)  %.0fs" % (n, len(todo), rel[7:], time.time() - t0), flush=True)
        else:
            t = H.detail_submit(big, **RECIPE_B)
            if t is not None:
                t["label"] = rel
            waiting.append((rel, big, t))
        while waiting and (len(waiting) >= QUEUE or rel == todo[-1][0]):
            wrel, wbig, t = waiting[0]
            d = wbig if t is None else H.detail_poll(t)
            if d is None:
                time.sleep(0.3)
                continue
            waiting.popleft()
            save(wrel, d)
            n += 1
            left = (time.time() - t0) / n * (len(todo) - n - len(later)) / 60
            print("[%d/%d] %s  %.0fs elapsed, ~%.0f min left" % (n, len(todo), wrel[7:], time.time() - t0, left), flush=True)
    while waiting:
        wrel, wbig, t = waiting[0]
        d = wbig if t is None else H.detail_poll(t)
        if d is None:
            time.sleep(0.3)
            continue
        waiting.popleft()
        save(wrel, d)
        n += 1
        print("[%d/%d] %s" % (n, len(todo), wrel[7:]), flush=True)
    for src, dst in later:
        if done(src):
            copy(src, dst)
            print("   copied (identical to %s): %s" % (os.path.basename(src), dst[7:]), flush=True)
    print("all done in %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
