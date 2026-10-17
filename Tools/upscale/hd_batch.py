"""hd_batch.py - makes HD (@2 / @4) sprites with the locked-in recipe, for a whole list of game images, and installs them.

Recipe (chosen 2026-10-16):  4x-ReboutBlend x8  ->  colour match to vanilla  ->  SDXL detailer (denoise 0.28,
faces 0.10)  ->  shrunk to @2 (2x) and @4 (4x).  Needs ComfyUI running (http://127.0.0.1:8000).

How it works
  * The image list comes from sets/<name>.txt (made from the game's used_images.txt).
  * Animated sheets (e.g. celica_squat_rub-530-530-6.png = 6 frames side by side) are done frame by frame.
  * Context-aware: each layer frame is upscaled lying on the body/head layers under it in the game (never on
    clothing), then cut out again with its own transparency (edge pixels are un-mixed).  Stops tiny features
    on their own layer (mouth, nipples, slime blobs) from being redrawn as something else.
  * Only the layer's area (+ 24 px of surroundings) is processed, not the empty canvas.
  * ComfyUI always has up to 3 detailer jobs queued; the next frames are prepared while it works.
  * @4 files are made for single pictures only.  Animated sheets get @2 only (an @4 6-frame sheet is
    12720x2120 = ~100 MB of video memory per layer).  --sheet-at4 makes them anyway.
  * Floor shadows (pure black, half transparent) are kept away from the AI and redrawn as a clean smooth shape,
    the same in every frame.  Context layers never include the shadow (boots/feet no longer get shadow painted on).
  * Frame anchoring: wherever a frame's vanilla pixels equal the first frame's, it gets the first frame's HD pixels,
    so the parts that don't move can't flicker.  Frames identical to the first one aren't processed at all.
  * Already-made files are skipped (--force to redo), so a stopped run can simply be started again.

Output
  Mods/hd_sprites_mod/images/...@2.png / @4.png  (the uploadable mod), copied into game/images/... (--no-install skips)
  Upscale/hd_preview/<set>/ : per pose, an animated GIF (vanilla | HD) to check for flicker, plus a still PNG.
  The preview folder opens when done (--no-open skips).
"""
import os, sys, shutil, time, json, uuid, argparse, re, warnings
from collections import deque
warnings.filterwarnings("ignore")
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import torch, spandrel
from compare_upscalers import WS, MODEL_DIR, ALPHA_MODEL, DEV, font, load_image, upscale4, IMG_DIR, bleed
from refine_compare import color_match, comfy, COMFY, COMFY_DIR, CKPT, POS, NEG, STEPS

MOD = os.path.join(WS, "Mods", "hd_sprites_mod")
GAME = os.path.normpath(os.path.join(WS, "..", "game"))
PREVIEW = os.path.join(WS, "Upscale", "hd_preview")
SETS = os.path.join(HERE, "sets")
MODEL = "4x-ReboutBlend.pth"
# ---- recipe "P" (locked 2026-10-17): tile ControlNet holds every shape, the AI repaints with semi-realistic blended
# shading.  Faces stay gentle (no LoRAs, 0.10) so expressions match vanilla; glow overlays get no AI pass at all.
DENOISE = 0.60
CN_TILE = "xinsir_controlnet_tile_sdxl.safetensors"
CN_STRENGTH = 0.80
P_LORAS = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.35),
           ("Niji_semi_realism_v5.safetensors", 0.5)]
BODY_EXTRA_LORAS = [("feet v3.safetensors", 0.5)]      # body layers: realistic feet/toes wherever feet are in the frame
P_STEPS = 14
POS_P = ("masterpiece, best quality, Jeddtl02, detailed skin, smooth blended shading, soft gradients, semi-realistic, "
         "realistic skin, subtle muscle definition, clean lineart, game sprite, simple background")
POS_P_BODY = POS_P + ", Feet, perfect, realistic feet, detailed toes"
NEG_P = ("blurry, soft, jpeg artifacts, noise, grain, sketch, text, bad anatomy, deformed, extra toes, missing toes, "
         "fused toes, extra fingers")
FACE_DENOISE = 0.10          # expression layers (name contains "_face"): tiny features, must stay identical to vanilla
QUEUE = 3                    # detailer jobs kept queued in ComfyUI
MARGIN = 24                  # surroundings kept around a layer (in original pixels)

# ---- layer kinds (by the part of the name after the pose), in drawing order.  Only hairb/body/breasts/neck/head
# are ever used as context (what lies under another layer); clothing, faces, hair fronts and grabs never are.
KINDS = [
    (r"^_head\w*hair_\w*b$", "hairb", 0),
    (r"^$", "body", 1),
    (r"^_breasts", "breasts", 2),
    (r"^_(top|bottom|feet|socks|sleeves|head)_", "clothing", 5),
    (r"^_arms_", "arms", 8),
    (r"^_head\w*neck$", "neck", 9),
    (r"^_head(forward|down|up|tilt)$", "head", 10),
    (r"^_(\w+_)?face_", "face", 11),             # also celica_nelpossessed_face_..., _behind_ghost_face_...
    (r"^_head\w*hair_", "hair", 12),
    (r"^_grab_", "grab", 13),
]


def kind_of(suffix):
    for rx, k, rank in KINDS:
        if re.match(rx, suffix):
            return k, rank
    return "other", 6


def parse(rel):
    base, w, h, n = os.path.basename(rel)[:-4].rsplit("-", 3)
    return base, int(w), int(h), int(n)


def full_sheet(rel):
    load_image(rel)                                               # extracts it from the archive if needed
    return Image.open(os.path.join(IMG_DIR, rel.replace("/", os.sep))).convert("RGBA")


def stack(layers):
    out = Image.new("RGBA", layers[0].size, (0, 0, 0, 0))
    for l in layers:
        out.alpha_composite(l)
    return out


def clean_alpha(im):
    a = np.array(im)
    a[a[..., 3] < 8] = 0
    return Image.fromarray(a, "RGBA")


def shadow_mask(arr):
    """the floor shadow: pure black at ~50% transparency (0,0,0,128) - the only half-transparent pixels in body layers"""
    return (arr[..., 0] == 0) & (arr[..., 1] == 0) & (arr[..., 2] == 0) & (arr[..., 3] >= 115) & (arr[..., 3] <= 140)


def no_shadow(im):
    a = np.array(im)
    a[shadow_mask(a)] = 0
    return Image.fromarray(a, "RGBA")


def shadow_hd(mask, size, alpha=128):
    """a clean, smooth version of a pixel-art shadow mask at a bigger size (no AI: identical every frame)"""
    m = Image.fromarray((mask * 255).astype(np.uint8), "L").resize(size, Image.BICUBIC)
    v = np.array(m).astype(np.float32) / 255.0
    v = np.clip((v - 0.5) * 3.0 + 0.5, 0, 1)                     # sharpen the soft edge back to a crisp outline
    out = np.zeros((size[1], size[0], 4), np.uint8)
    out[..., 3] = (v * alpha).round().astype(np.uint8)
    return Image.fromarray(out, "RGBA")


_exists = {}


def exists_in_game(rel):
    if rel not in _exists:
        try:
            load_image(rel)
            _exists[rel] = True
        except Exception:
            _exists[rel] = False
    return _exists[rel]


def pose_of(rel, poses=None):
    """the pose a layer belongs to.  Starting from the shortest start of its name that is also a picture with the same
    frame layout, a longer start becomes the pose when the extra part is not a layer kind:
      celica_squat_rub_face_aroused-530-530-6 -> celica_squat_rub      celica_face_climax-530-530-1 -> celica
      celica_hurt_face_normal-530-530-1      -> celica_hurt  ("_hurt" is a pose, not a layer)
      celica_headtilthair_normal-530-530-1   -> celica       ("_headtilt" is a head layer)"""
    base, w, h, n = parse(rel)
    folder = rel.rsplit("/", 1)[0]
    parts = base.split("_")
    pose = None
    for k in range(1, len(parts) + 1):
        p = "_".join(parts[:k])
        if not exists_in_game("%s/%s-%d-%d-%d.png" % (folder, p, w, h, n)):
            continue
        if pose is None:
            pose = p
        elif p != base and kind_of(p[len(pose):])[0] == "other":
            pose = p
        elif p == base and kind_of(p[len(pose):])[0] == "other":
            pose = p
    return pose or base


def context_for(rel, poses):
    """vanilla layers that lie under this layer in the game (same pose, same frame layout)"""
    base, w, h, n = parse(rel)
    folder = rel.rsplit("/", 1)[0]
    pose = pose_of(rel, poses)
    if pose is None:
        return []
    suffix = base[len(pose):]
    kind, rank = kind_of(suffix)
    hv = re.search(r"head(forward|down|up|tilt)", suffix)
    hv = hv.group(1) if hv else "forward"
    want = [("_head%shair_normalb" % hv, 0), ("", 1), ("_breasts", 2), ("_head%sneck" % hv, 9), ("_head%s" % hv, 10)]
    out = []
    for suf, r in want:
        if r >= rank:
            continue
        crel = "%s/%s%s-%d-%d-%d.png" % (folder, pose, suf, w, h, n)
        if crel != rel and exists_in_game(crel):
            out.append(crel)
    return out


# ---------------------------------------------------------------------------------------------------- detailer (async)
def detail_submit(img, denoise, seed=1, ckpt=None, pos=None, neg=None, loras=(), cn=None, steps=None):
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not bb:
        return None
    m = 64
    x0, y0 = max(bb[0] - m, 0) // 8 * 8, max(bb[1] - m, 0) // 8 * 8                 # SDXL needs multiples of 8
    x1, y1 = min(-(-(bb[2] + m) // 8) * 8, img.width // 8 * 8), min(-(-(bb[3] + m) // 8) * 8, img.height // 8 * 8)
    box = (x0, y0, x1, y1)
    if x1 - x0 < 64 or y1 - y0 < 64:
        return None
    crop = np.array(img.crop(box))
    rgb = Image.fromarray(bleed(crop, radius=16, thresh=8).round().clip(0, 255).astype(np.uint8), "RGB")
    W, H = rgb.size
    cols, rows = -(-W // 1536), -(-H // 1536)
    tw, th = -(-(-(-W // cols)) // 8) * 8, -(-(-(-H // rows)) // 8) * 8
    name = "tom_hd_%s.png" % uuid.uuid4().hex[:10]
    rgb.save(os.path.join(COMFY_DIR, "input", name))
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt or CKPT}},
        "4": {"class_type": "LoadImage", "inputs": {"image": name}},
        "5": {"class_type": "UltimateSDUpscaleNoUpscale", "inputs": {
            "upscaled_image": ["4", 0], "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "vae": ["1", 2],
            "seed": seed, "steps": steps or STEPS, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            "mode_type": "Linear", "tile_width": tw, "tile_height": th, "mask_blur": 16, "tile_padding": 64,
            "seam_fix_mode": "None", "seam_fix_denoise": 0.2, "seam_fix_width": 64, "seam_fix_mask_blur": 8,
            "seam_fix_padding": 16, "force_uniform_tiles": False, "tiled_decode": False, "batch_size": 1}},
        # PreviewImage = ComfyUI's temp folder (cleaned by ComfyUI itself), not output/ - ComfyUI scans output/
        # in the background and keeps files there open, which made deleting them fail
        "6": {"class_type": "PreviewImage", "inputs": {"images": ["5", 0]}},
    }
    model, clip, nid = ["1", 0], ["1", 1], 20
    for lname, st in loras:                                     # LoRA chain
        wf[str(nid)] = {"class_type": "LoraLoader", "inputs": {"model": model, "clip": clip, "lora_name": lname,
                                                               "strength_model": st, "strength_clip": st}}
        model, clip = [str(nid), 0], [str(nid), 1]
        nid += 1
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": pos or POS}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": neg or NEG}}
    wf["5"]["inputs"]["model"] = model
    if cn:                                                       # tile ControlNet: keeps every shape where it is
        wf["7"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": cn[0]}}
        wf["8"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                   "control_net": ["7", 0], "image": ["4", 0], "strength": cn[1], "start_percent": 0.0, "end_percent": 1.0}}
        wf["5"]["inputs"]["positive"], wf["5"]["inputs"]["negative"] = ["8", 0], ["8", 1]
    pid = comfy("/prompt", {"prompt": wf, "client_id": "tom"})["prompt_id"]
    return {"pid": pid, "name": name, "box": box, "img": img}


def recipe_for(rel, a):
    """detailer settings for a layer: faces gentle, glow overlays none, body layers + feet LoRA, the rest recipe P"""
    base = parse(rel)[0]
    if "glow" in base:
        return None
    if "_face" in base:
        return {"denoise": a.face_denoise}
    p = {"denoise": a.denoise, "loras": P_LORAS, "cn": (CN_TILE, CN_STRENGTH), "steps": P_STEPS, "pos": POS_P, "neg": NEG_P}
    if base == pose_of(rel):                                   # the pose's body layer
        p.update(loras=P_LORAS + BODY_EXTRA_LORAS, pos=POS_P_BODY)
    return p


def _read_retry(path, tries=40):
    # read a file ComfyUI just wrote; wait a little if something still has it open
    import io
    for i in range(tries):
        try:
            with open(path, "rb") as f:
                return Image.open(io.BytesIO(f.read())).convert("RGB")
        except (PermissionError, OSError):
            time.sleep(0.25)
    raise RuntimeError("could not read " + path)


def detail_poll(t):
    """None while still running; the detailed RGBA image when done"""
    h = comfy("/history/" + t["pid"])
    if t["pid"] not in h:
        return None
    st = h[t["pid"]].get("status", {})
    img = t["img"]
    try:
        os.remove(os.path.join(COMFY_DIR, "input", t["name"]))
    except Exception:
        pass
    if st.get("status_str") == "error":
        print("   ! detailer error, keeping the upscale without it:", json.dumps(st)[:300], flush=True)
        return img
    o = h[t["pid"]]["outputs"]["6"]["images"][0]
    src = os.path.join(COMFY_DIR, o.get("type", "temp"), o.get("subfolder", ""), o["filename"])
    res = np.array(_read_retry(src))
    try:
        os.remove(src)
    except OSError:
        pass                                               # ComfyUI empties its temp folder itself
    out = img.copy()
    a = np.array(img.crop(t["box"]))[..., 3]
    out.paste(Image.fromarray(np.dstack([res, a]), "RGBA"), t["box"][:2])
    return out


# ---------------------------------------------------------------------------------------------------- sets
def make_set_from_used(used_txt, name, exclude=()):
    """sets/<name>.txt from a used_images.txt recorded in the game (character pictures only)"""
    rels = []
    for line in open(used_txt, encoding="utf8"):
        f = line.split("\t")[0].strip()
        if not f.startswith("images/CHAR/") or not f.endswith(".png"):
            continue
        f = re.sub(r"@\d+(?=\.png$)", "", f)
        if any(x in f for x in exclude) or f in rels:
            continue
        rels.append(f)
    os.makedirs(SETS, exist_ok=True)
    with open(os.path.join(SETS, name + ".txt"), "w", encoding="utf8") as o:
        o.write("\n".join(rels) + "\n")
    return rels


# ---------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="slime_fight", help="sets/<name>.txt")
    ap.add_argument("--denoise", type=float, default=DENOISE)
    ap.add_argument("--face-denoise", type=float, default=FACE_DENOISE)
    ap.add_argument("--sheet-at4", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", help="only files whose name contains one of these")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="only count the frames that would be generated")
    a = ap.parse_args()
    try:
        comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first, then run this again." % COMFY)
    for d in ("input", "output", "temp"):                       # leftovers from an interrupted run
        for fn in os.listdir(os.path.join(COMFY_DIR, d)) if os.path.isdir(os.path.join(COMFY_DIR, d)) else []:
            if fn.startswith("tom_hd_"):
                try:
                    os.remove(os.path.join(COMFY_DIR, d, fn))
                except OSError:
                    pass
    rels = [l.strip() for l in open(os.path.join(SETS, a.set + ".txt"), encoding="utf8") if l.strip()]
    if a.only:
        rels = [r for r in rels if any(o in r for o in a.only)]

    def out_path(rel, s):
        return os.path.join(MOD, rel.replace("/", os.sep))[:-4] + "@%d.png" % s

    def scales(rel):
        return (2, 4) if parse(rel)[3] == 1 or a.sheet_at4 else (2,)

    todo = [r for r in rels if a.force or not all(os.path.exists(out_path(r, s)) for s in scales(r))]
    print("%d images in set '%s', %d to make" % (len(rels), a.set, len(todo)), flush=True)

    poses = None

    model = amodel = None

    def up8(img):
        w, h = img.size
        x4 = upscale4(model, amodel, img)
        return color_match(upscale4(model, amodel, x4.resize((w * 2, h * 2), Image.LANCZOS)), img)

    # one job per non-empty, non-repeated frame
    jobs, files = deque(), {}
    culled, partial = [0], [0]
    for rel in todo:
        base, w, h, n = parse(rel)
        sheet = full_sheet(rel)
        files[rel] = {"left": 0, "canv": {s: Image.new("RGBA", (w * n * s, h * s), (0, 0, 0, 0)) for s in scales(rel)},
                      "sheet": sheet, "ref": None, "frames": [], "dups": {}, "w": w, "h": h}
        ctx = context_for(rel, poses)
        ref_arr, seen = None, {}
        for f in range(n):
            fr = sheet.crop((f * w, 0, f * w + w, h))
            bb = fr.getchannel("A").getbbox()
            if not bb:
                continue
            arr = np.array(fr)
            key = arr.tobytes()
            if key in seen and seen[key] != files[rel]["ref"]:
                files[rel]["dups"][f] = seen[key]          # repeat of an earlier frame (e.g. 1-2-3-2): copied at the end
                culled[0] += 1
                continue
            files[rel]["frames"].append(f)
            if files[rel]["ref"] is None:
                files[rel]["ref"] = f
                ref_arr = arr
                seen[key] = f
            elif key in seen:
                culled[0] += 1
                continue                                   # identical to the reference frame: copied at the end
            else:
                seen[key] = f
            if f != files[rel]["ref"]:
                # only the part that differs from the reference frame is generated; the rest is the reference's HD
                db = Image.fromarray(np.any(arr != ref_arr, axis=2).astype(np.uint8) * 255, "L").getbbox()
                if db:
                    bb = db
                    partial[0] += 1
            box = (max(bb[0] - MARGIN, 0), max(bb[1] - MARGIN, 0), min(bb[2] + MARGIN, w), min(bb[3] + MARGIN, h))
            jobs.append({"rel": rel, "f": f, "box": box, "ctx": ctx, "w": w, "h": h,
                         "recipe": recipe_for(rel, a)})
            files[rel]["left"] += 1
    total = len(jobs)
    print("%d frames to generate - %d repeated frames culled, %d frames only partly generated (the part that moves)"
          % (total, culled[0], partial[0]), flush=True)
    if a.dry_run:
        return

    def anchor_frames(rel):
        """where a frame's vanilla pixels equal the reference frame's, use the reference frame's HD pixels:
        parts that don't move can't flicker.  Frames identical to the reference become exact copies."""
        F = files[rel]
        ref, w, h = F["ref"], F["w"], F["h"]
        if ref is None or len(F["frames"]) < 2:
            return
        sheet = np.array(F["sheet"])
        rv = sheet[:, ref * w:(ref + 1) * w]
        for f in F["frames"]:
            if f == ref:
                continue
            diff = np.any(sheet[:, f * w:(f + 1) * w] != rv, axis=2)
            m = Image.fromarray((diff * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(3))  # +1 px around changes
            for s, canv in F["canv"].items():
                ms = np.array(m.resize((w * s, h * s), Image.BILINEAR)).astype(np.float32)[..., None] / 255.0
                c = np.array(canv)
                cur = c[:, f * w * s:(f + 1) * w * s].astype(np.float32)
                rf = c[:, ref * w * s:(ref + 1) * w * s].astype(np.float32)
                c[:, f * w * s:(f + 1) * w * s] = (cur * ms + rf * (1 - ms)).round().astype(np.uint8)
                F["canv"][s] = Image.fromarray(c, "RGBA")

    def copy_dups(rel):
        F = files[rel]
        w = F["w"]
        for f, src in F["dups"].items():
            for s_, canv in F["canv"].items():
                canv.paste(canv.crop((src * w * s_, 0, (src + 1) * w * s_, canv.height)), (f * w * s_, 0))

    def finish_file(rel):
        anchor_frames(rel)
        copy_dups(rel)
        for s, canv in files[rel]["canv"].items():
            p = out_path(rel, s)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            # compress_level 1: decodes ~2.7x faster in Ren'Py than max compression (18 vs 50 ms per 6360x1060 sheet)
            clean_alpha(canv).save(p, compress_level=1)
            if not a.no_install:
                dst = os.path.join(GAME, os.path.relpath(p, MOD))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(p, dst)
        del files[rel]

    for rel in [r for r in list(files) if files[r]["left"] == 0]:
        finish_file(rel)                                                      # completely empty pictures

    def place(j, crop8):
        x0, y0 = j["f"] * j["w"] + j["box"][0], j["box"][1]
        bw, bh = j["box"][2] - j["box"][0], j["box"][3] - j["box"][1]
        for s, canv in files[j["rel"]]["canv"].items():
            canv.paste(crop8.resize((bw * s, bh * s), Image.LANCZOS), (x0 * s, y0 * s))
        files[j["rel"]]["left"] -= 1
        if files[j["rel"]]["left"] == 0:
            finish_file(j["rel"])

    def prepare(j):
        w, f, box = j["w"], j["f"], j["box"]

        def frame(rel):
            return full_sheet(rel).crop((f * w, 0, f * w + w, j["h"])).crop(box)
        van = frame(j["rel"])
        sm = shadow_mask(np.array(van))
        j["shadow"] = sm if sm.any() else None              # the floor shadow is redrawn cleanly, not by the AI
        van = no_shadow(van)
        if not van.getchannel("A").getbbox():
            j["alone"] = van.resize((van.width * 8, van.height * 8))
            j["big"], j["ticket"] = j["alone"], None
            return
        j["alone"] = up8(van)
        big = j["alone"]
        if j["ctx"]:
            below = stack([no_shadow(frame(c)) for c in j["ctx"]])     # no shadow under boots/feet
            big = up8(stack([below, van]))
            j["below"] = up8(below)
        j["big"] = big
        j["ticket"] = detail_submit(big, **j["recipe"]) if j["recipe"] else None

    def complete(j, detailed):
        if j["ctx"]:
            B = np.array(j["below"]).astype(np.float32)
            Bc = B[..., :3] * (B[..., 3:] / 255.0)
            D = np.array(detailed).astype(np.float32)
            C, A = D[..., :3], D[..., 3:] / 255.0                   # the stacked picture and its combined opacity
            al = np.array(j["alone"])[..., 3:].astype(np.float32) / 255.0
            # un-mix from what is below:  C*A = al*L + (1-al)*below_premultiplied   (works for see-through layers too,
            # e.g. Nel the ghost at 66% opacity - the old formula assumed a solid picture below and brightened her)
            Lr = np.where(al > 0.05, (C * A - (1 - al) * Bc) / np.maximum(al, 0.05), C)
            crop8 = Image.fromarray(np.dstack([np.clip(Lr, 0, 255), al * 255]).round().astype(np.uint8), "RGBA")
        else:
            crop8 = detailed
        if j.get("shadow") is not None:
            sh = shadow_hd(j["shadow"], crop8.size)
            sh.alpha_composite(crop8)
            crop8 = sh
        for k in ("alone", "below", "big", "ticket", "shadow"):
            j.pop(k, None)
        place(j, crop8)

    L = spandrel.ModelLoader()
    model = L.load_from_file(os.path.join(MODEL_DIR, MODEL)).to(DEV).eval()
    amodel = L.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()
    t0, done, inflight = time.time(), 0, []

    def report(j):
        el = time.time() - t0
        print("[%d/%d] %s frame %d   %.0fs elapsed, ~%.0f min left" % (
            done, total, os.path.basename(j["rel"]), j["f"] + 1, el, el / done * (total - done) / 60), flush=True)

    while jobs or inflight:
        while jobs and len(inflight) < QUEUE:
            j = jobs.popleft()
            prepare(j)
            if j["ticket"] is None:
                complete(j, j["big"])
                done += 1
                report(j)
            else:
                inflight.append(j)
        finished = False
        for j in list(inflight):
            res = detail_poll(j["ticket"])
            if res is not None:
                inflight.remove(j)
                complete(j, res)
                done += 1
                finished = True
                report(j)
        if not finished:
            time.sleep(0.25)
    print("all done in %.1f min" % ((time.time() - t0) / 60), flush=True)

    # ---- previews: per pose, its main layers stacked, vanilla (2x, blocky) | HD @2 - animated GIF + still PNG
    outdir = os.path.join(PREVIEW, a.set)
    os.makedirs(outdir, exist_ok=True)
    groups = {}
    for r in rels:
        base, w, h, n = parse(r)
        folder = r.rsplit("/", 1)[0]
        groups.setdefault((folder, pose_of(r), w, h, n), []).append(r)
    for (folder, pose, w, h, n), members in sorted(groups.items()):
        cand = []
        for r in members:
            suffix = parse(r)[0][len(pose):]
            k, rank = kind_of(suffix)
            if "slimesuit" in suffix or "slimepanties" in suffix or "slimegirl" in suffix:
                continue
            if k in ("face", "arms") and not any(x in suffix for x in ("_normal", "_crossed", "_waist", "_down")):
                continue
            cand.append((rank, len(suffix), suffix, r))
        seen, layers = set(), []
        for rank, _, suffix, r in sorted(cand):
            k = kind_of(suffix)[0]
            if k in ("face", "arms", "head", "neck", "hair", "hairb") and k in seen:
                continue
            seen.add(k)
            layers.append(r)
        if not layers or not all(os.path.exists(out_path(r, 2)) for r in layers):
            continue
        van = stack([full_sheet(r) for r in layers])
        hd = stack([Image.open(out_path(r, 2)).convert("RGBA") for r in layers])
        bb = None
        for f in range(n):
            b = van.crop((f * w, 0, f * w + w, h)).getbbox()
            if b:
                bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
        if bb is None:
            continue
        bb = (max(bb[0] - 10, 0), max(bb[1] - 10, 0), min(bb[2] + 10, w), min(bb[3] + 10, h))
        cw, ch = (bb[2] - bb[0]) * 2, (bb[3] - bb[1]) * 2
        frames = []
        for f in range(n):
            can = Image.new("RGBA", (cw * 2 + 30, ch + 40), (34, 24, 42, 255))
            d = ImageDraw.Draw(can)
            d.text((10, 8), "Vanilla", font=font(16), fill=(240, 220, 255))
            d.text((cw + 20, 8), "HD @2", font=font(16), fill=(240, 220, 255))
            vb = (f * w + bb[0], bb[1], f * w + bb[2], bb[3])
            can.alpha_composite(van.crop(vb).resize((cw, ch), Image.NEAREST), (10, 30))
            can.alpha_composite(hd.crop(tuple(v * 2 for v in vb)), (cw + 20, 30))
            frames.append(can.convert("RGB"))
        stem = "%s_%s" % (os.path.basename(folder), pose)
        frames[0].save(os.path.join(outdir, stem + ".png"))
        if n > 1:
            frames[0].save(os.path.join(outdir, stem + ".gif"), save_all=True, append_images=frames[1:], duration=160, loop=0)
    print("previews:", outdir)
    if not a.no_open:
        os.startfile(outdir)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--make-set":
        # hd_batch.py --make-set <used_images.txt> <name> [exclude ...]
        r = make_set_from_used(sys.argv[2], sys.argv[3], tuple(sys.argv[4:]))
        print("sets/%s.txt: %d images" % (sys.argv[3], len(r)))
    else:
        main()
