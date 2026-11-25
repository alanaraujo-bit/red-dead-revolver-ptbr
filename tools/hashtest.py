"""Find the hash function mapping strtbl keys to row hashes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660


def joaat(s, lower=True):
    h = 0
    for c in (s.lower() if lower else s).encode('latin-1'):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    return (h + (h << 15)) & 0xFFFFFFFF


def fnv1(s):
    h = 0x811C9DC5
    for c in s.encode('latin-1'):
        h = (h * 0x01000193) & 0xFFFFFFFF
        h ^= c
    return h


def fnv1a(s):
    h = 0x811C9DC5
    for c in s.encode('latin-1'):
        h ^= c
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def djb2(s):
    h = 5381
    for c in s.encode('latin-1'):
        h = (h * 33 + c) & 0xFFFFFFFF
    return h


def sdbm(s):
    h = 0
    for c in s.encode('latin-1'):
        h = (c + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


def x65599(s):
    h = 0
    for c in s.encode('latin-1'):
        h = (h * 65599 + c) & 0xFFFFFFFF
    return h


def elf(s):
    h = 0
    for c in s.encode('latin-1'):
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    buf = iso9660.read(f, idx['FRONT.DAT'])
e = next(x for x in dave.parse(buf)[1] if x[0] == 'swat.strtbl')
t = strtbl.parse(dave.get(buf, e))
hashes = {r['hash'] for r in t['rows']}
cands = {'joaat_lower': lambda k: joaat(k, True), 'joaat': lambda k: joaat(k, False), 'fnv1': fnv1, 'fnv1a': fnv1a,
         'djb2': djb2, 'sdbm': sdbm, 'x65599': x65599, 'x65599_lower': lambda k: x65599(k.lower()),
         'fnv1a_lower': lambda k: fnv1a(k.lower()), 'djb2_lower': lambda k: djb2(k.lower()),
         'elf': elf, 'elf_lower': lambda k: elf(k.lower()), 'elf_upper': lambda k: elf(k.upper())}
for name, fn in cands.items():
    hit = sum(fn(k) in hashes for k in t['keys'])
    print(f'{name:14} {hit}/{len(t["keys"])}')
print('sample row hashes:', [hex(r['hash']) for r in t['rows'][:4]], 'buckets', t['buckets'])
