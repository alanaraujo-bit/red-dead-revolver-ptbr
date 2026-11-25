"""Hex peek: py -I peek.py FILE [offset] [length]"""
import sys
p = sys.argv[1]
off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 256
d = open(p, 'rb').read()
print(f'size={len(d)}')
for i in range(off, min(off + n, len(d)), 16):
    row = d[i:i + 16]
    print(f'{i:08x}  {row.hex(" "):<47}  {"".join(chr(c) if 32 <= c < 127 else "." for c in row)}')
