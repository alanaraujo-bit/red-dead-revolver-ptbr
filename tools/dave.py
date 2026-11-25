"""Angel Studios 'Dave' archives (Red Dead Revolver PS2): read, extract, rebuild.

Layout: header(16) | pad to 0x800 | entries(count*16: name_off, offset, size, zsize) |
names block | file data. 'Dave' = 6-bit packed names, 'DAVE' = plain names.
zsize != size means the stored bytes are deflate-compressed.
"""
import struct, sys, zlib, os

B64 = '\0 #$()-./?0123456789_abcdefghijklmnopqrstuvwxyz~'
SECTOR = 0x800


def _decode_name(names, off, prev):
    """6-bit chars, LSB-first; codes >= 48 copy a prefix of the previous name."""
    bitpos = off * 8

    def bits6():
        nonlocal bitpos
        v = 0
        for k in range(6):
            v |= ((names[bitpos >> 3] >> (bitpos & 7)) & 1) << k
            bitpos += 1
        return v

    out = []
    while True:
        t = bits6()
        if t >= 48:
            n = (t - 0x38) + (bits6() - 0x20) * 8
            out.extend(prev[:n])
            continue
        if t == 0:
            return ''.join(out)
        out.append(B64[t])


def parse(buf):
    """Return (header dict, entries) where entries = [(name, offset, size, zsize), ...] in directory order."""
    magic, count, dir_size, names_size = struct.unpack_from('<4sIII', buf, 0)
    if magic not in (b'Dave', b'DAVE'):
        raise ValueError(f'not a Dave archive ({magic!r})')
    names = buf[SECTOR + dir_size:SECTOR + dir_size + names_size]
    entries, prev = [], ''
    for i in range(count):
        noff, off, size, zsize = struct.unpack_from('<IIII', buf, SECTOR + i * 16)
        if magic == b'Dave':
            name = _decode_name(names, noff, prev)
        else:
            name = names[noff:names.index(b'\0', noff)].decode('latin-1')
        prev = name
        entries.append((name, off, size, zsize))
    hdr = dict(magic=magic, count=count, dir_size=dir_size, names_size=names_size,
               data_start=SECTOR + dir_size + names_size)
    return hdr, entries


def _is_zlib(raw):
    return len(raw) >= 2 and raw[0] & 0x0F == 8 and (raw[0] << 8 | raw[1]) % 31 == 0


def get(buf, entry):
    name, off, size, zsize = entry
    raw = bytes(buf[off:off + zsize])
    if size == zsize:
        return raw
    data = zlib.decompress(raw, 15 if _is_zlib(raw) else -15)
    if len(data) != size:
        raise ValueError(f'{name}: size mismatch {len(data)} != {size}')
    return data


def _compress_like(original_raw, data):
    """Compress new data with the same container (zlib vs raw deflate) the original used."""
    if _is_zlib(original_raw):
        return zlib.compress(data, 9)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def rebuild(buf, replacements):
    """Rebuild archive bytes, swapping file contents by name. Keeps header, names block,
    directory order, data order and 0x800 alignment of originally sector-aligned files."""
    hdr, entries = parse(buf)
    unknown = set(replacements) - {e[0] for e in entries}
    if unknown:
        raise KeyError(f'not in archive: {sorted(unknown)}')
    out = bytearray(buf[:hdr['data_start']])
    new_pos = {}
    for idx in sorted(range(len(entries)), key=lambda i: entries[i][1]):
        name, off, size, zsize = entries[idx]
        raw = bytes(buf[off:off + zsize])
        if name in replacements:
            data = replacements[name]
            if size == zsize:  # stored uncompressed originally: keep it that way
                raw, zsize = data, len(data)
            else:
                raw = _compress_like(raw, data)
                zsize = len(raw)
            size = len(data)
        align = SECTOR if off % SECTOR == 0 else 0x10
        out.extend(b'\0' * (-len(out) % align))
        new_pos[idx] = (len(out), size, zsize)
        out.extend(raw)
    out.extend(b'\0' * (-len(out) % SECTOR))
    for idx, (off, size, zsize) in new_pos.items():
        noff = struct.unpack_from('<I', buf, SECTOR + idx * 16)[0]
        struct.pack_into('<IIII', out, SECTOR + idx * 16, noff, off, size, zsize)
    return bytes(out)


if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]
    buf = open(path, 'rb').read()
    hdr, entries = parse(buf)
    if cmd == 'list':
        print(f'{path}: {hdr["magic"].decode()} {len(entries)} files')
        for name, off, size, zsize in entries:
            print(f'{"Z" if size != zsize else " "} {size:>10} {name}')
    elif cmd == 'extract':
        out = sys.argv[3]
        pat = sys.argv[4].lower() if len(sys.argv) > 4 else ''
        os.makedirs(out, exist_ok=True)
        for e in entries:
            if pat in e[0].lower():
                with open(os.path.join(out, e[0]), 'wb') as g:
                    g.write(get(buf, e))
        print('ok')
