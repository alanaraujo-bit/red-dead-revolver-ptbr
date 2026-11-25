"""Exact characters each font must render: table font of every translated row plus fonts that
UI layouts (.swui FONT:/TEXTBOX/BUTTON tags) apply to string keys. usage: fontneeds.py ISO"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660
from build import load_translations, load_swui_map, load_new_keys
from extract import SKIP

tm, override = load_translations()
swui_map = load_swui_map()
new_keys = load_new_keys()
needs = collections.defaultdict(set)
swui_keys = collections.defaultdict(set)   # key -> fonts
# Lookup tables whose columns the code copies into placeholders: {table: {column: font}} (from the layouts)
LOOKUP_FONTS = {
    'BookContents': {1: 'steelfish', 2: 'regulatorcondensed', 4: 'berrylium'},   # bookchapterview: heading, title, description
    'LevelTable': {2: 'regulatorcondensed', 3: 'regulatorcondensed'},             # postermultiview: level_name, level_desc
}
with open(sys.argv[1], 'rb') as f:
    idx = iso9660.index(f)
    for path in sorted(p for p in idx if p.endswith('.DAT') and p != 'STREAMS.DAT'):
        buf = iso9660.read(f, idx[path])
        try:
            entries = dave.parse(buf)[1]
        except ValueError:
            continue
        texts = dict(new_keys)  # rows build.py adds to swat.strtbl
        for e in entries:
            if e[0].endswith('.strtbl') and not SKIP.search(e[0]):
                t = strtbl.parse(dave.get(buf, e))
                for key, row in zip(strtbl.row_keys(t), t['rows']):
                    pt = override.get(f'{e[0][:-7]}/{key}', tm.get(row['text'], row['text']))
                    texts[key] = pt
                    needs[row['font'].lower()].update(pt)
            elif '.swui' in e[0]:
                font = table = None
                body = re.sub(r'(?m)^\s*;.*$', '', dave.get(buf, e).decode('latin-1', 'replace'))   # drop commented-out tags
                for tag in re.findall(r'<([^<>]*)>', body):
                    parts = tag.split(':')
                    if parts[0] == 'LOOKUP':
                        table = parts[1]
                        continue
                    if parts[0] == 'LOOKUPDATA':   # table values shown via code (e.g. map names on posters)
                        for col, v in enumerate(tag[11:].split(',')):
                            if col in LOOKUP_FONTS.get(table, {}):
                                swui_keys[v.strip()].add(LOOKUP_FONTS[table][col])
                        continue
                    if parts[0] == 'FONT':
                        font = parts[1].lower()
                        continue
                    if font and len(parts) > 1:
                        for p in parts[1:]:  # the key can be any field (e.g. BUTTON name btnNo)
                            swui_keys[p].add(font)
                        if parts[-1] in swui_map:  # translated literal label
                            needs[font].update(swui_map[parts[-1]])
        for key, fonts in swui_keys.items():
            if key in texts:
                for fn in fonts:
                    needs[fn].update(texts[key])
                    if os.environ.get('WHY') and fn == os.environ['WHY'].split(':')[0] and set(os.environ['WHY'].split(':')[1]) & set(texts[key]):
                        print('WHY', path, key, repr(texts[key][:60]))
report = {}
for fn, chars in sorted(needs.items()):
    ext = ''.join(sorted(c for c in chars if ord(c) > 126))
    report[fn] = ext
    print(f'{fn:20} {ext}')
import json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json.dump(report, open(os.path.join(ROOT, 'work', 'fontneeds.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
