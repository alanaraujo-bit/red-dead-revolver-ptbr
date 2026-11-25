"""Catalogue every static text block compiled into .pck files (see pcktext.py).
Blocks name a font id; fonts are either the shared UI font (glyph = code - 32, see pcktext.GLYPH) or
subset fonts holding only the glyphs that text uses, whose code table (ascending u16 list padded with
0xCD) sits in the same pck. Each block is decoded with the table that yields the most plausible text.

usage: pcktextscan.py ISO OUT.json  -> {pck: {block_offset: {"font": [id, size], "table": offset|null,
                                              "room": bytes, "lines": [[x, y, text], ...]}}}"""
import sys, os, re, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660, pcktext

INV = {v: k for k, v in pcktext.GLYPH.items()}
SKIP = re.compile(r'(old|backup|temp|bad|copy)', re.I)
GOOD = re.compile(r"[A-Za-z0-9 .,'!?:;()\-$&/%\"]")


def code_tables(d):
    """Ascending u16 code lists (>= 2 entries, 0x20..0x2fff) framed by 0xCD padding."""
    out = {}
    for m in re.finditer(rb'(?:\xcd\xcd)((?:[\x20-\xff][\x00-\x2f]){2,})(?=\xcd)', d):
        codes = list(struct.unpack_from(f'<{len(m.group(1)) // 2}H', m.group(1)))
        if all(a < b for a, b in zip(codes, codes[1:])):
            out[m.start(1)] = codes
    # tables not framed by padding: any 2-aligned ascending run of printable codes starting with a space
    for i in range(0, len(d) - 6, 2):
        if d[i:i + 2] == b'\x20\x00' and i not in out:
            codes = [0x20]
            j = i + 2
            while j + 2 <= len(d):
                c = struct.unpack_from('<H', d, j)[0]
                if not (codes[-1] < c < 0x3000):
                    break
                codes.append(c)
                j += 2
            if len(codes) >= 4:
                out[i] = codes
    return out


COMMON = set('the a an and of to in is it he his was that for with on as at by be this you your from are or not but had have '
             'has her she him they their them we were will one all can more no so up out if about what when who which '
             'there into only some like than then its also just over new been would my me do'.split())


def score(text):
    """Plausible English: share of allowed characters, boosted by common English words."""
    chars = sum(bool(GOOD.match(c)) for c in text) / max(1, len(text))
    words = re.findall(r"[a-z']+", text.lower())
    common = sum(w in COMMON for w in words) / max(1, len(words))
    return chars + common


def decode(lines, table):
    if table is None:
        return [''.join(INV.get(i, '�') for i, _ in g) for _, g, _ in lines]
    return [''.join(chr(table[i]) if i < len(table) else '�' for i, _ in g) for _, g, _ in lines]


def main():
    out, seen = {}, set()
    with open(sys.argv[1], 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('SWAT.DAT', 'FRONT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                if not e[0].endswith('.pck') or e[0] in seen or SKIP.search(e[0]):
                    continue
                seen.add(e[0])
                d = dave.get(buf, e)
                tables = code_tables(d)
                blocks = []
                for m in re.finditer(rb'\x02\x00....\x01\x00', d, re.S):
                    try:
                        size, lines, end = pcktext.parse_block(d, m.start())
                    except Exception:
                        continue
                    if lines and any(g for _, g, _ in lines):
                        blocks.append((m.start(), size, lines, end))
                # one code table per font id: the one whose decoding of all that font's blocks reads best
                by_font = {}
                for s, size, lines, end in blocks:
                    by_font.setdefault(size if isinstance(size, tuple) else (size,), []).append(lines)

                def fits(t, ls):
                    return t is None or all(i < len(tables[t]) for ln in ls for _, g, _ in ln for i, _ in g)
                choice = {}
                for font, ls in by_font.items():
                    cands = [t for t in [None] + list(tables) if fits(t, ls)]
                    choice[font] = max(cands, key=lambda t: score(' '.join(x for ln in ls for x in decode(ln, None if t is None else tables[t]))))
                for s, size, lines, end in blocks:
                    best = choice[size if isinstance(size, tuple) else (size,)]
                    texts = decode(lines, None if best is None else tables[best])
                    out.setdefault(e[0], {})[hex(s)] = {
                        'font': list(size) if isinstance(size, tuple) else size,
                        'table': None if best is None else hex(best), 'room': end + 2 - s,
                        'score': round(score(''.join(texts)), 2),
                        'lines': [[x, y, t] for (y, _, x), t in zip(lines, texts)]}
    json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = sum(len(v) for v in out.values())
    low = sum(1 for v in out.values() for b in v.values() if b['score'] < 0.95)
    print(f'{n} text blocks in {len(out)} pck files ({low} with doubtful decoding)')


if __name__ == '__main__':
    main()
