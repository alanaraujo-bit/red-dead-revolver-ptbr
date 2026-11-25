"""Extract every runtime string table from the ISO into work/source.json (unique English strings
with the table/key names they appear under) and print token statistics."""
import sys, os, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660

# Dev leftovers inside SWAT.DAT that the PS2 build never loads.
SKIP = re.compile(r'^(backup_|bak2_|xb_)|^swat\.bak\.|^swat_xbx\.')


def main():
    iso, out = sys.argv[1], sys.argv[2]
    uniq = {}  # en -> {"keys": [...], "fonts": set}
    tables = collections.Counter()
    with open(iso, 'rb') as f:
        idx = iso9660.index(f)
        for path in sorted(p for p in idx if p.endswith('.DAT')):
            buf = iso9660.read(f, idx[path])
            try:
                _, entries = dave.parse(buf)
            except ValueError:
                continue
            for e in entries:
                if not e[0].endswith('.strtbl') or SKIP.search(e[0]):
                    continue
                tables[e[0]] += 1
                t = strtbl.parse(dave.get(buf, e))
                for key, row in zip(strtbl.row_keys(t), t['rows']):
                    if not row['text'].strip():
                        continue
                    u = uniq.setdefault(row['text'], {'keys': [], 'fonts': set()})
                    tag = f"{e[0][:-7]}/{key}"
                    if tag not in u['keys']:
                        u['keys'].append(tag)
                    u['fonts'].add(row['font'])
    items = [{'en': en, 'keys': v['keys'], 'fonts': sorted(v['fonts'])} for en, v in uniq.items()]
    # ids are referenced by traducao/*.json: keep existing ids stable, append new texts at the end
    old = {}
    if os.path.exists(out):
        old = {it['en']: it['id'] for it in json.load(open(out, encoding='utf-8'))}
    nxt = max([int(i) for i in old.values()] or [0]) + 1
    for it in sorted(items, key=lambda x: (x['keys'][0].lower(), x['en'])):
        if it['en'] in old:
            it['id'] = old[it['en']]
        else:
            it['id'] = f'{nxt:04d}'
            nxt += 1
    items.sort(key=lambda x: x['id'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(items, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # human-readable batches for translating: "id | first key (+n) | font | text" (newlines as ⏎)
    bdir = os.path.join(os.path.dirname(out), 'batches')
    os.makedirs(bdir, exist_ok=True)
    for b in range(0, len(items), 110):
        with open(os.path.join(bdir, f'b{b // 110 + 1:02d}.txt'), 'w', encoding='utf-8') as g:
            for it in items[b:b + 110]:
                more = f" (+{len(it['keys']) - 1})" if len(it['keys']) > 1 else ''
                g.write(f"{it['id']} | {it['keys'][0]}{more} | {','.join(it['fonts'])} | {it['en'].replace(chr(10), ' ⏎ ')}\n")

    words = sum(len(i['en'].split()) for i in items)
    print(f'tables={len(tables)} unique_strings={len(items)} words={words}')
    toks = collections.Counter()
    for i in items:
        for m in re.findall(r'%[-+ 0#]*\d*(?:\.\d+)?[a-zA-Z]|~[^~\s]{1,12}~|<[^<>]{1,20}>|\[[^\[\]]{1,20}\]|\{[^{}]{1,20}\}|\\[a-z]|[^\x20-\x7e\n]', i['en']):
            toks[m] += 1
    print('tokens:', toks.most_common(40))
    print('with newline:', sum('\n' in i['en'] for i in items))
    print('fonts:', collections.Counter(fn for i in items for fn in i['fonts']).most_common())


if __name__ == '__main__':
    main()
