"""Does the ELF (or any small root file) embed the LBAs of the DAT files? (hardcoded disc layout)"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso9660

with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    elf = iso9660.read(f, idx['SLUS_205.00'])
    for path, (rec, lba, size) in sorted(idx.items()):
        if not path.endswith('.DAT') and not path.endswith('.PSS'):
            continue
        hits_lba = elf.count(struct.pack('<I', lba))
        hits_size = elf.count(struct.pack('<I', size))
        hits_sec = elf.count(struct.pack('<I', -(-size // 2048)))
        if hits_lba or hits_size or hits_sec:
            print(f'{path:24} lba={lba:8} hits_lba={hits_lba} hits_size={hits_size} hits_sectors={hits_sec}')
print('done')
