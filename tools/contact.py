"""Contact sheet of every glyph of a font with its character label (for visual inspection)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontpatch as fp
from PIL import Image, ImageDraw

iso, name, out = sys.argv[1:4]
files = fp.load_from_iso(iso, [name])[name]
head, recs, npages = fp.parse_fonttex(files[name + '.fonttex'])
texs = [fp.decode_tex(files[f'{name}_{i:02d}.tex']) for i in range(npages)]
cell = 56
cols = 16
rows = (len(recs) + cols - 1) // cols
sheet = Image.new('RGBA', (cols * cell, rows * (cell + 14)), (50, 25, 25, 255))
d = ImageDraw.Draw(sheet)
for i, r in enumerate(recs):
    g = fp.cut(texs[r['page']], r)
    g.putalpha(g.getchannel('A').point(lambda v: min(255, v * 2)))
    x, y = (i % cols) * cell, (i // cols) * (cell + 14)
    if g.width > cell or g.height > cell:
        g.thumbnail((cell, cell))
    sheet.alpha_composite(g, (x + 2, y + 14))
    d.text((x + 2, y), f'{r["code"]:x}', fill=(255, 255, 0, 255))
sheet.save(out)
print(len(recs), 'glyphs')
