"""Catalogue human-readable strings embedded in .pck UI packages (NUL-terminated latin-1 inside
string pools). In-place translation must fit the original byte length.
usage: pckstrings.py ISO OUT.json"""
import sys, os, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660

RUN = re.compile(rb'(?<=[\x00\xcd])[\x20-\x7e]{3,}(?=\x00)')
WORDY = re.compile(r"^[A-Z0-9][A-Za-z0-9 ,.'!?:&\-()\"/]*$")
SKIP_FILES = re.compile(r'(old|backup|temp|bad)', re.I)


def candidates(d):
    for m in RUN.finditer(d):
        s = m.group().decode('latin-1')
        letters = sum(c.isalpha() for c in s)
        if letters < 3 or not WORDY.match(s):
            continue
        if ' ' not in s and not (s[0].isupper() and s[1:].islower() and len(s) >= 4) and not s.isupper():
            continue
        if re.search(r'\.(tex|pck|mod|anim|swui|skel)$', s, re.I) or '_' in s:
            continue
        yield m.start(), s


if __name__ == '__main__':
    iso, out = sys.argv[1], sys.argv[2]
    found = collections.defaultdict(lambda: {'files': set(), 'count': 0})
    seen = set()
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for path in sorted(p for p in idx if p.endswith('.DAT') and p != 'STREAMS.DAT'):
            buf = iso9660.read(f, idx[path])
            try:
                entries = dave.parse(buf)[1]
            except ValueError:
                continue
            for e in entries:
                if not e[0].endswith('.pck') or SKIP_FILES.search(e[0]) or e[0] in seen:
                    continue
                seen.add(e[0])
                for off, s in candidates(dave.get(buf, e)):
                    found[s]['files'].add(e[0])
                    found[s]['count'] += 1
    items = [{'en': s, 'max': len(s), 'files': sorted(v['files'])} for s, v in sorted(found.items())]
    json.dump(items, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for it in items:
        print(f"{it['max']:3} {it['en']!r} {len(it['files'])} {it['files'][:2]}")
    print(len(items), 'strings in', len(seen), 'pck files')
