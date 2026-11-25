"""Find which disc files (raw or inside Dave archives, decompressed) contain a phrase,
as ASCII or UTF-16LE. usage: findtext.py ISO "phrase" ["phrase2" ...]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660

iso, needles = sys.argv[1], sys.argv[2:]
ENCS = ('latin-1', 'utf-16-le', 'utf-16-be', 'utf-32-le')
pats = [(n, enc, n.encode(enc)) for n in needles for enc in ENCS]
pats += [(n, 'lower-latin1', n.lower().encode('latin-1')) for n in needles]
pats += [(n, 'upper-latin1', n.upper().encode('latin-1')) for n in needles]


def scan(label, data):
    for n, enc, p in pats:
        i = data.find(p)
        if i >= 0:
            print(f'{label}: {n!r} {enc} @ {i:#x} (x{data.count(p)})')


with open(iso, 'rb') as f:
    idx = iso9660.index(f)
    for path, entry in sorted(idx.items()):
        if path.endswith('.PSS') or (os.environ.get('ONLY') and path != os.environ['ONLY']):
            continue
        buf = iso9660.read(f, entry)
        scan(path, buf)
        try:
            _, entries = dave.parse(buf)
        except ValueError:
            continue
        for e in entries:
            try:
                scan(f'{path}/{e[0]}', dave.get(buf, e))
            except Exception:
                pass
