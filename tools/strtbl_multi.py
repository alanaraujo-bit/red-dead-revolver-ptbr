"""Inspect multi-language .strtbl (e.g. lvl_frontend): keys and per-language row counts."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660


def parse_lang(d, p):
    count = struct.unpack_from('<I', d, p)[0]
    p += 4
    rows = []
    for _ in range(count):
        h, flag = struct.unpack_from('<IH', d, p); p += 6
        n = struct.unpack_from('<I', d, p)[0]; p += 4
        font = d[p:p + n].decode('latin-1'); p += n
        n = struct.unpack_from('<I', d, p)[0]; p += 4
        text = d[p:p + 2 * n].decode('utf-16-le')[:-1]; p += 2 * n
        sx, sy, tail = struct.unpack_from('<ffH', d, p); p += 10
        rows.append((h, font, text))
    return rows, p


with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    buf = iso9660.read(f, idx['SWAT.DAT'])
for e in dave.parse(buf)[1]:
    if e[0] in sys.argv[2:]:
        d = dave.get(buf, e)
        nlang = struct.unpack_from('<I', d, 0)[0]
        offs = struct.unpack_from(f'<{nlang}I', d, 4)
        p = 4 + 4 * nlang
        buckets, nkeys = struct.unpack_from('<II', d, p); p += 8
        keys = []
        for _ in range(nkeys):
            n = struct.unpack_from('<I', d, p)[0]; p += 4
            keys.append(d[p:p + n].decode('latin-1')); p += n + 1
        print(e[0], 'langs offsets', offs, 'keys', len(keys))
        print('keys:', keys)
        for li, o in enumerate(sorted(set(offs))):
            if o >= len(d):
                continue
            rows, end = parse_lang(d, o)
            print(f'lang@{o}: rows={len(rows)} end={end} fonts={sorted({r[1] for r in rows})} sample_len={[len(r[2]) for r in rows[:5]]}')
