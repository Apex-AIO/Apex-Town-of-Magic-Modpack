"""ckpt_compare.py - what does each checkpoint in ComfyUI/models/checkpoints do to the style?  (needs ComfyUI running)

Same recipe as the HD sprites (4x-ReboutBlend x8 + colour match), then the detailer pass with EVERY checkpoint,
at a low strength (denoise 0.30 by default - checkpoints can change the look a lot).
Subjects: Celica standing in her starting outfit (all 13 layers stacked) and the slime.
  (For speed the stacked picture is detailed in one go; the real HD batch details layer by layer in context,
   so the final result can differ a little - this is a style preview.)
Pony checkpoints (name contains "pony") get Pony-style prompts (score_9, ...) automatically.

Output (opens when done):  Upscale/ckpt_compare/<subject>_d<denoise>.png       every checkpoint side by side at 2x
                           Upscale/ckpt_compare/<subject>_d<denoise>_zoom.png  close-ups (face / highlights)
Options:  --denoise 0.45     --only wai dasiwa ...  (checkpoints whose name contains one of these)
"""
import os, sys, glob, time, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spandrel
from compare_upscalers import WS, MODEL_DIR, ALPHA_MODEL, DEV, font, upscale4
from refine_compare import color_match, comfy, COMFY, COMFY_DIR, POS, NEG
from hd_batch import full_sheet, stack, no_shadow, shadow_mask, shadow_hd, detail_submit, detail_poll

OUT = os.path.join(WS, "Upscale", "ckpt_compare")
CKPT_DIR = os.path.join(COMFY_DIR, "models", "checkpoints")
CURRENT = "waiIllustriousSDXL_v170.safetensors"
PONY_POS = "score_9, score_8_up, score_7_up, source_anime, " + POS
PONY_NEG = "score_4, score_5, score_6, " + NEG
C = "images/CHAR/celica/%s-530-530-1.png"
CELICA = ["celica_headforwardhair_normalb", "celica", "celica_breasts", "celica_bottom_panties", "celica_top_bra",
          "celica_feet_normal", "celica_bottom_normal", "celica_top_normal", "celica_arms_waist",
          "celica_headforwardneck", "celica_headforward", "celica_face_normal", "celica_headforwardhair_normal"]
SUBJECTS = {
    # name: (layers, frame width, zoom box in 1x pixels of the cropped picture: centre x, centre y)
    "celica_standing": ([C % n for n in CELICA], 530, None),
    "slime": (["images/CHAR/slime/slime-530-530-4.png"], 530, None),
}
BG = (34, 24, 42, 255)


def subject_picture(layers, fw):
    pic = stack([full_sheet(l).crop((0, 0, fw, full_sheet(l).height)) for l in layers])
    bb = pic.getbbox()
    m = 16
    return pic.crop((max(bb[0] - m, 0), max(bb[1] - m, 0), min(bb[2] + m, pic.width), min(bb[3] + m, pic.height)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--denoise", type=float, default=0.30)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    try:
        comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first." % COMFY)
    ckpts = sorted(os.path.basename(p) for p in glob.glob(os.path.join(CKPT_DIR, "*.safetensors")))
    if a.only:
        ckpts = [c for c in ckpts if any(o.lower() in c.lower() for o in a.only)]
    print("%d checkpoints, denoise %.2f" % (len(ckpts), a.denoise), flush=True)
    os.makedirs(OUT, exist_ok=True)

    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, "4x-ReboutBlend.pth")).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()

    subj = {}
    for name, (layers, fw, _) in SUBJECTS.items():
        van = subject_picture(layers, fw)
        sm = shadow_mask(np.array(van))
        body = no_shadow(van)
        w, h = body.size
        x4 = upscale4(model, amodel, body)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), body)
        subj[name] = {"van": van, "x8": x8, "shadow": sm if sm.any() else None, "res": {}}
        print("prepared", name, van.size, flush=True)

    def finish(name, img):
        s = subj[name]
        if s["shadow"] is not None:
            sh = shadow_hd(s["shadow"], img.size)
            sh.alpha_composite(img)
            img = sh
        w, h = s["van"].size
        return img.resize((w * 2, h * 2), Image.LANCZOS)

    for name in subj:
        subj[name]["res"]["ESRGAN only (no checkpoint)"] = finish(name, subj[name]["x8"])

    # jobs grouped per checkpoint (each checkpoint is loaded once), up to 3 queued in ComfyUI
    jobs = [(c, n) for c in ckpts for n in subj]
    inflight, t0, done = [], time.time(), 0
    while jobs or inflight:
        while jobs and len(inflight) < 3:
            c, n = jobs.pop(0)
            pony = "pony" in c.lower()
            t = detail_submit(subj[n]["x8"], a.denoise, ckpt=c, pos=PONY_POS if pony else None, neg=PONY_NEG if pony else None)
            inflight.append((c, n, t))
        got = False
        for item in list(inflight):
            c, n, t = item
            r = detail_poll(t)
            if r is not None:
                inflight.remove(item)
                label = os.path.splitext(c)[0] + ("   (current)" if c == CURRENT else "")
                subj[n]["res"][label] = finish(n, r)
                done += 1
                got = True
                print("[%d/%d] %s - %s  %.0fs" % (done, len(ckpts) * len(subj), n, c, time.time() - t0), flush=True)
        if not got:
            time.sleep(0.3)

    outs = []
    for n, s in subj.items():
        w, h = s["van"].size
        tiles = [("VANILLA (2x)", s["van"].resize((w * 2, h * 2), Image.NEAREST))] + list(s["res"].items())
        cols = 6 if w < 200 else 4
        tw, th = w * 2, h * 2
        cap = 30
        rows = -(-len(tiles) // cols)
        can = Image.new("RGBA", (cols * (tw + 12) + 12, rows * (th + cap + 12) + 50), BG)
        d = ImageDraw.Draw(can)
        d.text((12, 12), "%s  -  detailer denoise %.2f  (all at 2x = what the game shows with @2)" % (n, a.denoise), font=font(20), fill=(240, 220, 255))
        for i, (lab, im) in enumerate(tiles):
            x, y = 12 + (i % cols) * (tw + 12), 50 + (i // cols) * (th + cap + 12)
            d.text((x, y + 4), lab[:40], font=font(14), fill=(255, 210, 140) if "current" in lab or "VANILLA" in lab else (230, 230, 230))
            can.alpha_composite(im, (x, y + cap))
        p = os.path.join(OUT, "%s_d%.2f.png" % (n, a.denoise))
        can.convert("RGB").save(p)
        outs.append(p)
        # close-ups: celica's face/upper body, the slime's middle
        if n.startswith("celica"):
            bb = (int(w * 0.30) * 2, int(h * 0.0) * 2, int(w * 0.85) * 2, int(h * 0.32) * 2)
        else:
            bb = (int(w * 0.1) * 2, int(h * 0.1) * 2, int(w * 0.9) * 2, int(h * 0.9) * 2)
        z = 2
        zw, zh = (bb[2] - bb[0]) * z, (bb[3] - bb[1]) * z
        cols = max(1, min(5, 2400 // (zw + 12)))
        rows = -(-len(tiles) // cols)
        can = Image.new("RGBA", (cols * (zw + 12) + 12, rows * (zh + cap + 12) + 50), BG)
        d = ImageDraw.Draw(can)
        d.text((12, 12), "%s close-up  -  denoise %.2f" % (n, a.denoise), font=font(20), fill=(240, 220, 255))
        for i, (lab, im) in enumerate(tiles):
            x, y = 12 + (i % cols) * (zw + 12), 50 + (i // cols) * (zh + cap + 12)
            d.text((x, y + 4), lab[:48], font=font(14), fill=(255, 210, 140) if "current" in lab or "VANILLA" in lab else (230, 230, 230))
            can.alpha_composite(im.crop(bb).resize((zw, zh), Image.LANCZOS), (x, y + cap))
        p = os.path.join(OUT, "%s_d%.2f_zoom.png" % (n, a.denoise))
        can.convert("RGB").save(p)
        outs.append(p)
    print("done in %.1f min" % ((time.time() - t0) / 60))
    for p in outs:
        print(" ", p)
        if not a.no_open:
            os.startfile(p)


if __name__ == "__main__":
    main()
