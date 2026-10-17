"""bg_test.py - test renders for background HD: a few locations x a few recipes, side by side.  Needs ComfyUI.

    python bg_test.py                                  l_home, l_clothingshop, l_forest
    python bg_test.py --locs l_tavern,l_plaza --time evening

Every layer the game loads is upscaled on its own (base picture, the _<time> window view, _lights), then stacked
the way the game draws them (sky colour, base, lights, window view) for the comparison.  Output (local only):
    Upscale/bg_test/<location>.png   whole picture per recipe + two close-ups at the size a 4K window shows
Recipes:
    A  upscale only      4x-ReboutBlend x8 + colour match (no AI repaint)
    B  light detail      + SDXL detailer 0.30, tile ControlNet 0.8, Detailer LoRA, scenery prompt
    C  like characters   + detailer 0.55 with the characters' recipe-P LoRAs (smooth, semi-realism)
"""
import os, sys, time, argparse
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "art"))
import hd_batch as H
from compare_upscalers import upscale4, MODEL_DIR, ALPHA_MODEL, DEV
from refine_compare import color_match
from catalog import read_index, read_bytes, ARCHIVES
import spandrel

WS = H.WS
OUT = os.path.join(WS, "Upscale", "bg_test")
POS_BG = ("masterpiece, best quality, scenery, no humans, detailed background, game background art, clean lineart, "
          "smooth blended shading, soft gradients, detailed textures")
NEG_BG = ("1girl, person, people, character, text, watermark, signature, blurry, jpeg artifacts, noise, grain, deformed")
RECIPES = {
    "B": dict(denoise=0.30, loras=[("DetailerILv2-000008.safetensors", 0.6)], cn=(H.CN_TILE, 0.80), steps=14,
              pos=POS_BG, neg=NEG_BG),
    "C": dict(denoise=0.55, loras=H.P_LORAS, cn=(H.CN_TILE, 0.80), steps=14, pos=POS_BG, neg=NEG_BG),
}
_idx = {}


def load(rel):
    if not _idx:
        for a in ARCHIVES:
            _idx.update({k: (a, v) for k, v in read_index(a).items()})
    if rel not in _idx:
        return None
    a, e = _idx[rel]
    import io
    return Image.open(io.BytesIO(read_bytes(a, e))).convert("RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locs", default="l_home,l_clothingshop,l_forest")
    ap.add_argument("--time", default="day")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    try:
        H.comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running - start it first.")
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, H.MODEL)).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    def up4(img):
        """x8 like the characters, then down to x4 (= the @4 file a 4K window shows)"""
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)
        return x8.resize((w * 4, h * 4), Image.LANCZOS)

    t0 = time.time()
    for loc in a.locs.split(","):
        layers = [("base", "images/BG/%s.png" % loc), ("lights", "images/BG/%s_lights.png" % loc),
                  ("view", "images/BG/%s_%s.png" % (loc, a.time))]
        layers = [(k, r, load(r)) for k, r in layers]
        layers = [(k, r, im) for k, r, im in layers if im is not None]
        res = {"vanilla": {}, "A": {}, "B": {}, "C": {}}
        jobs = []
        for k, rel, im in layers:
            res["vanilla"][k] = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
            res["A"][k] = up4(im)
            for rname, rc in RECIPES.items():
                t = H.detail_submit(res["A"][k], seed=7, **rc)
                jobs.append((rname, k, t))
        for rname, k, t in jobs:
            if t is None:
                res[rname][k] = res["A"][k]
                continue
            while True:
                d = H.detail_poll(t)
                if d is not None:
                    res[rname][k] = d
                    break
                time.sleep(0.5)
            print("   %s %s %s done (%.0fs)" % (loc, rname, k, time.time() - t0), flush=True)
        # stack like the game: sky colour, base, lights, window view
        W, Hh = res["A"]["base"].size
        full = {}
        for rname in ("vanilla", "A", "B", "C"):
            c = Image.new("RGBA", (W, Hh), (150, 190, 230, 255))
            for k in ("base", "lights", "view"):
                if k in res[rname]:
                    c.alpha_composite(res[rname][k])
            full[rname] = c.convert("RGB")
            if rname != "vanilla":
                full[rname].save(os.path.join(OUT, "%s_%s.png" % (loc, rname)))
        # sheet: 4 whole pictures (each 760 wide) + 2 close-ups at full @4 size
        tw = 760
        th = int(Hh * tw / W)
        labels = {"vanilla": "original (pixel x4)", "A": "A upscale only", "B": "B light detail 0.30",
                  "C": "C like characters 0.55"}
        from PIL import ImageDraw
        sheet = Image.new("RGB", (tw * 2 + 10, th * 2 + 10 + 2 * (420 + 10) + 30), (25, 22, 30))
        for i, rname in enumerate(("vanilla", "A", "B", "C")):
            x, y = (i % 2) * (tw + 10), (i // 2) * (th + 10)
            sheet.paste(full[rname].resize((tw, th), Image.LANCZOS), (x, y))
            ImageDraw.Draw(sheet).text((x + 8, y + 6), labels[rname], fill=(255, 255, 0))
        crops = [(int(W * 0.30), int(Hh * 0.25)), (int(W * 0.62), int(Hh * 0.55))]
        cw, ch = 380, 420
        y0 = th * 2 + 20
        for j, (cx, cy) in enumerate(crops):
            for i, rname in enumerate(("vanilla", "A", "B", "C")):
                box = (cx, cy, cx + cw, cy + ch)
                sheet.paste(full[rname].crop(box), (i * (cw + 3), y0 + j * (ch + 10)))
        p = os.path.join(OUT, "%s.png" % loc)
        sheet.save(p)
        print("sheet:", p, flush=True)
    print("all done in %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
