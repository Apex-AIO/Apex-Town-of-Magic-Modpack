"""hd_batch.py - refine every PNG of a folder through a ComfyUI workflow (folder in, folder out).

    python Tools/hd_batch.py <input_dir> [output_dir] [--url URL] [--limit N] [--workflow FILE] [--write-workflow]

  * Checks ComfyUI first (GET /system_stats) and stops with a clear message if it isn't reachable.
  * Per PNG: upload -> load the API workflow (Tools/workflows/hd_refine_api.json) -> POST /prompt -> wait via
    /history -> download via /view -> <output_dir>/<same name>.png.  Existing outputs are skipped.
  * A failing file is logged to Upscale/logs/ and the run goes on.  Only one summary line is printed.

The workflow file is generated from the project's locked sprite recipe the first time (or with --write-workflow) and can
be edited by hand afterwards: x4 ReboutBlend model pass -> SDXL detailer (UltimateSDUpscaleNoUpscale, tile ControlNet,
LoRAs).  This is the ComfyUI-side version of recipe P; the full game pipeline (Tools/upscale/hd_batch.py) additionally
does the x8 two-pass upscale and the sprite-context handling.  Transparent sprites keep their alpha (resized separately).
Output size is 4x the input size.
"""
import os, sys, io, json, time, uuid, argparse, traceback
import numpy as np
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(WS, "Upscale", "hd_refine")
LOG_DIR = os.path.join(WS, "Upscale", "logs")
WORKFLOW = os.path.join(HERE, "workflows", "hd_refine_api.json")
URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8000")
WAIT_S = 600

# ---- the locked sprite recipe (values mirror Tools/upscale/hd_batch.py) -----------------------------------------
CKPT = "waiIllustriousSDXL_v170.safetensors"
UPSCALER = "4x-ReboutBlend.pth"
CN_TILE, CN_STRENGTH = "xinsir_controlnet_tile_sdxl.safetensors", 0.80
LORAS = [("DetailerILv2-000008.safetensors", 0.6), ("Smooth_Booster_v5.safetensors", 0.35), ("Niji_semi_realism_v5.safetensors", 0.5)]
STEPS, DENOISE = 14, 0.60
POS = ("masterpiece, best quality, Jeddtl02, detailed skin, smooth blended shading, soft gradients, semi-realistic, "
       "realistic skin, subtle muscle definition, clean lineart, game sprite, simple background")
NEG = ("blurry, soft, jpeg artifacts, noise, grain, sketch, text, bad anatomy, deformed, extra toes, missing toes, "
       "fused toes, extra fingers")


def build_workflow():
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
        "9": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "10": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["9", 0], "image": ["4", 0]}},
    }
    model, clip, nid = ["1", 0], ["1", 1], 20
    for name, st in LORAS:
        wf[str(nid)] = {"class_type": "LoraLoader", "inputs": {"model": model, "clip": clip, "lora_name": name,
                                                               "strength_model": st, "strength_clip": st}}
        model, clip, nid = [str(nid), 0], [str(nid), 1], nid + 1
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": POS}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": NEG}}
    wf["7"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CN_TILE}}
    wf["8"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": ["2", 0], "negative": ["3", 0], "control_net": ["7", 0], "image": ["10", 0],
        "strength": CN_STRENGTH, "start_percent": 0.0, "end_percent": 1.0}}
    wf["5"] = {"class_type": "UltimateSDUpscaleNoUpscale", "inputs": {
        "upscaled_image": ["10", 0], "model": model, "positive": ["8", 0], "negative": ["8", 1], "vae": ["1", 2],
        "seed": 1, "steps": STEPS, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": DENOISE,
        "mode_type": "Linear", "tile_width": 1024, "tile_height": 1024, "mask_blur": 16, "tile_padding": 64,
        "seam_fix_mode": "None", "seam_fix_denoise": 0.2, "seam_fix_width": 64, "seam_fix_mask_blur": 8,
        "seam_fix_padding": 16, "force_uniform_tiles": False, "tiled_decode": False, "batch_size": 1}}
    wf["6"] = {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": "hd_batch"}}
    return wf


def load_workflow(path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(build_workflow(), open(path, "w", encoding="utf8"), indent=1)
    return json.load(open(path, encoding="utf8"))


def bleed(rgba, iters=16):
    """fill fully transparent pixels with the colour of the nearest visible ones (no black halo after upscaling)"""
    a = rgba[..., 3] > 8
    rgb = rgba[..., :3].astype(np.float32)
    known = a.copy()
    for _ in range(iters):
        if known.all():
            break
        acc = np.zeros_like(rgb); cnt = np.zeros(known.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                k = np.roll(known, (dy, dx), (0, 1)); c = np.roll(rgb, (dy, dx), (0, 1))
                acc += c * k[..., None]; cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known |= grow
    return rgb.round().clip(0, 255).astype(np.uint8)


def prepare(path):
    """-> (RGB image with even size for upload, alpha channel or None)"""
    im = Image.open(path)
    im.load()
    im = im.convert("RGBA")
    w, h = im.width // 2 * 2, im.height // 2 * 2
    im = im.crop((0, 0, w, h))
    arr = np.array(im)
    alpha = Image.fromarray(arr[..., 3], "L") if (arr[..., 3] < 255).any() else None
    rgb = Image.fromarray(bleed(arr) if alpha is not None else arr[..., :3], "RGB")
    return rgb, alpha


def reachable(url):
    try:
        return requests.get(url + "/system_stats", timeout=3).ok
    except Exception:
        return False


def refine(url, wf_template, path, out_path):
    rgb, alpha = prepare(path)
    buf = io.BytesIO(); rgb.save(buf, "PNG"); buf.seek(0)
    up_name = "hdb_%s.png" % uuid.uuid4().hex[:10]
    r = requests.post(url + "/upload/image", files={"image": (up_name, buf, "image/png")}, data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    up_name = r.json()["name"]
    wf = json.loads(json.dumps(wf_template))
    for node in wf.values():
        ct, inp = node["class_type"], node["inputs"]
        if ct == "LoadImage":
            inp["image"] = up_name
        elif ct == "SaveImage":
            inp["filename_prefix"] = "hdb_" + uuid.uuid4().hex[:8]
        elif ct == "UltimateSDUpscaleNoUpscale":                       # tiles of at most ~1.5k px, multiples of 8
            W, H = rgb.width * 4, rgb.height * 4
            cols, rows = -(-W // 1536), -(-H // 1536)
            inp["tile_width"] = -(-(-(-W // cols)) // 8) * 8
            inp["tile_height"] = -(-(-(-H // rows)) // 8) * 8
    pid = requests.post(url + "/prompt", json={"prompt": wf, "client_id": "hd_batch"}, timeout=30)
    if pid.status_code != 200:
        raise RuntimeError("ComfyUI rejected the workflow: %s" % pid.text[:300])
    pid = pid.json()["prompt_id"]
    t0 = time.time()
    while True:
        h = requests.get("%s/history/%s" % (url, pid), timeout=30).json().get(pid)
        if h and h.get("outputs"):
            break
        if h and h.get("status", {}).get("status_str") == "error":
            raise RuntimeError("ComfyUI error: %s" % json.dumps(h["status"].get("messages", ""))[-300:])
        if time.time() - t0 > WAIT_S:
            requests.post(url + "/interrupt", timeout=10)
            raise TimeoutError("no result after %d s" % WAIT_S)
        time.sleep(0.5)
    img = next(i for o in h["outputs"].values() for i in o.get("images", []))
    data = requests.get(url + "/view", params={"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                               "type": img.get("type", "output")}, timeout=60)
    data.raise_for_status()
    out = Image.open(io.BytesIO(data.content)).convert("RGB")
    if alpha is not None:
        out = out.convert("RGBA")
        out.putalpha(alpha.resize(out.size, Image.Resampling.LANCZOS))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, "PNG")


def main():
    ap = argparse.ArgumentParser(description="Refine every PNG of a folder through ComfyUI.")
    ap.add_argument("input_dir", nargs="?")
    ap.add_argument("output_dir", nargs="?", default=DEFAULT_OUT)
    ap.add_argument("--url", default=URL, help="ComfyUI address (default %s or $COMFY_URL)" % URL)
    ap.add_argument("--limit", type=int, default=0, help="only the first N files")
    ap.add_argument("--workflow", default=WORKFLOW)
    ap.add_argument("--write-workflow", action="store_true", help="(re)create the workflow file from the recipe and exit")
    a = ap.parse_args()
    if a.write_workflow:
        os.makedirs(os.path.dirname(a.workflow), exist_ok=True)
        json.dump(build_workflow(), open(a.workflow, "w", encoding="utf8"), indent=1)
        print("workflow written:", a.workflow)
        return 0
    url = a.url.rstrip("/")
    if not reachable(url):
        print("ComfyUI is not reachable at %s - start ComfyUI (or pass --url) and run again." % url)
        return 2
    if not a.input_dir or not os.path.isdir(a.input_dir):
        print("Input folder not found: %s" % a.input_dir)
        return 2
    wf = load_workflow(a.workflow)
    files = sorted(f for f in os.listdir(a.input_dir) if f.lower().endswith(".png"))
    if a.limit:
        files = files[:a.limit]
    done = skipped = failed = 0
    log = None
    t0 = time.time()
    for f in files:
        out_path = os.path.join(a.output_dir, f)
        if os.path.exists(out_path):
            skipped += 1
            continue
        try:
            refine(url, wf, os.path.join(a.input_dir, f), out_path)
            done += 1
        except Exception as e:
            failed += 1
            if log is None:
                os.makedirs(LOG_DIR, exist_ok=True)
                log = os.path.join(LOG_DIR, "hd_batch_%s.log" % time.strftime("%Y%m%d_%H%M%S"))
            with open(log, "a", encoding="utf8") as lf:
                lf.write("%s  %s  %s: %s\n" % (time.strftime("%H:%M:%S"), f, type(e).__name__, str(e)[:400]))
                lf.write(traceback.format_exc(limit=3) + "\n")
    s = time.time() - t0
    print("done %d, skipped %d, failed %d, time %dm %02ds%s" % (done, skipped, failed, s // 60, s % 60,
                                                                  ("  (log: %s)" % log) if log else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
