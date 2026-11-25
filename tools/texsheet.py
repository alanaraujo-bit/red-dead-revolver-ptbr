"""Contact sheets of every .tex in some archives, to spot textures with baked-in English text.
Each cell shows the texture as seen in game (R/B swapped back) with its index; a CSV maps
index -> archive, name, size, format. Textures whose size doesn't match a known format are listed as skipped.

usage: texsheet.py ISO OUTDIR ARCHIVE.DAT [ARCHIVE.DAT ...] [--filter=REGEX] [--alpha-only]
"""
import sys, os, struct, csv, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660
from PIL import Image, ImageDraw
from texpatch import to_view, decode_any

CELL, COLS, ROWS = 256, 6, 4


def known(d):
    return view(d) is not None


def view(d):
    """Decode by payload size (format codes vary: 0x0E/0x01 paletted 8bpp, 0x0B 8bpp grey, 0x11 24bpp...).
    Returns the in-game view (mip level 0) or None."""
    if len(d) < 14:
        return None
    w, h = struct.unpack_from('<HH', d, 0)
    n, body = w * h, len(d) - 14
    if not n:
        return None
    try:
        t = decode_any(d)[0]   # paletted, mip level 0
    except ValueError:
        t = None
    if t:
        # many UI textures are one flat colour with the artwork in alpha: composite over a dark blue
        cols = [t['pal'][i] for i in t['idx']]
        amax = max(c[3] for c in cols) or 1
        scale = 255 / amax if amax <= 128 else 1   # fonts use PS2 alpha 0-128, others 0-255
        bg = (30, 45, 80)
        img = Image.new('RGB', (w, h))
        img.putdata([tuple(int(bg[j] + (c[2 - j] - bg[j]) * min(1, c[3] * scale / 255)) for j in range(3)) for c in cols])
        view.alpha_art = len({c[:3] for c in cols}) <= 4 and len({c[3] for c in cols}) > 2
        return img
    view.alpha_art = False
    if body in (n, 3 * n, 4 * n):
        mode = {n: 'L', 3 * n: 'RGB', 4 * n: 'RGBA'}[body]
        return Image.frombytes(mode, (w, h), d[14:]).convert('RGB')   # direct colour is RGB
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    alpha_only = '--alpha-only' in sys.argv
    flt = next((re.compile(a[9:], re.I) for a in sys.argv[1:] if a.startswith('--filter=')), None)
    iso, outdir, archives = args[0], args[1], args[2:]
    os.makedirs(outdir, exist_ok=True)
    items, skipped, seen = [], [], set()
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in archives:
            buf = iso9660.read(f, idx[arc.upper()])
            for e in dave.parse(buf)[1]:
                if not e[0].endswith('.tex') or e[0] in seen or (flt and not flt.search(e[0])):
                    continue
                seen.add(e[0])
                d = dave.get(buf, e)
                if not known(d):
                    skipped.append((arc, e[0], len(d)))
                    continue
                w_, h_, fmt = struct.unpack_from('<HHH', d, 0)
                img = view(d)
                if alpha_only and not view.alpha_art:
                    continue
                items.append((arc, e[0], w_, h_, hex(fmt), img))
    with open(os.path.join(outdir, 'index.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['n', 'archive', 'name', 'w', 'h', 'fmt'])
        for n, it in enumerate(items):
            w.writerow([n, *it[:5]])
    per = COLS * ROWS
    for s in range(0, len(items), per):
        sheet = Image.new('RGB', (COLS * CELL, ROWS * (CELL + 20)), (40, 40, 40))
        dr = ImageDraw.Draw(sheet)
        for k, it in enumerate(items[s:s + per]):
            img = it[5].copy()
            img.thumbnail((CELL, CELL), Image.LANCZOS)
            x, y = (k % COLS) * CELL, (k // COLS) * (CELL + 20)
            sheet.paste(img, (x, y + 20))
            dr.text((x + 3, y + 3), f'#{s + k} {it[1][:30]}', fill=(255, 255, 0))
        sheet.save(os.path.join(outdir, f'sheet_{s // per:03d}.png'))
    print(f'{len(items)} textures in {-(-len(items) // per)} sheets; skipped {len(skipped)}: {skipped[:10]}')


if __name__ == '__main__':
    main()
