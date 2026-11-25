"""Search u32 values close to (header base + string offset) to find the pointer convention."""
import sys, struct

d = open(sys.argv[1], 'rb').read()
for s in sys.argv[2:]:
    off = d.find(s.encode('latin-1') + b'\0')
    base = struct.unpack_from('<I', d, 0)[0]
    hits = []
    for i in range(0, len(d) - 3, 4):
        v = struct.unpack_from('<I', d, i)[0]
        delta = v - (base + off)
        if -0x40 <= delta <= 0x40:
            hits.append((hex(i), delta))
    print(f'{s!r} @ {off:#x}: refs (file_off, delta) = {hits[:10]}')
