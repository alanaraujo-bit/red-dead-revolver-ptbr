"""Extract a font (fonttex + its .tex pages) from the ISO, dump glyph records and render pages to PNG.
usage: fontdump.py ISO fontname OUTDIR"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660
from PIL import Image


def tex_to_image(d):
    w, h, fmt = struct.unpack_from('<HHH', d, 0)
    ncol = 256 if fmt == 0x0E else 16
    pal = [tuple(d[14 + i * 4:18 + i * 4]) for i in range(ncol)]
    px = d[14 + ncol * 4:]
    img = Image.new('RGBA', (w, h))
    out = []
    for i in range(w * h):
        if ncol == 256:
            c = px[i]
        else:
            b = px[i >> 1]
            c = (b & 0x0F) if i % 2 == 0 else (b >> 4)
        r, g, b_, a = pal[c]
        out.append((r, g, b_, min(255, a * 2)))
    img.putdata(out)
    return img, fmt, pal


if __name__ == '__main__':
    iso, name, outdir = sys.argv[1:4]
    os.makedirs(outdir, exist_ok=True)
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        files = {}
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                if e[0].startswith(name + '.') or e[0].startswith(name + '_'):
                    files.setdefault(e[0], dave.get(buf, e))
    for fn, d in sorted(files.items()):
        open(os.path.join(outdir, fn), 'wb').write(d)
        if fn.endswith('.tex'):
            img, fmt, pal = tex_to_image(d)
            img.save(os.path.join(outdir, fn + '.png'))
            print(fn, img.size, 'fmt', hex(fmt))
    ft = files[name + '.fonttex']
    print('header words:', [hex(x) for x in struct.unpack_from('<11I', ft, 0)])
    n = struct.unpack_from('<I', ft, 0x2C)[0]
    print('glyphs', n, 'trailer', ft[0x30 + n * 10:].hex(' '))
    for i in range(n):
        rec = ft[0x30 + i * 10:0x30 + i * 10 + 10]
        code = struct.unpack_from('<I', rec, 0)[0]
        if chr(code) in 'AaBbMmXxYyZz|{}~' or i % 15 == 0:
            print(f'{i:3} {chr(code)!r:5} raw={rec.hex(" ")}  x={rec[4]} y={rec[5]} w={rec[6]} h={rec[7]} s16={struct.unpack_from("<h", rec, 8)[0]}')
