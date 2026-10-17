"""rpa_extract.py - list / extract Ren'Py RPA-3.0 archives.
usage: python rpa_extract.py ARCHIVE [OUTDIR] [--list] [--filter SUBSTR] [--ext .rpy,.rpyc]
"""
import sys, os, zlib, pickle, argparse

def read_index(path):
    with open(path, "rb") as f:
        hdr = f.readline().decode().split()
        assert hdr[0] == "RPA-3.0", hdr
        off, key = int(hdr[1], 16), int(hdr[2], 16)
        f.seek(off)
        idx = pickle.loads(zlib.decompress(f.read()), encoding="bytes")
    out = {}
    for k, v in idx.items():
        k = k.decode("utf8") if isinstance(k, bytes) else k
        parts = []
        for t in v:
            o, l = t[0] ^ key, t[1] ^ key
            pre = t[2] if len(t) > 2 else b""
            if isinstance(pre, str):
                pre = pre.encode("latin1")
            parts.append((o, l, pre))
        out[k] = parts
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive"); ap.add_argument("outdir", nargs="?")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--filter", default="")
    ap.add_argument("--ext", default="")
    a = ap.parse_args()
    idx = read_index(a.archive)
    exts = tuple(e for e in a.ext.split(",") if e)
    names = sorted(n for n in idx if a.filter in n and (not exts or n.endswith(exts)))
    if a.list or not a.outdir:
        for n in names:
            print(n, sum(p[1] for p in idx[n]))
        return
    with open(a.archive, "rb") as f:
        for n in names:
            dst = os.path.join(a.outdir, n)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as o:
                for off, ln, pre in idx[n]:
                    f.seek(off); o.write(pre + f.read(ln - len(pre)))
    print("extracted", len(names), "files to", a.outdir)

if __name__ == "__main__":
    main()
