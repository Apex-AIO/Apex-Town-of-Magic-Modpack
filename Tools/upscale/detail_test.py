"""detail_test.py - how much more detail can Celica get?  (needs ComfyUI running)

Celica standing, twice:  barefoot in her outfit (shows the feet)  and  without clothes (the body).
Columns (round 2, aiming towards realism):
  A  Current HD recipe (the installed @2 files)
  C  Tile ControlNet + DetailerIL LoRA, strength 0.60 (round 1 favourite)
  E  C + Smooth Booster LoRA 0.35: smoother, more blended skin
  F  E + realistic feet pass (feet v3 LoRA, strength 0.50)
  G  E + realistic feet pass, stronger (0.65)
Everything is shown at 2x (what the game shows with @2) + close-ups of the feet and the stomach.
(B-D detail the stacked picture in one go - a preview of the look, not yet the per-layer HD files.)
Output (opens when done): Upscale/detail_test/
"""
import os, sys, time, uuid, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spandrel
from compare_upscalers import WS, MODEL_DIR, ALPHA_MODEL, DEV, font, upscale4, bleed
from refine_compare import color_match, comfy, COMFY, COMFY_DIR, CKPT
from hd_batch import full_sheet, stack, no_shadow, shadow_mask, shadow_hd, detail_poll

OUT = os.path.join(WS, "Upscale", "detail_test")
GAME = os.path.normpath(os.path.join(WS, "..", "game"))
TILE_CN = "xinsir_controlnet_tile_sdxl.safetensors"
BODY_LORAS = [("DetailerILv2-000008.safetensors", 0.6)]
SMOOTH_LORAS = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.35)]   # C + gentle smoothing/blending
I_LORAS = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.525)]   # G with smoothing x1.5
I_FEET_LORAS = [("feet v3.safetensors", 1.12)]
SEMI_LORAS = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.35),
              ("Niji_semi_realism_v5.safetensors", 0.5)]                 # G + semi-realistic blended shading
SEMI_LORAS_STRONG = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.35),
                     ("Niji_semi_realism_v5.safetensors", 0.8)]                                                       # feet LoRA x1.4
FEET_LORAS = [("feet v3.safetensors", 0.8)]                                                        # realistic feet/toes (Feet XL)
POS_BODY = ("masterpiece, best quality, Jeddtl02, detailed skin, soft realistic shading, semi-realistic anatomy, "
            "subtle muscle definition, clean lineart, anime game sprite, simple background")
POS_SMOOTH = ("masterpiece, best quality, Jeddtl02, detailed skin, smooth blended shading, soft gradients, semi-realistic, "
              "realistic skin, subtle muscle definition, clean lineart, game sprite, simple background")
POS_FEET = ("masterpiece, best quality, Feet, perfect, barefoot, realistic feet, detailed toes, toenails, natural toe shape, "
            "smooth blended shading, semi-realistic, clean lineart")
NEG = ("blurry, soft, jpeg artifacts, noise, grain, sketch, text, bad anatomy, deformed, extra toes, missing toes, "
       "fused toes, extra fingers")
C = "images/CHAR/celica/%s-530-530-1.png"
OUTFIT = ["celica_headforwardhair_normalb", "celica", "celica_breasts", "celica_bottom_panties", "celica_top_bra",
          "celica_bottom_normal", "celica_top_normal", "celica_arms_waist",
          "celica_headforwardneck", "celica_headforward", "celica_face_normal", "celica_headforwardhair_normal"]
NUDE = ["celica_headforwardhair_normalb", "celica", "celica_breasts", "celica_arms_waist",
        "celica_headforwardneck", "celica_headforward", "celica_face_normal", "celica_headforwardhair_normal"]
SUBJECTS = {"barefoot_outfit": OUTFIT, "body": NUDE}
BG = (34, 24, 42, 255)


def smooth(img, amount, radius=14, eps=0.012):
    """edge-preserving smoothing (self-guided filter): evens out shading/gradients, keeps lines and outlines.
    amount 0 = untouched, 1 = fully filtered."""
    import cv2
    a = np.array(img).astype(np.float32)
    rgb = a[..., :3] / 255.0
    f = cv2.ximgproc.guidedFilter(guide=rgb, src=rgb, radius=radius, eps=eps)
    out = rgb * (1 - amount) + f * amount
    # line protection: dark outline pixels keep their original value (soft ramp between 0.18 and 0.32 brightness)
    lum = (rgb * [0.299, 0.587, 0.114]).sum(2, keepdims=True)
    keep = np.clip((0.32 - lum) / 0.14, 0, 1)
    a[..., :3] = np.clip(out * (1 - keep) + rgb * keep, 0, 1) * 255.0
    return Image.fromarray(a.round().astype(np.uint8), "RGBA")


def submit(img, denoise, loras, pos, cn_strength, seed=1):
    """USDU (no upscale) with LoRAs + tile ControlNet; img RGBA, see-through parts filled.  -> ticket for detail_poll"""
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    m = 64
    x0, y0 = max(bb[0] - m, 0) // 8 * 8, max(bb[1] - m, 0) // 8 * 8
    x1, y1 = min(-(-(bb[2] + m) // 8) * 8, img.width // 8 * 8), min(-(-(bb[3] + m) // 8) * 8, img.height // 8 * 8)
    box = (x0, y0, x1, y1)
    rgb = Image.fromarray(bleed(np.array(img.crop(box)), radius=16, thresh=8).round().clip(0, 255).astype(np.uint8), "RGB")
    W, H = rgb.size
    cols, rows = -(-W // 1536), -(-H // 1536)
    tw, th = -(-(-(-W // cols)) // 8) * 8, -(-(-(-H // rows)) // 8) * 8
    name = "tom_dt_%s.png" % uuid.uuid4().hex[:10]
    rgb.save(os.path.join(COMFY_DIR, "input", name))
    wf = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}}}
    model, clip, nid = ["1", 0], ["1", 1], 10
    for lname, st in loras:
        wf[str(nid)] = {"class_type": "LoraLoader", "inputs": {"model": model, "clip": clip, "lora_name": lname,
                                                               "strength_model": st, "strength_clip": st}}
        model, clip = [str(nid), 0], [str(nid), 1]
        nid += 1
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": pos}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": NEG}}
    wf["4"] = {"class_type": "LoadImage", "inputs": {"image": name}}
    wf["7"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": TILE_CN}}
    wf["8"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {"positive": ["2", 0], "negative": ["3", 0],
               "control_net": ["7", 0], "image": ["4", 0], "strength": cn_strength, "start_percent": 0.0, "end_percent": 1.0}}
    wf["5"] = {"class_type": "UltimateSDUpscaleNoUpscale", "inputs": {
        "upscaled_image": ["4", 0], "model": model, "positive": ["8", 0], "negative": ["8", 1], "vae": ["1", 2],
        "seed": seed, "steps": 14, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
        "mode_type": "Linear", "tile_width": tw, "tile_height": th, "mask_blur": 16, "tile_padding": 64,
        "seam_fix_mode": "None", "seam_fix_denoise": 0.2, "seam_fix_width": 64, "seam_fix_mask_blur": 8,
        "seam_fix_padding": 16, "force_uniform_tiles": False, "tiled_decode": False, "batch_size": 1}}
    wf["6"] = {"class_type": "PreviewImage", "inputs": {"images": ["5", 0]}}
    pid = comfy("/prompt", {"prompt": wf, "client_id": "tom"})["prompt_id"]
    return {"pid": pid, "name": name, "box": box, "img": img}


def wait(t):
    while True:
        r = detail_poll(t)
        if r is not None:
            return r
        time.sleep(0.3)


def main():
    try:
        comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first." % COMFY)
    if not os.path.exists(os.path.join(COMFY_DIR, "models", "controlnet", TILE_CN)):
        sys.exit("missing models/controlnet/%s - the download has not finished yet" % TILE_CN)
    os.makedirs(OUT, exist_ok=True)
    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, "4x-ReboutBlend.pth")).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()
    t0 = time.time()
    outs = []
    for sname, layers in SUBJECTS.items():
        rels = [C % n for n in layers]
        full = stack([full_sheet(r) for r in rels])
        bb = full.getbbox()
        box = (max(bb[0] - 16, 0), max(bb[1] - 16, 0), min(bb[2] + 16, 530), min(bb[3] + 16, 530))
        van = full.crop(box)
        w, h = van.size
        sm = shadow_mask(np.array(van))
        body = no_shadow(van)
        x4 = upscale4(model, amodel, body)
        x8 = color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), body)
        alpha = x8.getchannel("A")

        def fin(img):
            img = img.copy()
            img.putalpha(alpha)                                        # outline always = the sprite's own
            if sm.any():
                sh = shadow_hd(sm, img.size)
                sh.alpha_composite(img)
                img = sh
            return img.resize((w * 2, h * 2), Image.LANCZOS)

        # A: the installed per-layer HD files
        hd = stack([Image.open(os.path.join(GAME, r.replace("/", os.sep))[:-4] + "@2.png").convert("RGBA") for r in rels])
        cols = [("VANILLA (2x)", van.resize((w * 2, h * 2), Image.NEAREST)),
                ("A  current HD recipe (0.28)", hd.crop(tuple(v * 2 for v in box)))]
        print("%s: G..." % sname, flush=True)
        re_ = wait(submit(x8, 0.60, SMOOTH_LORAS, POS_SMOOTH, 0.80))          # G's body (E)
        a = np.array(alpha) > 8
        ys = np.nonzero(a.any(1))[0]
        top = int(ys[-1] - (ys[-1] - ys[0]) * 0.13)
        xs = np.nonzero(a[top:].any(0))[0]
        fb = (max(xs[0] - 96, 0), max(top - 96, 0), min(xs[-1] + 96, re_.width), re_.height)
        mask = Image.new("L", (fb[2] - fb[0], fb[3] - fb[1]), 0)
        ImageDraw.Draw(mask).rectangle((48, 48, mask.width - 49, mask.height - 1), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(24))                 # soft blend into the legs
        rg = re_.copy()
        rg.paste(wait(submit(re_.crop(fb), 0.65, FEET_LORAS, POS_FEET, 0.65)), fb[:2], mask)
        cols.append(("G  favourite", fin(rg)))
        # the AI paints the blending itself (semi-realism LoRA) - no filters, so detail and lines stay
        for lab, loras, dn in (("P  G + semi-realism LoRA 0.5", SEMI_LORAS, 0.60),
                               ("Q  G + semi-realism LoRA 0.8", SEMI_LORAS_STRONG, 0.60),
                               ("R  Q at strength 0.70", SEMI_LORAS_STRONG, 0.70)):
            print("%s: %s..." % (sname, lab), flush=True)
            r = wait(submit(x8, dn, loras, POS_SMOOTH, 0.80))
            r.paste(wait(submit(r.crop(fb), 0.65, FEET_LORAS, POS_FEET, 0.65)), fb[:2], mask)
            cols.append((lab, fin(r)))
        print("%s done (%.0fs)" % (sname, time.time() - t0), flush=True)

        # sheet: everything at 2x
        tw, th, cap = w * 2, h * 2, 28
        can = Image.new("RGBA", (12 + len(cols) * (tw + 12), th + cap + 60), BG)
        d = ImageDraw.Draw(can)
        d.text((12, 12), "%s  -  all at 2x (what the game shows with @2)" % sname, font=font(20), fill=(240, 220, 255))
        for i, (lab, im) in enumerate(cols):
            x = 12 + i * (tw + 12)
            d.text((x, 50), lab, font=font(14), fill=(255, 210, 140) if i < 2 else (230, 230, 230))
            can.alpha_composite(im, (x, 50 + cap))
        p = os.path.join(OUT, sname + ".png")
        can.convert("RGB").save(p)
        outs.append(p)
        # close-ups at 4x of the 1x picture: feet and stomach
        for zname, zb in (("feet", (0.0, 0.84, 1.0, 1.0)), ("stomach", (0.25, 0.30, 0.80, 0.55))):
            b = (int(zb[0] * w) * 2, int(zb[1] * h) * 2, int(zb[2] * w) * 2, int(zb[3] * h) * 2)
            zw, zh = (b[2] - b[0]) * 2, (b[3] - b[1]) * 2
            can = Image.new("RGBA", (12 + len(cols) * (zw + 12), zh + cap + 60), BG)
            d = ImageDraw.Draw(can)
            d.text((12, 12), "%s - %s close-up" % (sname, zname), font=font(20), fill=(240, 220, 255))
            for i, (lab, im) in enumerate(cols):
                x = 12 + i * (zw + 12)
                d.text((x, 50), lab, font=font(14), fill=(255, 210, 140) if i < 2 else (230, 230, 230))
                can.alpha_composite(im.crop(b).resize((zw, zh), Image.LANCZOS), (x, 50 + cap))
            p = os.path.join(OUT, "%s_%s.png" % (sname, zname))
            can.convert("RGB").save(p)
            outs.append(p)
    print("done in %.1f min" % ((time.time() - t0) / 60))
    if "--no-open" not in sys.argv:
        for p in outs:
            os.startfile(p)


if __name__ == "__main__":
    main()
