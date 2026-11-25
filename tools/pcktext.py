"""Static text compiled inside .pck UI packages (boot legal/autosave screens, journal titles...).

A text block (found by its glyph records) is a stream of u16 pairs:
  0002 ffff ffff 0001   block start
  000b SIZE             font size (400 = the boot screens)
  0004 X                (optional) pen x for the next line; 0 after the first line, an indent otherwise
  0003 Y  0005 N        line: y position, N glyph records follow
  GLYPH ADVANCE ...     glyph index (ASCII: code - 0x20) and pen advance
  0000                  end of block, rest padded with 0xCD up to the original end
"""
import struct, sys, os, json, re

ASCII = {chr(c): c - 0x20 for c in range(0x20, 0x7f)}
# Glyph numbers of the shared UI font beyond ASCII, mapped in game (work/snaps/acc2.png):
# index 96 = euro, 102.. = Latin-1 lowercase from à in order; upper case and ® use their Latin-1 code.
GLYPH = dict(ASCII)
GLYPH.update({c: 102 + i for i, c in enumerate('àáâãäåæçèéêëìíîïðñòóôõö÷øùúûü')})
GLYPH.update({c: ord(c) for c in 'ÀÁÂÃÇÉÊÍÓÔÕÚ®'})
BASE = {'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ç': 'c', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o',
        'õ': 'o', 'ú': 'u', 'ü': 'u', 'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ç': 'C', 'É': 'E', 'Ê': 'E',
        'Í': 'I', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ú': 'U'}


def parse_block(d, start):
    """-> (size, [(y, [(glyph, adv), ...], x or None)], end_offset_of_terminator)"""
    p = start
    assert d[p:p + 2] == b'\x02\x00' and d[p + 6:p + 8] == b'\x01\x00', 'not a text block'   # bytes 2-5: font id?
    p += 8
    size = x = None
    lines = []
    while True:
        tok, val = struct.unpack_from('<HH', d, p)
        if size is None and tok not in (0x03, 0x04, 0x05, 0x00):
            size = (tok, val)   # font/size token: 0x000b 400 on the boot screens, 0x003a 480 on the journal title
            p += 4
        elif tok == 0x03:
            y = val
            t2, n = struct.unpack_from('<HH', d, p + 4)
            assert t2 == 0x05
            p += 8
            glyphs = [struct.unpack_from('<HH', d, p + 4 * i) for i in range(n)]
            p += 4 * n
            lines.append((y, glyphs, x))
            x = None
        elif tok == 0x04:
            x = val
            p += 4
        elif tok == 0x00:
            return size, lines, p
        else:
            raise ValueError(f'unknown token {tok:#x} at {p:#x}')


def build_block(size, lines, font=None):
    out = bytearray(b'\x02\x00\xff\xff\xff\xff\x01\x00') if font is None else bytearray(font)
    out += struct.pack('<HH', *(size if isinstance(size, tuple) else (0x0b, size)))
    for line in lines:
        y, glyphs = line[0], line[1]
        x = line[2] if len(line) > 2 else None
        if x is not None:
            out += struct.pack('<HH', 0x04, x)
        out += struct.pack('<HHHH', 0x03, y, 0x05, len(glyphs))
        for g, a in glyphs:
            out += struct.pack('<HH', g, a)
    out += b'\x00\x00'
    return bytes(out)


def advances(d, blocks, fit):
    """Pen advance per character: exact values used by the shipped text, else the fit from the
    berrylium metrics (same design); accented letters take their base letter's advance."""
    adv, spaces = {}, []
    for s in blocks:
        for _, g, _ in parse_block(d, s)[1]:
            for i, a in g:
                if i == 0:
                    spaces.append(a)
                elif i < 95:
                    adv.setdefault(chr(i + 32), a)
                elif i == 0xAE:
                    adv.setdefault('®', a)
    # justified lines stretch their spaces and line ends shrink them: the most common value is the natural one
    adv[' '] = max(set(spaces), key=spaces.count)
    for c, a in fit.items():
        adv.setdefault(c, a)
    for c, b in BASE.items():
        adv.setdefault(c, adv[b])
    return adv


def width(s, adv):
    return sum(adv[c] for c in s)


def wrap(text, limits, adv):
    """Greedy word wrap into len(limits) lines, line k no wider than limits[k]."""
    lines, cur = [], ''
    for word in text.split(' '):
        cand = word if not cur else cur + ' ' + word
        if width(cand, adv) <= limits[min(len(lines), len(limits) - 1)]:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > len(limits):
        raise ValueError(f'text needs {len(lines)} lines, only {len(limits)}: {text[:50]!r}')
    return lines


def glyphs(s, adv, space=None):
    """space: optional advance for this line's spaces (tighten a line or match a layout gap)."""
    missing = [c for c in s if c not in GLYPH]
    if missing:
        raise ValueError(f'no glyph for {missing} in {s!r}')
    return [(GLYPH[c], space if c == ' ' and space else adv[c]) for c in s]


def measured_advances(d, scan, font):
    """{char: advance} of one font, read from this pck's blocks that use it (UI-numbered fonts only)."""
    out = {}
    if not scan or font is None:
        return out
    for k, info in scan.items():
        if info.get('font') != font or info.get('table') is not None:
            continue
        try:
            _, lines, _ = parse_block(d, int(k, 16))
        except Exception:
            continue
        for (_, g, _), (_, _, t) in zip(lines, info['lines']):
            for (gi, adv), c in zip(g, t):
                if c != ' ':
                    out.setdefault(c, adv)
    return out


def wrap_free(text, limit, adv):
    """Greedy word wrap with no line count limit; explicit line breaks with '\\n'."""
    out = []
    for para in text.split('\n'):
        cur = ''
        for word in para.split(' '):
            cand = word if not cur else cur + ' ' + word
            if cur and width(cand, adv) > limit:
                out.append(cur)
                cur = word
            else:
                cur = cand
        out.append(cur)
    return out


def auto_item(d, start, item, adv_ui, measured, orig_texts):
    """Automatic layout: item {"text": str (wrapped at the widest original line) | "lines": [...],
    "font": [id, size] (switch from a subset font), "widen": factor on the wrap width}.
    Left-aligned blocks keep the margin; centred ones keep each line's centre; a gap of 4+ spaces
    (where the game draws a button icon or a number) stays at the same x."""
    size, orig, _ = parse_block(d, start)
    font = tuple(item['font']) if 'font' in item else size
    fsize = font[1]
    a = {c: round(v * fsize / 400) for c, v in adv_ui.items()}
    if 'font' not in item and measured:
        a.update(measured)
    owidth = [sum(x for _, x in g) for _, g, _ in orig]
    left = all(x in (None, 0) for _, _, x in orig)
    lines = wrap_free(item['text'], max(owidth) * item.get('widen', 1.0), a) if 'text' in item else item['lines']
    ys = [y for y, _, _ in orig]
    step = ys[1] - ys[0] if len(ys) > 1 else round(fsize * 0.95)
    while len(ys) < len(lines):
        ys.append(ys[-1] + step)
    new = []
    for j, line in enumerate(lines):
        g = glyphs(line, a)
        w = sum(x for _, x in g)
        oj = min(j, len(orig) - 1)
        ox = orig[oj][2] or 0
        if left:
            x = (orig[j][2] if j < len(orig) else 0) if j else orig[0][2]
        else:
            x = round(ox + owidth[oj] / 2 - w / 2)
            mo = re.search(' {4,}', orig_texts[oj]) if oj < len(orig_texts) else None
            mn = re.search(' {4,}', line)
            if mo and mn:
                x = round(ox + sum(adv for _, adv in orig[oj][1][:mo.start()]) - width(line[:mn.start()], a))
            x = max(0, x)
        new.append((ys[j], g, x))
    return replace_block(d, start, build_block(font, new, d[start:start + 8]))


ERRORS = []


def translate(d, spec, adv, scan=None):
    """spec: {block_offset_hex: {"lines": [...]} or {"paragraphs": [[first_line, n_lines, text], ...],
    "max": width}} or an "auto" item (see auto_item). Line slots (y positions) are the original ones;
    unused slots are dropped. scan: this pck's entries from pcktextscan.py (decoded originals)."""
    if '_images' in spec:   # {bitmap object offset: PNG path relative to the project root}
        import pckimage
        from PIL import Image
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bms = {b['obj']: b for b in pckimage.bitmaps(d)}
        for k, path in spec['_images'].items():
            if not os.path.exists(os.path.join(root, path)):   # art is not in the repo: keep the original bitmap
                print(f'image missing, kept original: {path}')
                continue
            b = bms[int(k, 16)]
            # redrawn art comes back larger and opaque: fit it and keep the original transparency
            img = Image.open(os.path.join(root, path)).convert('RGB').resize((b['w'], b['h']), Image.LANCZOS)
            img.putalpha(pckimage.decode(d, b).getchannel('A'))
            d = pckimage.encode(d, b, img)
    for k, item in spec.items():
        if k.startswith('_'):
            continue
        start = int(k, 16)
        if item.get('auto'):
            info = (scan or {}).get(k, {})
            otexts = [t for _, _, t in info.get('lines', [])]
            try:
                d = auto_item(d, start, item, adv, measured_advances(d, scan, info.get('font')), otexts)
            except ValueError as ex:   # report every overflow at once, keep the original block
                ERRORS.append(f'{k}: {ex}')
            continue
        size, orig, _ = parse_block(d, start)
        if 'font' in item:   # e.g. the journal title: its own font only holds the English letters
            size = tuple(item['font'])
        scale = item.get('scale', 1)
        a = {c: round(v * scale) for c, v in adv.items()}
        if 'lines' in item:
            texts = item['lines']
        else:
            texts = [''] * len(orig)
            for first, n, text in item['paragraphs']:
                for j, line in enumerate(wrap(text, [item['max']] * n, a)):
                    texts[first + j] = line
        limits = item.get('limits', [item.get('max', 10 ** 9)] * len(texts))
        spaces = item.get('space', [None] * len(texts))
        # keep each slot's y and x; a slot after a dropped one still needs its explicit x (0 = margin)
        new = [(orig[j][0], glyphs(t, a, spaces[j]), orig[j][2] if orig[j][2] is not None or not k2 else 0)
               for k2, (j, t) in enumerate((j, t) for j, t in enumerate(texts) if t)]
        if 'x' in item:   # explicit pen x per line (null keeps the slot's)
            new = [(y, g, item['x'][k] if k < len(item['x']) and item['x'][k] is not None else x)
                   for k, (y, g, x) in enumerate(new)]
        if item.get('align') == 'center':   # x + width/2 is constant in the shipped block
            y0, g0, x0 = orig[0]
            center = (x0 or 0) + sum(a for _, a in g0) / 2
            new = [(y, g, max(0, round(center - sum(a for _, a in g) / 2))) for y, g, _ in new]
        for (_, g, _), lim, t in zip(new, limits, [t for t in texts if t]):
            if sum(a for _, a in g) > lim:
                raise ValueError(f'{t!r} is {sum(a for _, a in g)} wide, limit {lim}')
        d = replace_block(d, start, build_block(size, new, d[start:start + 8]))
    return d


def main():
    """usage: pcktext.py ISO -> work/pck_out/<name>.pck for every file in traducao/_pcktext.json"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dave, iso9660
    from fontpatch import parse_fonttex, load_from_iso
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = json.load(open(os.path.join(root, 'traducao', '_pcktext.json'), encoding='utf-8'))
    # advances for glyphs absent from the shipped text: linear fit on berrylium (w + xadj), see README
    files = load_from_iso(sys.argv[1], ['berrylium'])['berrylium']
    fit = {chr(r['code']): round(13.42 * (r['w'] + r['xadj']) + 39.7) for r in parse_fonttex(files['berrylium.fonttex'])[1]}
    out_dir = os.path.join(root, 'work', 'pck_out')
    os.makedirs(out_dir, exist_ok=True)
    with open(sys.argv[1], 'rb') as f:
        idx = iso9660.index(f)
        buf = iso9660.read(f, idx['SWAT.DAT'])
        get = lambda n: next(dave.get(buf, e) for e in dave.parse(buf)[1] if e[0] == n)
        # pen advances of the shared UI font at size 400, measured on the boot-screen text of logo01.pck
        logo = get('logo01.pck')
        adv = advances(logo, [int(k, 16) for k in spec['logo01.pck'] if not k.startswith('_')], fit)
        scan = json.load(open(os.path.join(root, 'work', 'pck_static.json'), encoding='utf-8'))
        for name, blocks in spec.items():
            if name.startswith('_'):
                continue
            d = get(name)
            ERRORS.clear()
            new = translate(d, blocks, adv, scan.get(name))
            for msg in ERRORS:
                print(f'ERROR {name} {msg}')
            assert len(new) == len(d)
            open(os.path.join(out_dir, name), 'wb').write(new)
            for k in blocks:
                if k.startswith('_'):
                    continue
                for y, g, x in parse_block(new, int(k, 16))[1]:
                    t = ''.join(next((c for c, i in GLYPH.items() if i == gi), '?') for gi, _ in g)
                    print(f'{name} {k} x={x} y={y:5} w={sum(a for _, a in g):6} {t}')


def replace_block(d, start, new_block):
    """Write new_block over the original block, padding with 0xCD up to the original terminator."""
    _, _, end = parse_block(d, start)
    # the block may also take the 0xCD alignment padding after its terminator: the rest of the
    # terminator's word, then whole 0xCDCDCDCD words (a partly-CD word belongs to the next object)
    p = end + 2
    while p % 4 and p < len(d) and d[p] == 0xCD:
        p += 1
    if p % 4 == 0:
        while d[p:p + 4] == b'\xcd' * 4:
            p += 4
    room = p - start
    if len(new_block) > room:
        raise ValueError(f'text block needs {len(new_block)} bytes, only {room} available')
    return d[:start] + new_block + b'\xcd' * (room - len(new_block)) + d[start + room:]


if __name__ == '__main__':
    main()
