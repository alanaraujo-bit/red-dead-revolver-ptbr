"""Executable strings for PCSX2: the ELF is compressed on disc (stub at 0x800008), so instead of
rebuilding it we overwrite the strings in EE RAM after it unpacks itself, with a PCSX2 cheat patch
(keeps the CRC, so the 21:9/60 FPS patches keep working). PCSX2 only.

usage: elfpatch.py EE_RAM_DUMP OUT.pnach
  EE_RAM_DUMP: eeMemory.bin from any savestate of the game (a .p2s is a zip).
traducao/_elf.json: {"0xADDR": [english, portuguese]}; the Portuguese must fit the bytes the
original string owns (its length plus the NUL padding before the next string).
"""
import sys, os, json, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUP = 'Traducao PT-BR (textos do executavel)'


def main():
    ram = bytearray(open(sys.argv[1], 'rb').read())
    orig = bytes(ram)
    table = json.load(open(os.path.join(ROOT, 'traducao', '_elf.json'), encoding='utf-8'))
    # pointer tables: strings only reachable through a table can be repacked in their joint region
    for tab in table.get('_tables', []):
        ptrs = int(tab['pointers'], 16)
        start, size = int(tab['region'][0], 16), tab['region'][1]
        en = [s.encode('latin-1') + b'\0' for s, _ in tab['strings']]
        if orig[start:start + size] != b''.join(en):
            raise SystemExit(f'table {tab["pointers"]}: region does not hold {[s for s, _ in tab["strings"]]}')
        pos = start
        for k, (_, pt) in enumerate(tab['strings']):
            ptb = pt.encode('latin-1') + b'\0'
            if pos + len(ptb) > start + size:
                raise SystemExit(f'table {tab["pointers"]}: strings need more than {size} bytes')
            if struct.unpack_from('<I', orig, ptrs + 4 * k)[0] != start + sum(len(x) for x in en[:k]):
                raise SystemExit(f'table {tab["pointers"]}: entry {k} does not point at {tab["strings"][k][0]!r}')
            ram[pos:pos + len(ptb)] = ptb
            struct.pack_into('<I', ram, ptrs + 4 * k, pos)
            pos += len(ptb)
        ram[pos:start + size] = b'\0' * (start + size - pos)
    for addr, (en, pt) in ((int(k, 16), v) for k, v in table.items() if not k.startswith('_')):
        enb, ptb = en.encode('latin-1') + b'\0', pt.encode('latin-1') + b'\0'
        if orig[addr:addr + len(enb)] != enb:
            raise SystemExit(f'{addr:#x}: expected {en!r}, found {orig[addr:addr + len(enb)]!r}')
        room = len(enb)
        while orig[addr + room] == 0:   # NUL padding up to the next string is free
            room += 1
        if len(ptb) > room:
            raise SystemExit(f'{addr:#x}: {pt!r} needs {len(ptb)} bytes, only {room} available')
        ram[addr:addr + room] = ptb + b'\0' * (room - len(ptb))
    lines = [f'[{GROUP}]', 'author=RDR-PTBR', 'description=Textos do executavel traduzidos (New Player, End...)']
    for a in range(0, len(ram), 4):
        if ram[a:a + 4] != orig[a:a + 4]:
            lines.append(f'patch=1,EE,{a:08X},word,{struct.unpack_from("<I", ram, a)[0]:08X}')
    open(sys.argv[2], 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print(f'{len(lines) - 3} words -> {sys.argv[2]}')


if __name__ == '__main__':
    main()
