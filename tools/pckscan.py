"""Find embedded English UI strings in .pck/.swui files: NUL-terminated latin-1 runs that start
on a 16-byte boundary (pck string slots are 16-aligned and padded with 0xCD).
Reports per-file counts and slot capacity. usage: pckscan.py DIR [--show N]"""
import sys, os, re, collections

RUN = re.compile(rb'[\x20-\x7e\x91-\x94\xa0-\xff]{2,}\x00')


def strings(d, aligned=True):
    out = []
    for m in RUN.finditer(d):
        s, e = m.start(), m.end()  # e is after NUL
        if aligned and s % 16:
            continue
        if s and d[s - 1] not in (0x00, 0xcd):
            continue
        txt = d[s:e - 1].decode('latin-1')
        if not re.search(r'[A-Za-z]{2}', txt):
            continue
        slot = e
        while slot < len(d) and d[slot] == 0xcd:
            slot += 1
        out.append((s, txt, slot - s))
    return out


if __name__ == '__main__':
    root = sys.argv[1]
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 0
    tot = collections.Counter()
    for fn in sorted(os.listdir(root)):
        d = open(os.path.join(root, fn), 'rb').read()
        ss = strings(d, aligned=fn.endswith('.pck'))
        texty = [x for x in ss if ' ' in x[1] or (x[1][:1].isupper() and len(x[1]) > 3)]
        if texty:
            tot['files'] += 1
            tot['strings'] += len(texty)
            print(f'{fn:45} {len(texty):4} strings')
            for s, t, cap in texty[:show]:
                print(f'    @{s:#07x} cap={cap:3} len={len(t):3} {t[:40]!r}')
    print(dict(tot))
