"""Level resource packs (*.rsc, magic RSC0) carry their own copies of the 3D textures (posters,
signs...), so a translated loose .tex must also be written into every .rsc that embeds it.

RSC0: 'RSC0' u32 count | count * (u32 offset, char[4] tag) ; tags PMT0/MIP0/PAL0/TEX0/MOD0/BND0...
Each texture is a run MIP0, PAL0, TEX0 (name at TEX0+160):
  MIP0: 96-byte header (u16 w, u16 h at +44) then level 0 pixels, PSMT8 GS-swizzled
  PAL0: 16-byte header then 256 RGBA entries, CSM1 order (8-15 <-> 16-23 in each 32), alpha 0-128
Loose .tex palettes are BGRA (alpha 0-255 or 0-128) in plain order with linear pixels.
"""
import struct
from fontpatch import decode_tex


def swz_index(i):
    """CSM1 palette order: swap bits 3 and 4 of the index."""
    return (i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)


def psmt8_map(w, h):
    """Linear (y*w+x) -> offset in the PSMT8-swizzled buffer."""
    m = [0] * (w * h)
    for y in range(h):
        for x in range(w):
            block = (y & ~0xf) * w + (x & ~0xf) * 2
            ss = (((y + 2) >> 2) & 1) * 4
            py = (((y & ~3) >> 1) + (y & 1)) & 7
            col = py * w * 2 + ((x + ss) & 7) * 4
            m[y * w + x] = block + col + ((y >> 1) & 1) + ((x >> 2) & 2)
    return m


def psmt4_map(w, h):
    """Linear (y*w+x) -> (byte offset, nibble shift) in the PSMT4-swizzled buffer.
    Verified 1:1 on duel_draw (256x128); the 'h' stride terms are as validated there."""
    m = [None] * (w * h)
    ph, pv = (w + 127) // 128, (h + 127) // 128
    for y in range(h):
        for x in range(w):
            pn = ((y & ~0x7f) // 128) * ph + ((x & ~0x7f) // 128)
            page = (pn // pv) * 32 * h * 2 + (pn % pv) * 64 * 4
            lx, ly = x & 0x7f, y & 0x7f
            block = ((lx & ~0x1f) >> 1) * h + (ly & ~0xf) * 2
            ss = (((ly + 2) >> 2) & 1) * 4
            py = (((ly & ~3) >> 1) + (ly & 1)) & 7
            col = py * h * 2 + ((lx + ss) & 7) * 4
            m[y * w + x] = (page + block + col + ((lx >> 3) & 3), ((y >> 1) & 1) * 4)
    return m


def entries(d):
    n = struct.unpack_from('<I', d, 4)[0]
    return [struct.unpack_from('<I4s', d, 8 + 8 * i) for i in range(n)]


def textures(d):
    """[(name, mip_offset, pal_offset)] for each MIP0, PAL0, TEX0 run."""
    ents = entries(d)
    out = []
    for i in range(2, len(ents)):
        (mo, mt), (po, pt), (to, tt) = ents[i - 2], ents[i - 1], ents[i]
        if (mt, pt, tt) == (b'MIP0', b'PAL0', b'TEX0'):
            out.append((d[to + 160:to + 192].split(b'\0')[0].decode('latin-1'), mo, po))
    return out


def rsc_alpha(a, amax):
    return a if amax <= 128 else (a * 128 + 127) // 255


def patch(d, loose, log=print):
    """loose: {name without .tex: loose .tex bytes}. Returns patched bytes (same size)."""
    if not d.startswith(b'RSC0'):
        return d
    out = bytearray(d)
    loose = {k.lower(): v for k, v in loose.items()}   # pack names keep authoring case (Feroommap)
    for name, mo, po in textures(d):
        name = name.lower()
        if name not in loose:
            continue
        w, h = struct.unpack_from('<HH', d, mo + 44)
        t = loose[name]
        lw, lh = struct.unpack_from('<HH', t, 0)
        bpp4 = _size(d, mo) == w * h // 2
        need = 14 + (64 + w * h // 2 if bpp4 else 1024 + w * h)
        if (lw, lh) != (w, h) or len(t) < need:
            log(f'rsc: {name} is {w}x{h} in the pack but {lw}x{lh} loose: skipped')
            continue
        t = decode_tex(t[:4] + (b'\x00\x00' if bpp4 else b'\x0e\x00') + t[6:need])
        # shortcut: only level 0 is rewritten; textures with mip levels in the pack are skipped
        if struct.unpack_from('<I', d, mo)[0] != 1 or _size(d, mo) not in (w * h, w * h // 2):
            log(f'rsc: {name} has mip levels in the pack: skipped')
            continue
        # The pack may hold its own variant of the artwork (other palette), so keep the pack palette and
        # map every translated pixel to its nearest pack colour. Loose palettes store the channels
        # reversed relative to the pack; CSM1 order applies to 256-colour palettes only.
        ncol = 16 if bpp4 else 256
        ppal = [tuple(d[po + 16 + 4 * (i if bpp4 else swz_index(i)):][:4]) for i in range(ncol)]
        amax = max(c[3] for c in t['pal'])
        target = [(b, g, r, rsc_alpha(a, amax)) for r, g, b, a in t['pal']]
        near = [min(range(ncol), key=lambda k: sum((x - y) ** 2 for x, y in zip(ppal[k], c))) for c in target]
        if bpp4:
            for lin, (pos, sh) in enumerate(psmt4_map(w, h)):
                o = mo + 96 + pos
                out[o] = (out[o] & ~(0xf << sh) & 0xff) | (near[t['idx'][lin]] << sh)
        else:
            m = psmt8_map(w, h)
            for lin, v in enumerate(t['idx']):
                out[mo + 96 + m[lin]] = near[v]
    return bytes(out)


def _size(d, off):
    offs = sorted(o for o, _ in entries(d)) + [len(d)]
    return offs[offs.index(off) + 1] - off - 96 if off in offs else -1


if __name__ == '__main__':
    # self-check: writing the ORIGINAL loose texture back must reproduce the pack byte for byte
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dave, iso9660
    from texpatch import find_tex
    iso, name = sys.argv[1], sys.argv[2]
    loose = {name: find_tex(iso, name + '.tex')}
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for arc in ('FRONT.DAT', 'SWAT.DAT'):
            buf = iso9660.read(f, idx[arc])
            for e in dave.parse(buf)[1]:
                if e[0].endswith('.rsc'):
                    d = dave.get(buf, e)
                    if d.startswith(b'RSC0') and any(n.lower() == name for n, _, _ in textures(d)):
                        print(arc, e[0], 'round trip identical:', patch(d, loose) == d)
