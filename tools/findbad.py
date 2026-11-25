"""Report string tables whose layout the parser rejects (name, archive, header words)."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660

seen = set()
with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    for path in sorted(p for p in idx if p.endswith('.DAT')):
        buf = iso9660.read(f, idx[path])
        try:
            _, entries = dave.parse(buf)
        except ValueError:
            continue
        for e in entries:
            if not e[0].endswith('.strtbl'):
                continue
            d = dave.get(buf, e)
            try:
                strtbl.parse(d)
            except Exception as ex:
                key = (e[0], len(d))
                if key in seen:
                    continue
                seen.add(key)
                words = struct.unpack_from('<12I', d, 0)
                print(f'{path} {e[0]} size={len(d)} err={ex} head={words}')
