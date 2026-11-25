"""Self-checks for the toolchain against the original ISO (read-only)."""
import sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660

ISO = sys.argv[1]
with open(ISO, 'rb') as f:
    idx = iso9660.index(f)
    print('iso files:', len(idx))
    front = iso9660.read(f, idx['FRONT.DAT'])
    lvl = iso9660.read(f, idx['LVLS_SNG\\BARFIGHT.DAT'])

with open(ISO, 'rb') as f:
    swat = iso9660.read(f, idx['SWAT.DAT'])
for e in dave.parse(swat)[1]:   # multi-language tables must round-trip too
    if e[0] in ('lvl_frontend.strtbl', 'lvl_front_crap.strtbl'):
        d = dave.get(swat, e)
        assert strtbl.build(strtbl.parse(d)) == d, e[0]
        print(e[0], 'multi-language round-trip ok')

for label, buf in (('FRONT', front), ('BARFIGHT', lvl)):
    hdr, entries = dave.parse(buf)
    # 1) every strtbl round-trips byte-exact
    for e in entries:
        if e[0].endswith('.strtbl'):
            d = dave.get(buf, e)
            assert strtbl.build(strtbl.parse(d)) == d, e[0]
    # 2) rebuild without changes keeps every file identical
    rb = dave.rebuild(buf, {})
    _, entries2 = dave.parse(rb)
    assert [e[0] for e in entries] == [e[0] for e in entries2]
    for a, b in zip(entries, entries2):
        assert dave.get(buf, a) == dave.get(rb, b), a[0]
    # 3) rebuild with a bigger strtbl still extracts everything identically
    e = next(x for x in entries if x[0] == 'swat.strtbl')
    t = strtbl.parse(dave.get(buf, e))
    t['rows'][0]['text'] += ' ação ÇÃO ' * 50
    new = strtbl.build(t)
    rb = dave.rebuild(buf, {'swat.strtbl': new})
    _, entries3 = dave.parse(rb)
    for a, b in zip(entries, entries3):
        expect = new if a[0] == 'swat.strtbl' else dave.get(buf, a)
        assert dave.get(rb, b) == expect, a[0]
    assert len(rb) % 0x800 == 0
    print(f'{label}: ok ({len(entries)} files, size {len(buf)} -> {len(rb)})')
print('ALL OK')
