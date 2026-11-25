"""Bitmaps inside .pck UI packages (journal pages, titles...). The pck is a memory image whose
pointers are base + offset (base = first u32). A bitmap object is
  [self ptr][descriptor ptr][1][ptr][01000001][cdcdcd01][4]...  followed (at +0x20) by its palette:
  256 RGBA entries, CSM1 order, alpha 0-128 (PSMT8) - or 16 entries for PSMT4.
The descriptor holds UV scales (floats 1/w, 1/h), at +0x18 the pixel pointer, and at +0x38/+0x3C a
GS-style word pair: psm (low byte: 5 = 8bpp, 6 = 4bpp?) and (h << 16 | w). Pixels are GS-swizzled
like the RSC packs (rscpatch.psmt8_map / psmt4_map).

usage: pckimage.py ISO PCKNAME OUTDIR   -> PNG per bitmap (name: <offset>_<w>x<h>.png)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660, rscpatch
from PIL import Image

OBJ_TAIL = struct.pack('<III', 0x01000001, 0xcdcdcd01, 4)


def bitmaps(d):
    """-> [dict(obj, pal, pix, w, h, bpp)]"""
    base = struct.unpack_from('<I', d, 0)[0]
    ptr = lambda v: v - base if base <= v < base + len(d) else None
    out = []
    i = d.find(OBJ_TAIL)
    while i >= 0:
        obj = i - 16
        if obj >= 0 and ptr(struct.unpack_from('<I', d, obj)[0]) == obj:
            desc = ptr(struct.unpack_from('<I', d, obj + 4)[0])
            if desc is not None and desc + 0x40 <= len(d):
                pix = ptr(struct.unpack_from('<I', d, desc + 0x18)[0])
                psm = struct.unpack_from('<I', d, desc + 0x38)[0] & 0xff
                w, h = struct.unpack_from('<HH', d, desc + 0x3c)
                bpp = {5: 8, 6: 4}.get(psm)
                if pix is not None and bpp and 8 <= w <= 1024 and 8 <= h <= 1024:
                    # pixels start 16 bytes past the stored pointer (found empirically: else the image is checkered)
                    out.append(dict(obj=obj, pal=obj + 0x20, pix=pix + 16, w=w, h=h, bpp=bpp))
        i = d.find(OBJ_TAIL, i + 1)
    return out


def decode(d, b):
    w, h = b['w'], b['h']
    ncol = 256 if b['bpp'] == 8 else 16
    pal = [tuple(d[b['pal'] + 4 * k:b['pal'] + 4 * k + 4]) for k in range(ncol)]
    col = lambda v: pal[rscpatch.swz_index(v) if ncol == 256 else v]
    img = Image.new('RGBA', (w, h))
    if b['bpp'] == 8:
        m = rscpatch.psmt8_map(w, h)
        img.putdata([(lambda c: (c[0], c[1], c[2], min(255, c[3] * 2)))(col(d[b['pix'] + m[k]])) for k in range(w * h)])
    else:
        m = rscpatch.psmt4_map(w, h)
        img.putdata([(lambda c: (c[0], c[1], c[2], min(255, c[3] * 2)))(col((d[b['pix'] + pos] >> sh) & 15)) for pos, sh in m])
    return img


def encode(d, b, img):
    """Write img (same size) into bitmap b with a fresh palette of its own -> new bytes (same size)."""
    w, h = b['w'], b['h']
    img = img.convert('RGBA')
    if img.size != (w, h):
        raise ValueError(f"image is {img.size[0]}x{img.size[1]}, bitmap is {w}x{h}")
    ncol = 256 if b['bpp'] == 8 else 16
    q = img.quantize(ncol, method=Image.Quantize.FASTOCTREE)
    pal = q.getpalette('RGBA')[:4 * ncol]
    pal += [0] * (4 * ncol - len(pal))
    out = bytearray(d)
    for i in range(ncol):
        r, g, bl, a = pal[4 * i:4 * i + 4]
        p = b['pal'] + 4 * (rscpatch.swz_index(i) if ncol == 256 else i)
        out[p:p + 4] = bytes((r, g, bl, (a + 1) // 2))   # GS alpha: 0-128
    idx = q.tobytes()   # one palette index per pixel
    if ncol == 256:
        for k, pos in enumerate(rscpatch.psmt8_map(w, h)):
            out[b['pix'] + pos] = idx[k]
    else:
        for k, (pos, sh) in enumerate(rscpatch.psmt4_map(w, h)):
            o = b['pix'] + pos
            out[o] = (out[o] & ~(0xf << sh) & 0xff) | (idx[k] << sh)
    return bytes(out)


def main():
    iso, name, outdir = sys.argv[1:4]
    os.makedirs(outdir, exist_ok=True)
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            d = next((dave.get(buf, e) for e in dave.parse(buf)[1] if e[0] == name), None)
            if d:
                break
    for b in bitmaps(d):
        img = decode(d, b)
        bg = Image.new('RGBA', img.size, (30, 45, 80, 255))
        bg.alpha_composite(img)
        bg.convert('RGB').save(os.path.join(outdir, f"{name[:-4]}_{b['obj']:06x}_{b['w']}x{b['h']}.png"))
        print(hex(b['obj']), b['w'], b['h'], b['bpp'])


if __name__ == '__main__':
    main()
