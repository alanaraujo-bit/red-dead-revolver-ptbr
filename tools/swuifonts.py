"""Which fonts do the UI layouts (.swui*) use, and for which string keys? usage: swuifonts.py ISO"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, iso9660

use = collections.Counter()
keys_by_font = collections.defaultdict(set)
seen = set()
with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    for path in sorted(p for p in idx if p.endswith('.DAT')):
        if path == 'STREAMS.DAT':
            continue
        buf = iso9660.read(f, idx[path])
        try:
            entries = dave.parse(buf)[1]
        except ValueError:
            continue
        for e in entries:
            if '.swui' not in e[0] or e[0] in seen:
                continue
            seen.add(e[0])
            txt = dave.get(buf, e).decode('latin-1', 'replace')
            font = None
            for tag in re.findall(r'<([^<>]*)>', txt):
                parts = tag.split(':')
                if parts[0] == 'FONT':
                    font = parts[1].lower()
                    use[font] += 1
                elif parts[0] in ('TEXTBOX', 'BUTTON', 'TEXT', 'LABEL') and font:
                    keys_by_font[font].add(parts[-1])
print('swui files:', len(seen))
print('FONT usage:', use.most_common())
for fn, ks in keys_by_font.items():
    print(f'{fn}: {len(ks)} keys e.g. {sorted(ks)[:12]}')
