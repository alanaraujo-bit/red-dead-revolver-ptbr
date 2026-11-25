"""UI layout labels that are not string-table keys (the engine shows them literally).
usage: swuiliterals.py ISO -> prints unique literals with the files using them"""
import sys, os, re, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660

TAGS = ('TEXT', 'TEXTBOX', 'BUTTON', 'LABEL')


def literals(txt, keys):
    out = []
    for m in re.finditer(r'<([^<>]*)>', txt):
        parts = m.group(1).split(':')
        if parts[0] not in TAGS or len(parts) < 2:
            continue
        last = parts[-1]
        if last in keys or not re.search(r'[A-Za-z]{2}', last) or re.fullmatch(r'[A-Za-z]+\d*_?\w*', last) and '_' in last:
            continue
        out.append(last)
    return out


if __name__ == '__main__':
    keys = set()
    swuis = {}
    with open(sys.argv[1], 'rb') as f:
        idx = iso9660.index(f)
        for path in sorted(p for p in idx if p.endswith('.DAT') and p != 'STREAMS.DAT'):
            buf = iso9660.read(f, idx[path])
            try:
                entries = dave.parse(buf)[1]
            except ValueError:
                continue
            for e in entries:
                if e[0].endswith('.strtbl'):
                    try:
                        keys.update(strtbl.parse(dave.get(buf, e))['keys'])
                    except ValueError:
                        pass
                elif '.swui' in e[0]:
                    swuis.setdefault(e[0], dave.get(buf, e).decode('latin-1'))
    found = collections.defaultdict(set)
    for name, txt in swuis.items():
        for lit in literals(txt, keys):
            found[lit].add(name)
    for lit, files in sorted(found.items()):
        print(f'{lit!r:45} {len(files)} {sorted(files)[:3]}')
    print(len(found), 'literals')
