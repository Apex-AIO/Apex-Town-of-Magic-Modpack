"""refine_compare.py - refined versions of two upscalers, compared to vanilla at vanilla size.

Needs: compare_upscalers.py run first (it makes the x8 files), and ComfyUI running (http://127.0.0.1:8000).
Run with ComfyUI's Python:  run_refine.bat

  Default: vanilla vs A.  --realesrgan adds B.  --denoise 0.15 sets the detailer strength.
  The pictures open by themselves when done.

  A) 4x-ReboutBlend x8  ->  colour matched to vanilla  ->  SDXL detailer (Ultimate SD Upscale, no upscale, denoise 0.05)
                        ->  shrunk to vanilla size
  B) RealESRGAN anime 6B x8  ->  shrunk to vanilla size  ->  vibrance -5%

Colour match: the difference between vanilla and the shrunk x8 (= what the model shifted) is lightly blurred,
enlarged and added back onto the x8 picture.  Colours return to vanilla, the model's new edges/shading stay.
Output: Upscale/compare/<sprite>_refined_detail<denoise>.png (+ _zoom.png); intermediate files in files/<sprite>/.
"""
import os, sys, json, time, uuid, shutil, argparse, urllib.request
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageFilter, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_upscalers import WS, OUT, BG, font, load_image, bleed, png_size, kb

COMFY = "http://127.0.0.1:8000"
COMFY_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ComfyUI")
CKPT = "waiIllustriousSDXL_v170.safetensors"
POS = "masterpiece, best quality, clean lineart, sharp edges, smooth cel shading, anime game sprite, simple background"
NEG = "blurry, soft, jpeg artifacts, noise, grain, watercolor, sketch, extra details, text"
DENOISE = 0.28
STEPS = 10                     # the detailer runs every step even at low denoise, so keep this small
VIBRANCE = -0.05
SPRITE = "images/CHAR/celica/celica_armsbehind-730-530-1.png"


def color_match(x8, vanilla):
    w, h = vanilla.size
    W, H = x8.size
    van = bleed(np.array(vanilla)).astype(np.float32)
    small = bleed(np.array(x8.resize((w, h), Image.LANCZOS))).astype(np.float32)
    diff = van - small                                                   # what the model shifted, per vanilla pixel
    t = torch.from_numpy(diff).permute(2, 0, 1)[None]
    g = torch.exp(-torch.arange(-2, 3, dtype=torch.float32) ** 2 / (2 * 0.8 ** 2)); g = g / g.sum()
    k = (g[:, None] * g[None, :]).expand(3, 1, 5, 5)
    t = F.conv2d(F.pad(t, (2, 2, 2, 2), mode="replicate"), k, groups=3)
    corr = F.interpolate(t, size=(H, W), mode="bicubic", align_corners=False)[0].permute(1, 2, 0).numpy()
    a = np.array(x8)
    rgb = np.clip(a[..., :3].astype(np.float32) + corr, 0, 255)
    return Image.fromarray(np.dstack([rgb, a[..., 3]]).round().astype(np.uint8), "RGBA")


def vibrance(img, amount):
    a = np.array(img).astype(np.float32)
    rgb = a[..., :3] / 255.0
    mx, mn = rgb.max(2, keepdims=True), rgb.min(2, keepdims=True)
    sat = mx - mn
    lum = (rgb * [0.299, 0.587, 0.114]).sum(2, keepdims=True)
    k = 1.0 + amount * (1.0 - sat)                                      # vibrance: low-saturation colours change most
    rgb = np.clip(lum + (rgb - lum) * k, 0, 1)
    return Image.fromarray(np.dstack([rgb * 255.0, a[..., 3:]]).round().astype(np.uint8), "RGBA")


def comfy(path, data=None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def detailer(img, denoise, seed=1):
    # SD detailer on the RGB (see-through areas filled with neighbour colours), alpha put back afterwards
    # only the visible part of the sprite is detailed (the rest is empty canvas): ~4 tiles instead of ~30
    full = img
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()   # the alpha model leaves faint noise everywhere
    m = 64
    x0, y0 = max(bb[0] - m, 0) // 8 * 8, max(bb[1] - m, 0) // 8 * 8           # SDXL needs sizes in multiples of 8
    x1, y1 = min(-(-(bb[2] + m) // 8) * 8, img.width // 8 * 8), min(-(-(bb[3] + m) // 8) * 8, img.height // 8 * 8)
    bb = (x0, y0, x1, y1)
    img = img.crop(bb)
    rgba = np.array(img)
    # edge colours spread only 16 px, flat grey beyond (no streaks for the detailer to work on)
    rgb = Image.fromarray(bleed(rgba, radius=16, thresh=8).round().clip(0, 255).astype(np.uint8), "RGB")
    # tiles sized to the crop (no wasted grid): full width up to 1536, rows of equal height up to 1536
    W, H = img.size
    cols = -(-W // 1536); rows = -(-H // 1536)
    tw, th = -(-(-(-W // cols)) // 8) * 8, -(-(-(-H // rows)) // 8) * 8
    name = "tom_detail_%s.png" % uuid.uuid4().hex[:8]
    rgb.save(os.path.join(COMFY_DIR, "input", name))
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": POS}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEG}},
        "4": {"class_type": "LoadImage", "inputs": {"image": name}},
        "5": {"class_type": "UltimateSDUpscaleNoUpscale", "inputs": {
            "upscaled_image": ["4", 0], "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "vae": ["1", 2],
            "seed": seed, "steps": STEPS, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": denoise,
            "mode_type": "Linear", "tile_width": tw, "tile_height": th, "mask_blur": 16, "tile_padding": 64,
            "seam_fix_mode": "None", "seam_fix_denoise": 0.2, "seam_fix_width": 64, "seam_fix_mask_blur": 8,
            "seam_fix_padding": 16, "force_uniform_tiles": False, "tiled_decode": False, "batch_size": 1}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": "tom_detail"}},
    }
    pid = comfy("/prompt", {"prompt": wf, "client_id": "tom"})["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(2)
        h = comfy("/history/" + pid)
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(json.dumps(st)[:2000])
            outs = h[pid]["outputs"]["6"]["images"]
            break
        print("   detailer running... %ds" % (time.time() - t0), flush=True)
    o = outs[0]
    src = os.path.join(COMFY_DIR, "output", o.get("subfolder", ""), o["filename"])
    res = np.array(Image.open(src).convert("RGB"))
    os.remove(src)
    os.remove(os.path.join(COMFY_DIR, "input", name))
    out = full.copy()
    out.paste(Image.fromarray(np.dstack([res, rgba[..., 3]]), "RGBA"), bb[:2])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=SPRITE)
    ap.add_argument("--denoise", type=float, default=DENOISE)
    ap.add_argument("--vibrance", type=float, default=VIBRANCE)
    ap.add_argument("--realesrgan", action="store_true", help="also add RealESRGAN + vibrance as a column")
    ap.add_argument("--no-open", action="store_true", help="don't open the pictures when done")
    a = ap.parse_args()
    try:
        comfy("/system_stats")
    except Exception:
        sys.exit("ComfyUI is not running at %s - start ComfyUI first, then run this again." % COMFY)
    van = load_image(a.image)
    w, h = van.size
    stem = os.path.splitext(os.path.basename(a.image))[0]
    files = os.path.join(OUT, "files", stem)
    def x8(model):
        p = os.path.join(files, model + "_x8.png")
        if not os.path.exists(p):                                   # make the x8 file first
            print("   making %s x8 (first time only)" % model, flush=True)
            sys.argv = [sys.argv[0], "--images", a.image, "--models", model + (".pth")]
            import compare_upscalers
            compare_upscalers.main()
        return Image.open(p).convert("RGBA")

    print("A) ReboutBlend: colour match", flush=True)
    rb = color_match(x8("4x-ReboutBlend"), van)
    rb.save(os.path.join(files, "4x-ReboutBlend_x8_colormatch.png"))
    print("   detailer denoise %.2f" % a.denoise, flush=True)
    rbd = detailer(rb, a.denoise)
    rbd.save(os.path.join(files, "4x-ReboutBlend_x8_colormatch_detail.png"))
    A = rbd.resize((w, h), Image.LANCZOS)
    A.save(os.path.join(files, "A_rebout_colormatch_detail%.2f_1x.png" % a.denoise))
    cols = [("Vanilla", van), ("ReboutBlend x8 + colour match + detailer %.2f" % a.denoise, A)]
    if a.realesrgan:
        print("B) RealESRGAN: shrink + vibrance %+d%%" % int(a.vibrance * 100), flush=True)
        B = vibrance(x8("RealESRGAN_x4plus_anime_6B").resize((w, h), Image.LANCZOS), a.vibrance)
        B.save(os.path.join(files, "B_realesrgan_vibrance_1x.png"))
        cols.append(("RealESRGAN anime x8 + vibrance %+d%%" % int(a.vibrance * 100), B))
    pad, cap = 14, 46
    can = Image.new("RGBA", (pad + len(cols) * (w + pad), 54 + cap + h + pad), BG + (255,))
    d = ImageDraw.Draw(can)
    d.text((pad, 10), stem + "  -  all shown at vanilla size %dx%d" % (w, h), font=font(22), fill=(30, 30, 30))
    for i, (n, im) in enumerate(cols):
        x = pad + i * (w + pad)
        d.text((x, 54), n, font=font(16), fill=(30, 30, 30))
        d.text((x, 74), "%dx%d  %s" % (w, h, kb(png_size(im))), font=font(14), fill=(40, 90, 170))
        can.alpha_composite(im, (x, 54 + cap))
    out = os.path.join(OUT, "%s_refined_detail%.2f.png" % (stem, a.denoise))
    can.convert("RGB").save(out)

    z, cw, ch = 3, 200, 180
    bb = van.getchannel("A").getbbox()
    cx, cy = (bb[0] + bb[2]) // 2, bb[1] + (bb[3] - bb[1]) // 3
    box = (cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2)
    can = Image.new("RGBA", (pad + len(cols) * (cw * z + pad), 40 + ch * z + pad), BG + (255,))
    d = ImageDraw.Draw(can)
    for i, (n, im) in enumerate(cols):
        x = pad + i * (cw * z + pad)
        d.text((x, 10), n + "  (3x close-up)", font=font(16), fill=(30, 30, 30))
        can.alpha_composite(im.crop(box).resize((cw * z, ch * z), Image.NEAREST), (x, 40))
    can.convert("RGB").save(out[:-4] + "_zoom.png")
    print("wrote", out, "+ _zoom.png")
    if not a.no_open:
        os.startfile(out)
        os.startfile(out[:-4] + "_zoom.png")


if __name__ == "__main__":
    main()
