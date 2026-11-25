"""Minimal ISO9660 access for the PS2 disc: find files, read them, relocate replaced files.

Only the ISO9660 tree is updated (that is what the PS2 BIOS and PCSX2 read);
the UDF bridge keeps pointing at the original extents.
"""
import struct

SECTOR = 2048
TAIL_PAD = 2048  # sectors (4 MiB) of zeros after relocated files


def _records(f, lba, size):
    f.seek(lba * SECTOR)
    data = f.read(size)
    pos = 0
    while pos < len(data):
        n = data[pos]
        if n == 0:  # records never cross sectors: skip to the next one
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + n]
        name = rec[33:33 + rec[32]]
        yield lba * SECTOR + pos, rec, name
        pos += n


def walk(f):
    """Yield (path, record_file_offset, lba, size, is_dir) for every entry."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    if pvd[1:6] != b'CD001':
        raise ValueError('no ISO9660 PVD')
    root = pvd[156:156 + 34]
    stack = [('', struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0])]
    while stack:
        base, lba, size = stack.pop()
        for off, rec, name in _records(f, lba, size):
            if name in (b'\0', b'\1'):
                continue
            n = name.decode('ascii').split(';')[0]
            path = f'{base}\\{n}' if base else n
            elba, esize = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            is_dir = bool(rec[25] & 2)
            yield path, off, elba, esize, is_dir
            if is_dir:
                stack.append((path, elba, esize))


def index(f):
    return {p.upper(): (off, lba, size) for p, off, lba, size, d in walk(f) if not d}


def read(f, entry):
    _, lba, size = entry
    f.seek(lba * SECTOR)
    return f.read(size)


def replace_files(f, idx, new_files, force_append=False):
    """Write each new file in place if it fits its old extent, else append it at the end
    of the image. Patches directory records and the PVD volume size. f opened 'r+b'.
    force_append: always relocate (used to exercise the relocation path in tests)."""
    f.seek(0, 2)
    end = orig_end = f.tell()
    if end % SECTOR:
        raise ValueError('image size is not sector aligned')
    for path, data in new_files.items():
        rec_off, lba, size = idx[path.upper()]
        old_sectors = -(-size // SECTOR)
        new_sectors = -(-len(data) // SECTOR)
        if new_sectors <= old_sectors and not force_append:
            new_lba = lba
        else:
            new_lba = end // SECTOR
            end += new_sectors * SECTOR
        f.seek(new_lba * SECTOR)
        f.write(data + b'\0' * (new_sectors * SECTOR - len(data)))
        f.seek(rec_off + 2)
        f.write(struct.pack('<I', new_lba) + struct.pack('>I', new_lba))
        f.write(struct.pack('<I', len(data)) + struct.pack('>I', len(data)))
        idx[path.upper()] = (rec_off, new_lba, len(data))
    if end > orig_end:
        # The game reads ahead past the end of files; on the original disc other data follows,
        # so keep a zero tail after the last relocated file or reads run past EOF and it hangs.
        f.seek(end)
        f.write(b'\0' * (TAIL_PAD * SECTOR))
    f.seek(0, 2)
    total = f.tell() // SECTOR
    f.seek(16 * SECTOR + 80)
    f.write(struct.pack('<I', total) + struct.pack('>I', total))
