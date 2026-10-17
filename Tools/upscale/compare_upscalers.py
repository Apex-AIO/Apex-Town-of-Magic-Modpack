"""compare_upscalers.py - "same size" upscaler comparison for game sprites.

Run with ComfyUI's Python (it has torch + CUDA + spandrel):   run_compare.bat
   or:  <ComfyUI>/.venv/Scripts/python.exe compare_upscalers.py [--images a.png ...] [--models a.pth ...]

For each sprite, ONE picture:  Upscale/compare/<sprite>.png
   one row per upscaler:   vanilla  |  upscaled x8, then shrunk back to the vanilla size
   Both halves are the same size, so what you see is the upscale's effect on the picture at the game's size.
   Each half has a title (what it is, and the PNG file size).
   Plus <sprite>_zoom.png: a 3x close-up of the same area in every version, side by side.
The full x8 files are kept in Upscale/compare/files/<sprite>/ for close inspection.

How x8 is made from a 4x model:  x4 = model(image);  x8 = model(x4 shrunk to x2).
Large images are processed in overlapping tiles (any size works on 16 GB of VRAM).
Transparency: see-through pixels first get the colour of the nearest visible pixel (no dark fringes), and the
alpha channel is upscaled separately with 4x-SkyrimAlpha (made for pixel-art alpha).
"""
import os, io, sys, glob, argparse, warnings
warnings.filterwarnings("ignore")
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
import spandrel

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.normpath(os.path.join(HERE, "..", ".."))                      # Claude Workspace
IMG_DIR = os.path.join(WS, "Extracted", "images")
OUT = os.path.join(WS, "Upscale", "compare")
MODEL_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ComfyUI", "models", "upscale_models")
ALPHA_MODEL = "4x-SkyrimAlpha.pth"
MODELS = ["4x-NXbrz.pth", "4x-ReboutBlend.pth", "4x-AnimeSharp.pth", "RealESRGAN_x4plus_anime_6B.pth"]
IMAGES = ["images/CHAR/celica/celica_armsbehind_grab_armsbehindb_demonlust-730-530-1.png",
          "images/CHAR/celica/celica_armsbehind-730-530-1.png"]
BG = (255, 255, 255)
DEV = "cuda" if torch.cuda.is_available() else "cpu"
TILE, PAD = 384, 24


def font(size):
    for f in ("arialbd.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def load_image(rel):
    p = os.path.join(IMG_DIR, rel.replace("/", os.sep))
    if not os.path.exists(p):                                  # pull it out of the game archives
        sys.path.insert(0, os.path.join(WS, "Tools", "scripts"))
        from rpa_extract import read_index
        game = os.path.normpath(os.path.join(WS, "..", "game"))
        for arc in sorted(glob.glob(os.path.join(game, "images*.rpa"))):
            idx = read_index(arc)
            if rel in idx:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(arc, "rb") as f, open(p, "wb") as o:
                    for off, ln, pre in idx[rel]:
                        f.seek(off); o.write(pre + f.read(ln - len(pre)))
                break
    im = Image.open(p).convert("RGBA")
    try:                                                      # first frame of a sprite sheet (name-W-H-frames.png)
        w, h = [int(x) for x in os.path.basename(p)[:-4].split("-")[-3:-1]]
        im = im.crop((0, 0, w, h))
    except ValueError:
        pass
    return im


def bleed(rgba, radius=None, fill=(128, 128, 128), thresh=0):
    # give see-through pixels the colour of the nearest visible pixel (only within `radius` px if given;
    # anything further away gets the flat `fill` colour)
    known = torch.from_numpy(rgba[..., 3] > thresh).to(DEV)
    rgb = torch.from_numpy(rgba[..., :3].astype(np.float32)).to(DEV).permute(2, 0, 1)[None]
    if bool(known.all()) or not bool(known.any()):
        return rgba[..., :3].astype(np.float32)
    k = known[None, None].float()
    rgb = rgb * k
    kern = torch.ones(1, 1, 3, 3, device=DEV)
    for _ in range(radius if radius else max(rgba.shape[:2])):
        if bool((k > 0).all()):
            break
        s = F.conv2d(rgb, kern.repeat(3, 1, 1, 1), padding=1, groups=3)
        c = F.conv2d(k, kern, padding=1)
        new = (k == 0) & (c > 0)
        rgb = torch.where(new, s / c.clamp(min=1), rgb)
        k = torch.where(new, torch.ones_like(k), k)
    rgb = torch.where(k > 0, rgb, torch.tensor(fill, dtype=rgb.dtype, device=DEV).view(1, 3, 1, 1))
    return rgb[0].permute(1, 2, 0).cpu().numpy()


@torch.inference_mode()
def run(model, rgb):
    # rgb float32 HxWx3 0-255 -> x4, tiled with overlap so big sprites fit in VRAM
    s = model.scale
    t = torch.from_numpy(rgb / 255.0).permute(2, 0, 1)[None].float().to(DEV)
    half = model.supports_half and DEV == "cuda"
    if half:
        model.half()
    _, _, H, W = t.shape
    out = torch.zeros(1, 3, H * s, W * s, device=DEV)
    for y in range(0, H, TILE):
        for x in range(0, W, TILE):
            y0, x0 = max(y - PAD, 0), max(x - PAD, 0)
            y1, x1 = min(y + TILE + PAD, H), min(x + TILE + PAD, W)
            tile = t[:, :, y0:y1, x0:x1]
            r = model(tile.half() if half else tile).float()
            ty, tx = (y - y0) * s, (x - x0) * s
            hh, ww = min(TILE, H - y) * s, min(TILE, W - x) * s
            out[:, :, y * s:y * s + hh, x * s:x * s + ww] = r[:, :, ty:ty + hh, tx:tx + ww]
    return (out.clamp(0, 1)[0].permute(1, 2, 0).cpu().numpy() * 255.0)


def upscale4(model, alpha_model, img):
    rgba = np.array(img.convert("RGBA"))
    rgb = run(model, bleed(rgba))
    a = run(alpha_model or model, np.repeat(rgba[..., 3:4].astype(np.float32), 3, 2)).mean(2)
    return Image.fromarray(np.dstack([rgb, a]).round().clip(0, 255).astype(np.uint8), "RGBA")


def png_size(im):
    b = io.BytesIO(); im.save(b, "PNG", optimize=True); return b.tell()


def kb(n):
    return "%.0f KB" % (n / 1024.0) if n >= 10240 else "%.1f KB" % (n / 1024.0)


def sheet(sprite_name, vanilla, rows):
    # rows: [(model_name, small_image, small_bytes, x8_size, x8_bytes)]
    w, h = vanilla.size
    pad, cap, head = 14, 44, 64
    f_title, f_lab, f_sub = font(24), font(17), font(14)
    W = pad + (w + pad) * 2
    H = head + len(rows) * (cap + h + pad)
    can = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(can)
    d.text((pad, 10), sprite_name, font=f_title, fill=(30, 30, 30))
    d.text((pad, 40), "left: vanilla  |  right: upscaled x8, shrunk back to %dx%d (same size as vanilla)" % (w, h), font=f_sub, fill=(90, 90, 90))
    vb = png_size(vanilla)
    y = head
    for name, small, sb, (bw, bh), bb in rows:
        d.rectangle((0, y - 2, W, y - 1), fill=(200, 200, 200))
        d.text((pad, y + 4), "Vanilla", font=f_lab, fill=(30, 30, 30))
        d.text((pad, y + 24), "%dx%d  %s" % (w, h, kb(vb)), font=f_sub, fill=(40, 90, 170))
        x2 = pad * 2 + w
        d.text((x2, y + 4), "%s  (x8 -> %dx%d)" % (name, w, h), font=f_lab, fill=(30, 30, 30))
        d.text((x2, y + 24), "shown: %s   |   full x8: %dx%d  %s" % (kb(sb), bw, bh, kb(bb)), font=f_sub, fill=(40, 90, 170))
        can.alpha_composite(vanilla, (pad, y + cap))
        can.alpha_composite(small, (x2, y + cap))
        y += cap + h + pad
    return can.convert("RGB")


def zoom_strip(sprite_name, vanilla, rows, z=3, cw=200, ch=180):
    # 3x close-up (nearest neighbour, no smoothing added) of the middle of the sprite, all versions side by side
    bb = vanilla.getchannel("A").getbbox() or (0, 0) + vanilla.size
    cx, cy = (bb[0] + bb[2]) // 2, bb[1] + (bb[3] - bb[1]) // 3
    box = (max(cx - cw // 2, 0), max(cy - ch // 2, 0), max(cx - cw // 2, 0) + cw, max(cy - ch // 2, 0) + ch)
    items = [("Vanilla", vanilla)] + [(n, im) for n, im, _, _, _ in rows]
    pad, cap = 10, 30
    can = Image.new("RGBA", (pad + len(items) * (cw * z + pad), cap + ch * z + pad), BG + (255,))
    d = ImageDraw.Draw(can)
    for i, (n, im) in enumerate(items):
        x = pad + i * (cw * z + pad)
        d.text((x, 6), n + "  (3x close-up)", font=font(17), fill=(30, 30, 30))
        can.alpha_composite(im.crop(box).resize((cw * z, ch * z), Image.NEAREST), (x, cap))
    return can.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="*", default=IMAGES, help="paths inside the game archives (images/...)")
    ap.add_argument("--models", nargs="*", default=MODELS, help="file names in ComfyUI/models/upscale_models")
    a = ap.parse_args()
    loader = spandrel.ModelLoader()
    alpha_model = None
    if os.path.exists(os.path.join(MODEL_DIR, ALPHA_MODEL)):
        alpha_model = loader.load_from_file(os.path.join(MODEL_DIR, ALPHA_MODEL)).to(DEV).eval()
    sprites = [(os.path.basename(r), load_image(r)) for r in a.images]
    results = {n: [] for n, _ in sprites}
    for mname in a.models:
        print("==", mname, flush=True)
        model = loader.load_from_file(os.path.join(MODEL_DIR, mname)).to(DEV).eval()
        stem = os.path.splitext(mname)[0]
        for sname, img in sprites:
            w, h = img.size
            x4 = upscale4(model, alpha_model, img)
            x8 = upscale4(model, alpha_model, x4.resize((w * 2, h * 2), Image.LANCZOS))
            small = x8.resize((w, h), Image.LANCZOS)
            files = os.path.join(OUT, "files", os.path.splitext(sname)[0])
            os.makedirs(files, exist_ok=True)
            x8.save(os.path.join(files, stem + "_x8.png"), optimize=True)
            small.save(os.path.join(files, stem + "_x8_to_1x.png"), optimize=True)
            results[sname].append((stem, small, png_size(small), x8.size, os.path.getsize(os.path.join(files, stem + "_x8.png"))))
            print("   ", sname, flush=True)
        del model
        if DEV == "cuda":
            torch.cuda.empty_cache()
    for sname, img in sprites:
        out = os.path.join(OUT, os.path.splitext(sname)[0] + ".png")
        sheet(sname, img, results[sname]).save(out)
        zoom_strip(sname, img, results[sname]).save(out[:-4] + "_zoom.png")
        print("wrote", out, "+ _zoom.png")


if __name__ == "__main__":
    main()
