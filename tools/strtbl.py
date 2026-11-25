"""Red Dead Revolver .strtbl string tables (layout inferred from the retail PS2 files).

u32 nlang | u32 lang_offset[nlang] | u32 buckets | u32 nkeys | nkeys * (u32 len, char[len], 0)
lang block (only lang 0 is used; the others point at EOF):
u32 count | count * (u32 hash, u16 flag, u32 fontlen, font, u32 nchars, utf16[nchars] incl. NUL,
f32 scale_x, f32 scale_y, u16 tail)
Rows are in the same order as keys.
"""
import struct


def elf_hash(key):
    """Row hash = classic ELF/PJW hash of the key (verified on all 1181 swat.strtbl keys)."""
    h = 0
    for c in key.encode('latin-1'):
        h = ((h << 4) + c) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


def row_keys(t):
    """List of keys aligned with t['rows'] (rows are stored in hash-bucket order, not key order)."""
    by_hash = {}
    for k in t['keys']:
        by_hash.setdefault(elf_hash(k), k)
    return [by_hash.get(r['hash'], f'#{r["hash"]:08x}') for r in t['rows']]


def _parse_rows(d, p):
    count = struct.unpack_from('<I', d, p)[0]
    p += 4
    rows = []
    for _ in range(count):
        h, flag = struct.unpack_from('<IH', d, p)
        p += 6
        n = struct.unpack_from('<I', d, p)[0]
        p += 4
        font = d[p:p + n].decode('latin-1')
        p += n
        n = struct.unpack_from('<I', d, p)[0]
        p += 4
        text = d[p:p + 2 * n].decode('utf-16-le')
        p += 2 * n
        sx, sy, tail = struct.unpack_from('<ffH', d, p)
        p += 10
        if not text.endswith('\0'):
            raise ValueError('string without NUL')
        rows.append(dict(hash=h, flag=flag, font=font, text=text[:-1], sx=sx, sy=sy, tail=tail))
    return rows, p


def parse(d):
    """Language blocks are stored back to back; unused language slots point at EOF.
    t['rows'] is language 0 (English); t['langs'] holds every block (others are kept verbatim)."""
    nlang = struct.unpack_from('<I', d, 0)[0]
    offs = struct.unpack_from(f'<{nlang}I', d, 4)
    p = 4 + 4 * nlang
    buckets, nkeys = struct.unpack_from('<II', d, p)
    p += 8
    keys = []
    for _ in range(nkeys):
        n = struct.unpack_from('<I', d, p)[0]
        p += 4
        keys.append(d[p:p + n].decode('latin-1'))
        p += n + 1
    if p != offs[0]:
        raise ValueError(f'key block ends at {p}, lang 0 at {offs[0]}')
    blocks = sorted(set(o for o in offs if o < len(d)))
    langs = []
    for o in blocks:
        if o != p:
            raise ValueError('language blocks are not contiguous')
        rows, p = _parse_rows(d, o)
        langs.append(rows)
    if p != len(d) or any(o != len(d) and o not in blocks for o in offs):
        raise ValueError('unexpected layout (trailing data)')
    slot_block = [blocks.index(o) if o in blocks else -1 for o in offs]
    return dict(nlang=nlang, buckets=buckets, keys=keys, rows=langs[0], langs=langs, slots=slot_block)


def build(t):
    head = bytearray()
    for k in t['keys']:
        kb = k.encode('latin-1')
        head += struct.pack('<I', len(kb)) + kb + b'\0'
    pos = 4 + 4 * t['nlang'] + 8 + len(head)
    langs = t.get('langs') or [t['rows']]
    langs = [t['rows']] + langs[1:]
    starts, bodies = [], []
    for rows in langs:
        body = bytearray(struct.pack('<I', len(rows)))
        for r in rows:
            fb = r['font'].encode('latin-1')
            tb = (r['text'] + '\0').encode('utf-16-le')
            body += struct.pack('<IHI', r['hash'], r['flag'], len(fb)) + fb
            body += struct.pack('<I', len(tb) // 2) + tb
            body += struct.pack('<ffH', r['sx'], r['sy'], r['tail'])
        starts.append(pos)
        bodies.append(body)
        pos += len(body)
    slots = t.get('slots') or [0] + [-1] * (t['nlang'] - 1)
    offs = [starts[s] if s >= 0 else pos for s in slots]
    out = struct.pack('<I', t['nlang']) + struct.pack(f'<{t["nlang"]}I', *offs)
    out += struct.pack('<II', t['buckets'], len(t['keys']))
    return bytes(out + head + b''.join(bodies))
