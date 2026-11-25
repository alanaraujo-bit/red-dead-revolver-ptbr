"""Probe how .pck files reference their strings: try base = first u32 and look for base+offset."""
import sys, struct

d = open(sys.argv[1], 'rb').read()
needle = sys.argv[2].encode('latin-1') + b'\0'
off = d.find(needle)
print('size', hex(len(d)), 'string at', hex(off))
heads = struct.unpack_from('<8I', d, 0)
print('header u32:', [hex(x) for x in heads])
for base_name, base in (('u32[0]', heads[0]), ('zero', 0)):
    val = struct.pack('<I', base + off)
    hits = [i for i in range(0, len(d) - 3, 4) if d[i:i + 4] == val]
    print(f'{base_name}: value {base + off:#x} found at {[hex(h) for h in hits[:8]]}')
# generic: any u32 in file whose low bits match the string offset relative to some base
vals = collections = {}
for i in range(0, len(d) - 3, 4):
    v = struct.unpack_from('<I', d, i)[0]
    b = v - off
    if 0 < b < 0x2000000 and b % 16 == 0:
        vals.setdefault(b, []).append(i)
cands = sorted(vals.items(), key=lambda kv: -len(kv[1]))[:5]
print('base candidates (base, refs):', [(hex(b), [hex(x) for x in refs[:3]]) for b, refs in cands])
