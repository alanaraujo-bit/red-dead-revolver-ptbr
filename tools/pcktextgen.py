"""Merge traducao/_pcktext_*.json (plain translations) into traducao/_pcktext.json as "auto" items.
Blocks in a subset font (catalogue 'table' set) cannot show new letters, so they switch to a full
UI-numbered font of the same pck (its advances are the UI ones scaled by size). Font ids are local
to each pck, so pcks without such a font (journal pages) keep those blocks in English.
usage: pcktextgen.py"""
import os, sys, json, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_FONTS = {'popups_01.pck': 17, 'popups_01_ingame.pck': 20, 'rewardweapon8.pck': 149}


def main():
    scan = json.load(open(os.path.join(ROOT, 'work', 'pck_static.json'), encoding='utf-8'))
    spec_path = os.path.join(ROOT, 'traducao', '_pcktext.json')
    spec = json.load(open(spec_path, encoding='utf-8'))
    for path in sorted(glob.glob(os.path.join(ROOT, 'traducao', '_pcktext_*.json'))):
        for pck, blocks in json.load(open(path, encoding='utf-8')).items():
            if pck.startswith('_'):
                continue
            out = spec.setdefault(pck, {})
            for k, tr in blocks.items():
                info = scan[pck][k]
                item = {'auto': True, ('text' if isinstance(tr, str) else 'lines'): tr}
                font = info['font']
                # journal pages hold subset fonts only, except the stats page (full fonts of its own)
                if info['table'] is not None or (re.match(r'j(0[2-9]|1\d)_', pck) and pck != 'j19_01_battles.pck'):
                    if pck not in UI_FONTS:
                        # font ids are local to each pck: a page with no full font of its own
                        # (journal pages) draws garbage with font 11. Left in English for now.
                        out.pop(k, None)
                        print('skipped (subset font only):', pck, k)
                        continue
                    item['font'] = [UI_FONTS[pck], font[1] if isinstance(font, list) else 400]
                out[k] = item
    json.dump(spec, open(spec_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('merged into', spec_path)


if __name__ == '__main__':
    main()
