"""Validate translations against the source: control symbols, %s, line structure, glyph coverage
per font and pixel width (real font metrics). usage: check.py ISO [--untranslated]"""
import sys, os, json, glob, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMBOLS = '½¼¾º®†‡•‣'
PATCHED_FONTS = os.path.join(ROOT, 'work', 'fonts_out')


def load_fonts(iso):
    """{fontname_lower: {code: width}} from the disc (patched copies in work/fonts_out win)."""
    fonts = {}
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                if e[0].endswith('.fonttex') and e[0][:-8] not in fonts:
                    fonts[e[0][:-8]] = dave.get(buf, e)
    for p in glob.glob(os.path.join(PATCHED_FONTS, '*.fonttex')):
        fonts[os.path.basename(p)[:-8]] = open(p, 'rb').read()
    out = {}
    for name, d in fonts.items():
        n = struct.unpack_from('<I', d, 0x2C)[0]
        if 0x30 + n * 10 > len(d):
            continue
        out[name] = {struct.unpack_from('<I', d, 0x30 + i * 10)[0]: d[0x30 + i * 10 + 6] for i in range(n)}
    return out


def width(text, glyphs):
    space = glyphs.get(ord('i'), 4)
    return max((sum(glyphs.get(ord(c), space) + 1 for c in line) for line in text.split('\n')), default=0)


def main():
    iso = sys.argv[1]
    src = json.load(open(os.path.join(ROOT, 'work', 'source.json'), encoding='utf-8'))
    tr = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'traducao', 'b*.json'))):
        tr.update(json.load(open(p, encoding='utf-8')))
    fonts = load_fonts(iso)
    problems = collections.defaultdict(list)
    missing_glyphs = collections.defaultdict(collections.Counter)
    wide = []
    for it in src:
        en, pt = it['en'], tr.get(it['id'])
        if pt is None:
            problems['untranslated'].append(it['id'])
            continue
        for s in SYMBOLS:
            if en.count(s) != pt.count(s):
                problems['symbol'].append(f"{it['id']} {s}: en={en.count(s)} pt={pt.count(s)}")
        if en.count('%s') != pt.count('%s'):
            problems['%s'].append(it['id'])
        if pt.count('\n') > en.count('\n') + 1:
            problems['more lines'].append(f"{it['id']} en={en.count(chr(10))} pt={pt.count(chr(10))}")
        if re.search(r'\bPress \?|\bpress \?|Push \?|release \?', en) and pt.count('?') < en.count('?'):
            problems['icon ?'].append(it['id'])
        for fn in it['fonts']:
            g = fonts.get(fn.lower())
            if g is None:
                problems['unknown font'].append(f"{it['id']} {fn}")
                continue
            for c in set(pt):
                if c not in '\n ' and ord(c) not in g:
                    missing_glyphs[fn][c] += 1
            we, wp = width(en, g), width(pt, g)
            if we and wp > we * 1.3 and wp - we > 40:
                wide.append((wp / we, it['id'], fn, we, wp))
    for k, v in problems.items():
        if k == 'untranslated' and '--untranslated' not in sys.argv:
            print(f'{k}: {len(v)}')
        else:
            print(f'{k} ({len(v)}): {v[:40]}')
    for fn, cnt in missing_glyphs.items():
        print(f'missing glyphs in {fn}: {"".join(sorted(cnt))}')
    wide.sort(reverse=True)
    print(f'wider than EN by >30% ({len(wide)}):', [(i, fn, we, wp) for r, i, fn, we, wp in wide[:60]])


if __name__ == '__main__':
    main()
