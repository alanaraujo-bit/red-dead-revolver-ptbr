"""Replace an 8bpp/4bpp .tex with an edited image (e.g. a translated poster), keeping its palette.

The PNG is the texture "as seen in game": channels R/B are swapped in the file and layouts may
flip it (REVERSE_Y), so pass --flip for those. The image is resized to the texture size and
quantised to the ORIGINAL palette, keeping each pixel's original alpha, so palette layout and
alpha stay exactly as the game expects.

usage: texpatch.py ISO texname edited.png OUTDIR [--flip]
       texpatch.py ISO texname --export view.png [--flip]   (dump the in-game view)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660
from PIL import Image
from fontpatch import decode_tex, encode_tex


def find_tex(iso, name):
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                if e[0] == name:
                    return dave.get(buf, e)
    raise SystemExit(f'{name} not found in FRONT.DAT/SWAT.DAT')


def decode_any(d):
    """Paletted .tex by payload size (format codes vary: 0x0E, 0x01, ...; decode_tex keys 8bpp on 0x0E).
    Returns (t, mips): mips = bytes of the smaller mip levels after level 0 (b'' if none)."""
    w, h = struct.unpack_from('<HH', d, 0)
    n, body = w * h, len(d) - 14
    for ncol, size, fmt in ((256, n, b'\x0e\x00'), (16, (n + 1) // 2, b'\x00\x00')):
        top = 14 + ncol * 4 + size
        if ncol * 4 + size <= body < ncol * 4 + 2 * size:
            t = decode_tex(d[:4] + fmt + d[6:top])
            t['head'] = d[:14]   # keep the real format code on encode
            return t, d[top:]
    raise ValueError(f'not a paletted texture ({w}x{h}, {len(d)} bytes)')


def to_view(t, flip):
    """File pixels -> RGB image as displayed (R/B swapped back; alpha dropped, it is kept per pixel on import)."""
    img = Image.new('RGB', (t['w'], t['h']))
    img.putdata([(b, g, r) for r, g, b, a in (t['pal'][i] for i in t['idx'])])
    return img.transpose(Image.FLIP_TOP_BOTTOM) if flip else img


def from_view(t, img, flip):
    """Edited RGB image -> pixel indices: nearest palette colour that keeps the original pixel's alpha.
    Image generators return no alpha, and posters only change ink, so the alpha mask stays as shipped."""
    img = img.convert('RGB').resize((t['w'], t['h']), Image.LANCZOS)
    if flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    pal = t['pal']
    by_alpha = {}
    for i, (r, g, b, a) in enumerate(pal):
        by_alpha.setdefault(a, []).append(i)
    cache = {}

    def q(rgb, a):
        key = (rgb, a)
        if key not in cache:
            cands = by_alpha.get(a) or range(len(pal))
            cache[key] = min(cands, key=lambda i: sum((x - y) ** 2 for x, y in zip(pal[i][:3], rgb)))
        return cache[key]
    # back to file space: swap R/B
    return encode_tex(t, [q((b, g, r), pal[o][3]) for (r, g, b), o in zip(img.getdata(), t['idx'])])


def alpha_view(t, flip):
    """Artwork stored in alpha (one flat colour): alpha as a white-on-black greyscale image."""
    img = Image.new('L', (t['w'], t['h']))
    img.putdata([t['pal'][i][3] for i in t['idx']])
    return img.transpose(Image.FLIP_TOP_BOTTOM) if flip else img


def alpha_import(t, img, flip):
    """White-on-black image -> alpha: each pixel takes the palette entry with the nearest alpha."""
    img = img.convert('L').resize((t['w'], t['h']), Image.LANCZOS)
    if flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    best = [min(range(len(t['pal'])), key=lambda i: abs(t['pal'][i][3] - v)) for v in range(256)]
    return encode_tex(t, [best[v] for v in img.getdata()])


def direct(d):
    """24/32bpp direct-colour .tex (no palette): (w, h, bytes per pixel) or None."""
    w, h = struct.unpack_from('<HH', d, 0)
    for bpp in (3, 4):
        if len(d) == 14 + w * h * bpp:
            return w, h, bpp
    return None


def direct_view(d, flip):
    w, h, bpp = direct(d)
    # direct colour is stored RGB (only palettes are BGR)
    img = Image.frombytes('RGB' if bpp == 3 else 'RGBA', (w, h), d[14:]).convert('RGB')
    return img.transpose(Image.FLIP_TOP_BOTTOM) if flip else img


def direct_import(d, img, flip):
    """Edited RGB -> same layout; 32bpp keeps the original alpha byte of every pixel."""
    w, h, bpp = direct(d)
    img = img.convert('RGB').resize((w, h), Image.LANCZOS)
    if flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    px = img.tobytes()
    if bpp == 4:
        out = bytearray(d[14:])
        out[0::4], out[1::4], out[2::4] = px[0::3], px[1::3], px[2::3]
        px = bytes(out)
    return d[:14] + px


def main():
    iso, name = sys.argv[1], sys.argv[2]
    flip = '--flip' in sys.argv
    raw = find_tex(iso, name)
    if direct(raw):
        if sys.argv[3] == '--export':
            direct_view(raw, flip).save(sys.argv[4])
            return
        out = direct_import(raw, Image.open(sys.argv[3]), flip)
        os.makedirs(sys.argv[4], exist_ok=True)
        open(os.path.join(sys.argv[4], name), 'wb').write(out)
        direct_view(out, flip).save(os.path.join(sys.argv[4], name + '.preview.png'))
        print(f'wrote {name} (direct colour) + preview')
        return
    t, mips = decode_any(raw)
    if '--alpha' in sys.argv:
        if sys.argv[3] == '--export':
            alpha_view(t, flip).save(sys.argv[4])
            return
        out = alpha_import(t, Image.open(sys.argv[3]), flip)
        os.makedirs(sys.argv[4], exist_ok=True)
        open(os.path.join(sys.argv[4], name), 'wb').write(out)
        alpha_view(decode_any(out)[0], flip).save(os.path.join(sys.argv[4], name + '.preview.png'))
        print(f'wrote {name} (alpha artwork) + preview')
        return
    if mips and sys.argv[3] != '--export':
        # shortcut: mip levels are not regenerated yet; add a downscale per level when a sign needs it
        raise SystemExit(f'{name} has mipmaps; import not supported yet')
    if sys.argv[3] == '--export':
        to_view(t, flip).save(sys.argv[4])
        return
    png, outdir = sys.argv[3], sys.argv[4]
    os.makedirs(outdir, exist_ok=True)
    out = from_view(t, Image.open(png), flip)
    open(os.path.join(outdir, name), 'wb').write(out)
    # preview of what will be in game, for review before building
    to_view(decode_any(out)[0], flip).save(os.path.join(outdir, name + '.preview.png'))
    print(f'wrote {name} ({t["w"]}x{t["h"]}) + preview')


if __name__ == '__main__':
    main()
