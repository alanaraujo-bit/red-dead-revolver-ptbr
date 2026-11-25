"""List glyphs that are just an empty rectangle (the font's 'missing character' box)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontpatch as fp


def is_box(img):
    w, h = img.size
    if w < 4 or h < 4:
        return False
    a = lambda x, y: img.getpixel((x, y))[3] >= 0x30
    border = [a(x, 0) for x in range(w)] + [a(x, h - 1) for x in range(w)] + [a(0, y) for y in range(h)] + [a(w - 1, y) for y in range(h)]
    inner = [a(x, y) for x in range(2, w - 2) for y in range(2, h - 2)]
    return sum(border) >= 0.8 * len(border) and not any(inner)


def box_codes(files, name):
    head, recs, npages = fp.parse_fonttex(files[name + '.fonttex'])
    texs = [fp.decode_tex(files[f'{name}_{i:02d}.tex']) for i in range(npages)]
    return [r['code'] for r in recs if is_box(fp.cut(texs[r['page']], r))]


if __name__ == '__main__':
    files = fp.load_from_iso(sys.argv[1], sys.argv[2:])
    for n in sys.argv[2:]:
        print(n, ''.join(chr(c) for c in box_codes(files[n], n)))
