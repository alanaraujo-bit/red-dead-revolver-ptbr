"""Add PT-BR accented glyphs to Red Dead Revolver bitmap fonts.

.fonttex: header(0x2C) | u32 count | count * (u32 code, u8 x, u8 y, u8 w, u8 h, s8 yoff, s8 xadj)
          | u32 pages | u32 page_end_index[pages]      (records sorted by code, pages = contiguous runs)
.tex:     u16 w, u16 h, u16 fmt(0x0E = 8bpp/256 colours, else 4bpp/16) + 4 x u16 | RGBA palette | pixels

Accented glyphs are composed from the font's own base letters plus anti-aliased accent marks,
then every glyph is re-packed (code order) into the same number of 128x128 pages.
usage: fontpatch.py ISO OUTDIR font [font ...]
"""
import sys, os, struct, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660
from PIL import Image, ImageDraw

ACCENTED = {  # char -> (base, accent)
    'á': ('a', 'acute'), 'à': ('a', 'grave'), 'â': ('a', 'circ'), 'ã': ('a', 'tilde'),
    'é': ('e', 'acute'), 'ê': ('e', 'circ'), 'í': ('i', 'acute'), 'ó': ('o', 'acute'),
    'ô': ('o', 'circ'), 'õ': ('o', 'tilde'), 'ú': ('u', 'acute'), 'ç': ('c', 'cedilla'),
    'Á': ('A', 'acute'), 'À': ('A', 'grave'), 'Â': ('A', 'circ'), 'Ã': ('A', 'tilde'),
    'É': ('E', 'acute'), 'Ê': ('E', 'circ'), 'Í': ('I', 'acute'), 'Ó': ('O', 'acute'),
    'Ô': ('O', 'circ'), 'Õ': ('O', 'tilde'), 'Ú': ('U', 'acute'), 'Ç': ('C', 'cedilla'),
}
QUOTES = {'“': '"', '”': '"', '‘': "'", '’': "'"}  # curly quotes copied from the straight ones
# Glyphs that are only the font's empty "missing character" box: shrunk to 1x1 to free atlas space.
BLANK = {'bosshealth': '#+<=>[\\]^{|}~'}
# Last resort: rare symbols no translated text renders in these fonts (checked with fontneeds.json).
BLANK_IF_NEEDED = {'regulatorcondensed': '\\^_`{|}<>~'}
SS = 8  # supersampling for accent marks


# ---------------------------------------------------------------- file formats
def parse_fonttex(d):
    n = struct.unpack_from('<I', d, 0x2C)[0]
    recs = []
    for i in range(n):
        code, x, y, w, h, yo, xa = struct.unpack_from('<IBBBBbb', d, 0x30 + i * 10)
        recs.append(dict(code=code, x=x, y=y, w=w, h=h, yoff=yo, xadj=xa))
    p = 0x30 + n * 10
    pages = struct.unpack_from('<I', d, p)[0]
    ends = list(struct.unpack_from(f'<{pages}I', d, p + 4))
    if p + 4 + 4 * pages != len(d) or ends[-1] != n:
        raise ValueError('unexpected fonttex trailer')
    page_of = []
    start = 0
    for pg, end in enumerate(ends):
        page_of += [pg] * (end - start)
        start = end
    for r, pg in zip(recs, page_of):
        r['page'] = pg
    return d[:0x2C], recs, pages


def build_fonttex(head, recs, page_ends):
    out = bytearray(head) + struct.pack('<I', len(recs))
    for r in recs:
        out += struct.pack('<IBBBBbb', r['code'], r['x'], r['y'], r['w'], r['h'], r['yoff'], r['xadj'])
    out += struct.pack('<I', len(page_ends)) + struct.pack(f'<{len(page_ends)}I', *page_ends)
    return bytes(out)


def decode_tex(d):
    w, h, fmt = struct.unpack_from('<HHH', d, 0)
    ncol = 256 if fmt == 0x0E else 16
    pal = [tuple(d[14 + i * 4:18 + i * 4]) for i in range(ncol)]
    px = d[14 + ncol * 4:]
    idx = list(px[:w * h]) if ncol == 256 else [(px[i >> 1] >> (4 * (i & 1))) & 0x0F for i in range(w * h)]
    return dict(w=w, h=h, fmt=fmt, head=d[:14], pal=pal, idx=idx)


def encode_tex(t, idx):
    if len(t['pal']) == 256:
        px = bytes(idx)
    else:
        px = bytes(idx[i] | (idx[i + 1] << 4) for i in range(0, len(idx), 2))
    return t['head'] + b''.join(bytes(c) for c in t['pal']) + px


# ---------------------------------------------------------------- glyph images (RGBA, PS2 alpha 0..128)
def cut(tex, r):
    img = Image.new('RGBA', (max(1, r['w']), max(1, r['h'])))
    data = []
    for yy in range(r['h']):
        row = (r['y'] + yy) * tex['w']
        for xx in range(r['w']):
            data.append(tex['pal'][tex['idx'][row + r['x'] + xx]])
    if data:
        img.putdata(data)
    return img


def ink_color(img):
    c = collections.Counter(p[:3] for p in img.getdata() if p[3] >= 0x60)
    return c.most_common(1)[0][0] if c else (255, 255, 255)


def stroke_width(img):
    runs = []
    for y in range(img.height):
        row = [img.getpixel((x, y))[3] >= 0x40 for x in range(img.width)]
        n = sum(row)
        if n:
            runs.append(n)
    return sorted(runs)[len(runs) // 2] if runs else 2


def accent_mask(kind, aw, ah, t):
    """Anti-aliased accent drawn at SSx and reduced; t = stroke thickness in output pixels."""
    big = Image.new('L', (aw * SS, ah * SS), 0)
    d = ImageDraw.Draw(big)
    W, H, T = aw * SS, ah * SS, max(SS, int(t * SS))
    if kind in ('acute', 'grave'):
        poly = [(0, H), (T * 1.4, H), (W, 0), (W - T * 1.4, 0)]
        if kind == 'grave':
            poly = [(W - x, y) for x, y in poly]
        d.polygon(poly, fill=255)
    elif kind == 'circ':
        d.line([(T / 2, H - T / 2), (W / 2, T / 2), (W - T / 2, H - T / 2)], fill=255, width=T, joint='curve')
    elif kind == 'tilde':
        amp = (H - T) / 2
        pts = [(T / 2 + (W - T) * i / 32, H / 2 - amp * math.sin(2 * math.pi * i / 32)) for i in range(33)]
        d.line(pts, fill=255, width=T, joint='curve')
    elif kind == 'cedilla':
        d.line([(W * 0.5, 0), (W * 0.5, H * 0.3), (W * 0.85, H * 0.5), (W * 0.65, H - T / 2), (W * 0.05, H - T / 2)],
               fill=255, width=T, joint='curve')
    small = big.resize((aw, ah), Image.BOX)
    # crisp edges: bitmap fonts at this size read better with little anti-aliasing
    return small.point(lambda v: 255 if v >= 150 else (v * 3 // 2 if v >= 50 else 0))


def dotless(img):
    """Remove the dot of an 'i': erase everything above the first empty row below the top ink."""
    a = [[img.getpixel((x, y))[3] for x in range(img.width)] for y in range(img.height)]
    seen_ink = False
    for y in range(img.height):
        has = any(v >= 0x20 for v in a[y])
        if has:
            seen_ink = True
        elif seen_ink:
            out = img.copy()
            for yy in range(y):
                for x in range(img.width):
                    out.putpixel((x, yy), (0, 0, 0, 0))
            return out.crop((0, y, img.width, img.height)), y
    return img, 0


def compose(ch, base_rec, base_img, metrics):
    base, kind = ACCENTED[ch]
    img, cropped = (dotless(base_img) if base == 'i' else (base_img, 0))
    yoff = base_rec['yoff'] + cropped
    color = ink_color(base_img)
    alpha_max = max(p[3] for p in base_img.getdata()) or 0x80
    upper = ch.isupper()
    xh = metrics['cap'] if upper else metrics['xh']
    t = min(5.0, max(1.6, metrics['stroke'] * 0.5))
    bw = img.width
    if kind == 'cedilla':
        cw, chh = max(4, round(bw * 0.5)), max(round(2 * t + 2), round(xh * 0.3))
        m = accent_mask(kind, cw, chh, t)
        W, H = bw, img.height + chh
        out = Image.new('RGBA', (W, H))
        out.alpha_composite(img, (0, 0))
        layer = Image.new('RGBA', (cw, chh), color + (0,))
        layer.putalpha(m.point(lambda v: v * alpha_max // 255))
        out.alpha_composite(layer, ((W - cw) // 2, img.height - 1 if img.height > 1 else 0))
        return out, dict(yoff=yoff, xadj=base_rec['xadj'])
    if kind in ('acute', 'grave'):
        aw = max(round(t * 2.6), round(bw * 0.5))
        ah = max(round(t + 2), round(xh * (0.24 if upper else 0.3)))
    elif kind == 'circ':
        aw = max(round(t * 3.5), round(bw * 0.75))
        ah = max(round(t * 1.8), round(aw * 0.45))
    else:  # tilde needs room to wave: thinner stroke, full letter width, else the wave breaks apart
        t = max(1.2, t * 0.6)
        aw = max(round(t * 5), bw)
        ah = max(round(t * 2 + 1), round(xh * 0.2))
    aw = min(aw, max(bw, 4) + 2)
    gap = 1 if upper else max(1, round(xh * 0.07))
    m = accent_mask(kind, aw, ah, t)
    W, H = max(bw, aw), ah + gap + img.height
    out = Image.new('RGBA', (W, H))
    out.alpha_composite(img, ((W - bw) // 2, ah + gap))
    layer = Image.new('RGBA', (aw, ah), color + (0,))
    layer.putalpha(m.point(lambda v: v * alpha_max // 255))
    out.alpha_composite(layer, ((W - aw) // 2, 0))
    return out, dict(yoff=yoff - ah - gap, xadj=base_rec['xadj'] - (W - bw))


# ---------------------------------------------------------------- packing / quantising
def _shelf(sub, page_w, page_h, pad, page=None):
    """Shelf-pack glyphs (tallest first) into one page; assign positions when page is given."""
    x = y = row_h = 0
    for rec, img in sorted(sub, key=lambda it: -it[1].height):
        w, h = img.size
        if x + w > page_w:
            x, y, row_h = 0, y + row_h + pad, 0
        if y + h > page_h or w > page_w:
            return False
        if page is not None:
            rec.update(page=page, x=x, y=y, w=w, h=h)
        x += w + pad
        row_h = max(row_h, h)
    return True


def pack(items, page_w, page_h, pad):
    """Pages hold contiguous runs of the code-sorted list (the trailer stores run ends);
    inside a page glyph positions are free, so each run is shelf-packed by height."""
    pages, i = 0, 0
    while i < len(items):
        k = 1
        while i + k <= len(items) and _shelf(items[i:i + k], page_w, page_h, pad):
            k += 1
        k -= 1
        if k == 0:
            raise RuntimeError('glyph larger than a page')
        _shelf(items[i:i + k], page_w, page_h, pad, page=pages)
        pages += 1
        i += k
    return pages


def quantizer(pal):
    cache = {}

    def q(p):
        if p[3] == 0:
            p = (0, 0, 0, 0)
        if p not in cache:
            cache[p] = min(range(len(pal)), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], p)) + (0 if (pal[i][3] == 0) == (p[3] == 0) else 10 ** 6))
        return cache[p]
    return q


def patch_font(files, name, wanted, blank_extra=''):
    """wanted: characters to add (those already in the font, or without a base glyph, are skipped)."""
    head, recs, npages = parse_fonttex(files[name + '.fonttex'])
    texs = [decode_tex(files[f'{name}_{i:02d}.tex']) for i in range(npages)]
    pw, ph = texs[0]['w'], texs[0]['h']
    imgs = {r['code']: (r, cut(texs[r['page']], r)) for r in recs}
    for ch in BLANK.get(name, '') + blank_extra:
        if ord(ch) in imgs:
            imgs[ord(ch)] = (imgs[ord(ch)][0], Image.new('RGBA', (1, 1)))
    have = set(imgs)
    get = lambda c: imgs.get(ord(c))
    xh_rec = get('x') or get('o')
    cap_rec = get('H') or get('E')
    metrics = dict(xh=xh_rec[0]['h'], cap=cap_rec[0]['h'], stroke=stroke_width((get('l') or get('I'))[1]))
    added = []
    for ch in wanted:
        if ord(ch) in have:
            continue
        if ch in QUOTES and get(QUOTES[ch]):
            brec, bimg = get(QUOTES[ch])
            imgs[ord(ch)] = (dict(code=ord(ch), yoff=brec['yoff'], xadj=brec['xadj']), bimg.copy())
            added.append(ch)
            continue
        if ch not in ACCENTED or get(ACCENTED[ch][0]) is None:
            continue
        brec, bimg = get(ACCENTED[ch][0])
        img, m = compose(ch, brec, bimg, metrics)
        rec = dict(code=ord(ch), yoff=max(-128, m['yoff']), xadj=max(-128, min(127, m['xadj'])))
        imgs[ord(ch)] = (rec, img)
        added.append(ch)
    order = [imgs[c] for c in sorted(imgs)]
    for pad in (1, 0):
        pages = pack(order, pw, ph, pad)
        if pages <= npages:
            break
    if pages > npages:
        raise RuntimeError(f'{name}: needs {pages} pages, has {npages}')
    # quantise every page with its original palette
    out = {}
    canvases = [Image.new('RGBA', (pw, ph)) for _ in range(npages)]
    for rec, img in order:
        canvases[rec['page']].alpha_composite(img, (rec['x'], rec['y']))
    for i, t in enumerate(texs):
        q = quantizer(t['pal'])
        out[f'{name}_{i:02d}.tex'] = encode_tex(t, [q(p) for p in canvases[i].getdata()])
    ends, cnt = [], 0
    for pg in range(npages):
        cnt += sum(1 for rec, _ in order if rec['page'] == pg)
        ends.append(cnt)
    # header word 5 is the ascent (= -min yoff of the retail font); the engine skips glyphs whose top
    # is above it, so raise it to cover the accented capitals.
    asc = max(struct.unpack_from('<I', head, 0x14)[0], -min(rec['yoff'] for rec, _ in order))
    head = head[:0x14] + struct.pack('<I', asc) + head[0x18:]
    out[name + '.fonttex'] = build_fonttex(head, [rec for rec, _ in order], ends)
    return out, added, pages, npages


def render(files, name, text, scale=3):
    """Preview: draw text with the (patched) font metrics on a dark strip."""
    head, recs, npages = parse_fonttex(files[name + '.fonttex'])
    texs = [decode_tex(files[f'{name}_{i:02d}.tex']) for i in range(npages)]
    by = {r['code']: r for r in recs}
    base = 64
    img = Image.new('RGBA', (1400, 96), (30, 30, 45, 255))
    x = 4
    for ch in text:
        r = by.get(ord(ch))
        if r is None:
            x += 10
            continue
        g = cut(texs[r['page']], r)
        g = g.copy()
        g.putalpha(g.getchannel('A').point(lambda v: min(255, v * 2)))
        img.alpha_composite(g, (x, base + r['yoff']))
        x += r['w'] + r['xadj'] + 2
    return img.resize((img.width * scale // 2, img.height * scale // 2), Image.NEAREST)


def load_from_iso(iso, names):
    files = collections.defaultdict(dict)
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                for n in names:
                    if e[0] == n + '.fonttex' or (e[0].startswith(n + '_') and e[0].endswith('.tex') and e[0][len(n) + 1:-4].isdigit()):
                        files[n].setdefault(e[0], dave.get(buf, e))
    return files


if __name__ == '__main__':
    iso, outdir, names = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(outdir, exist_ok=True)
    prev_dir = os.path.join(os.path.dirname(outdir), 'fonts_preview')
    os.makedirs(prev_dir, exist_ok=True)
    allfiles = load_from_iso(iso, names)
    import json
    needs = json.load(open(os.path.join(os.path.dirname(outdir), 'fontneeds.json'), encoding='utf-8'))
    full = list(ACCENTED) + list(QUOTES)
    sample = 'Ação Ç É Í Ó À Â Ã Ê Ô Õ Ú | ação cão você está à já é útil têm órfão pôr NÃO “Kid”'
    for n in names:
        need = [c for c in needs.get(n, '') if c in ACCENTED or c in QUOTES]
        used = set(needs.get(n, ''))
        rare = ''.join(c for c in BLANK_IF_NEEDED.get(n, '') if c not in used)
        for label, wanted, extra in (('full set', full, ''), ('text needs', need, ''),
                                     ('text needs + rare symbols freed', need, rare),
                                     ('text needs, no curly quotes', [c for c in need if c not in QUOTES], rare)):
            try:
                out, added, pages, npages = patch_font(allfiles[n], n, wanted, extra)
                if extra:
                    print(f'{n}: freed rare glyphs {extra!r}')
                break
            except RuntimeError as ex:
                print(f'{n}: {label} does not fit ({ex})')
        else:
            raise SystemExit(f'{n}: cannot fit the needed glyphs')
        for fn, data in out.items():
            open(os.path.join(outdir, fn), 'wb').write(data)
        merged = dict(allfiles[n], **out)
        render(merged, n, sample).save(os.path.join(prev_dir, f'{n}.png'))
        print(f'{n}: +{len(added)} glyphs ({"".join(added)}), pages {pages}/{npages}')
