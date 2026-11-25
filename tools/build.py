"""Build the PT-BR ISO: translate every runtime string table, swap patched fonts, relocate
changed archives inside a copy of the original image (the original is never written).

usage: build.py ORIGINAL.iso OUTPUT.iso [--mark]
  --mark  prefix every string with accented test characters (pipeline/font test)
"""
import sys, os, re, json, glob, shutil, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dave, strtbl, iso9660, rscpatch
from extract import SKIP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR_DIR = os.path.join(ROOT, 'traducao')
FONT_DIR = os.path.join(ROOT, 'work', 'fonts_out')   # patched *.fonttex / *.tex by file name
TEX_DIR = os.path.join(ROOT, 'work', 'tex_out')      # translated textures (texpatch.py) by file name
MARK = 'ãÉç '


def load_translations():
    """traducao/bNN.json: {source id: pt}; traducao/_override.json: {"table/key": pt}.
    Returns (tm: {english: pt}, override)."""
    src = {it['id']: it['en'] for it in json.load(open(os.path.join(ROOT, 'work', 'source.json'), encoding='utf-8'))}
    tm, override = {}, {}
    files = sorted(glob.glob(os.path.join(TR_DIR, 'b*.json'))) + glob.glob(os.path.join(TR_DIR, '_override.json'))
    for p in files:
        data = json.load(open(p, encoding='utf-8'))
        is_ovr = os.path.basename(p).startswith('_override')
        for k, v in data.items():
            if is_ovr:
                override[k] = v
                continue
            if k not in src:
                raise KeyError(f'{p}: unknown source id {k}')
            if src[k] in tm and tm[src[k]] != v:
                raise ValueError(f'{p}: id {k} translated twice differently')
            tm[src[k]] = v
    return tm, override


SWUI_TAGS = ('TEXT', 'TEXTBOX', 'BUTTON', 'LABEL')


def load_swui_map():
    p = os.path.join(TR_DIR, '_swui.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def translate_swui(data, mapping):
    """Swap literal UI labels (last field of TEXT/TEXTBOX/BUTTON/LABEL tags that are not string keys)."""
    txt = data.decode('latin-1')

    def fix(m):
        parts = m.group(1).split(':')
        if parts[0] in SWUI_TAGS and len(parts) > 1 and parts[-1] in mapping:
            parts[-1] = mapping[parts[-1]]
            return '<' + ':'.join(parts) + '>'
        return m.group(0)
    return re.sub(r'<([^<>]*)>', fix, txt).encode('latin-1')


def load_new_keys():
    """traducao/_keys.json {key: pt}: rows added to swat.strtbl for UI layout labels that are not
    string keys. The engine resolves every .swui label through the table and only shows the literal
    when the key is missing, so a new key translates the label without touching the layout."""
    p = os.path.join(TR_DIR, '_keys.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def add_keys(t, new):
    """Add rows for keys missing from table t (keys stay in their case-insensitive sorted order)."""
    import bisect
    taken = {r['hash'] for r in t['rows']}
    low = [k.lower() for k in t['keys']]
    added = 0
    for key, pt in new.items():
        if key in t['keys']:
            continue
        h = strtbl.elf_hash(key)
        if h in taken:
            raise ValueError(f'_keys.json: hash of {key!r} collides with an existing key')
        i = bisect.bisect_left(low, key.lower())
        t['keys'].insert(i, key)
        low.insert(i, key.lower())
        t['rows'].append(dict(hash=h, flag=1, font='berrylium', text=pt, sx=0.8, sy=0.8, tail=0))
        taken.add(h)
        added += 1
    return added


SUB_TIME = re.compile(r'^\d\d:\d\d\.\d$')


def sub_key(a, b):
    """Normalised 'line1<TAB>line2': no surrounding quotes/blanks (Excel export), single spaces."""
    norm = lambda s: re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip().strip('"').strip()
    return norm(a) + '\t' + norm(b)


def load_subs():
    """traducao/_subs.json {'en1<TAB>en2': 'pt1<TAB>pt2'} for the *_en.txt subtitle files."""
    p = os.path.join(TR_DIR, '_subs.json')
    if not os.path.exists(p):
        return {}
    return {sub_key(*k.split('\t')): v for k, v in json.load(open(p, encoding='utf-8')).items() if not k.startswith('_')}


def translate_subs(data, mapping, missing):
    """Subtitle file: UTF-16LE + BOM, CRLF, rows 'mm:ss.t<TAB>line1<TAB>line2<TAB>secs'.
    Fields with a comma are written quoted, like the shipped Excel export."""
    if not data.startswith(b'\xff\xfe') or len(data) % 2:
        return data   # not a shipped UTF-16 subtitle table (debug/test files): leave untouched
    text = data.decode('utf-16')
    out = []
    for line in text.split('\r\n'):
        f = line.split('\t')
        if len(f) >= 4 and SUB_TIME.match(f[0]) and (f[1].strip() or f[2].strip()):
            k = sub_key(f[1], f[2])
            if k in mapping:
                f[1:3] = [f'"{s}"' if ',' in s else s for s in mapping[k].split('\t')]
            else:
                missing.add(k)
        out.append('\t'.join(f))
    return ('\ufeff' + '\r\n'.join(out)).encode('utf-16-le')


def load_pck_map():
    """traducao/_pck.json {english: pt}. Strings live in script constant pools, so the replacement
    must keep the exact byte length (extra NULs would add constants and shift every index)."""
    p = os.path.join(TR_DIR, '_pck.json')
    if not os.path.exists(p):
        return {}
    out = {}
    for en, pt in json.load(open(p, encoding='utf-8')).items():
        a, b = en.encode('latin-1'), pt.encode('latin-1')
        if len(b) > len(a):
            raise ValueError(f'_pck.json: {pt!r} is longer than {en!r} ({len(b)} > {len(a)})')
        pad = len(a) - len(b)
        out[a] = b' ' * (pad // 2) + b + b' ' * (pad - pad // 2)
    return out


def translate_pck(data, mapping):
    """Replace whole pool strings (preceded by NUL/0xCD, followed by NUL), same length."""
    if not mapping:
        return data
    pat = re.compile(rb'(?<=[\x00\xcd])(' + b'|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)) + rb')(?=\x00)')
    return pat.sub(lambda m: mapping[m.group(1)], data)


# Journal page pcks draw their lists (raw nameList strings) with page fonts that hold ASCII only
JOURNAL_PAGE = re.compile(r'j(0[2-9]|1\d)_\d\d_')


def ascii_map(mapping):
    """Same replacements without accents (Latin-1: one byte per letter, so lengths stay)."""
    import unicodedata
    strip = lambda b: ''.join(c for c in unicodedata.normalize('NFKD', b.decode('latin-1'))
                              if not unicodedata.combining(c)).encode('latin-1')
    return {k: strip(v) for k, v in mapping.items()}


def dub_streams(f, idx):
    """work/dub/<stream>.wav (mono 16-bit at the stream's rate, see stma.py prep): encode and write over
    that stream inside STREAMS.DAT in place. The new audio must fit the original entry; the header's data
    size tells the game where it ends, the rest of the entry is zeroed."""
    import stma
    wavs = sorted(glob.glob(os.path.join(ROOT, 'work', 'dub', '*.wav')))
    if not wavs:
        return
    base = idx['STREAMS.DAT'][1] * 2048
    f.seek(base)
    entries = {e[0].lower(): e for e in dave.parse(f.read(8 << 20))[1]}   # directory fits in the first 8 MiB
    for w in wavs:
        name = os.path.splitext(os.path.basename(w))[0].lower() + '.stm'
        e = entries.get(name)
        if not e:
            raise SystemExit(f'dub: no stream {name} in STREAMS.DAT')
        f.seek(base + e[1])
        ref = f.read(e[2])
        new = stma.build(ref, w)
        if len(new) > e[2]:
            raise SystemExit(f'dub: {name} is {len(new)} bytes, the original slot holds {e[2]} (shorten the take)')
        f.seek(base + e[1])
        f.write(new + b'\0' * (e[2] - len(new)))
    print(f'dubbed streams: {len(wavs)}')


def main():
    src, dst = sys.argv[1], sys.argv[2]
    mark = '--mark' in sys.argv
    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit('output must differ from the original ISO')
    tm, override = load_translations()
    pck_map = {} if '--no-pck' in sys.argv else load_pck_map()
    pck_ascii = ascii_map(pck_map)
    swui_map = {} if '--no-swui' in sys.argv else load_swui_map()
    new_keys = {} if '--no-keys' in sys.argv else load_new_keys()
    subs = {} if '--no-subs' in sys.argv else load_subs()
    subs_missing = set()
    if '--keys-only' in sys.argv:   # diagnostics: add only the listed keys
        keep = sys.argv[sys.argv.index('--keys-only') + 1].split('|')
        new_keys = {k: v for k, v in new_keys.items() if k in keep}
    if '--swui-ascii' in sys.argv:  # diagnostics: strip accents from UI labels
        import unicodedata
        swui_map = {k: unicodedata.normalize('NFKD', v).encode('ascii', 'ignore').decode() for k, v in swui_map.items()}
    if '--swui-only' in sys.argv:   # diagnostics: translate only the listed labels
        keep = sys.argv[sys.argv.index('--swui-only') + 1].split('|')
        swui_map = {k: v for k, v in swui_map.items() if k in keep}
    fonts = {} if '--no-fonts' in sys.argv else \
        {os.path.basename(p): open(p, 'rb').read() for p in glob.glob(os.path.join(FONT_DIR, '*'))}
    rsc_tex = {}
    if '--no-tex' not in sys.argv:
        loose = {os.path.basename(p): open(p, 'rb').read() for p in glob.glob(os.path.join(TEX_DIR, '*.tex'))}
        fonts.update(loose)
        rsc_tex = {n[:-4]: v for n, v in loose.items()}   # level packs embed copies of 3D textures
        fonts.update({os.path.basename(p): open(p, 'rb').read() for p in glob.glob(os.path.join(ROOT, 'work', 'pck_out', '*.pck'))})
    stats = dict(rows=0, translated=0, missing=set())
    new_files = {}
    t0 = time.time()
    with open(src, 'rb') as f:
        idx = iso9660.index(f)
        for path in sorted(p for p in idx if p.endswith('.DAT')):
            buf = iso9660.read(f, idx[path])
            try:
                _, entries = dave.parse(buf)
            except ValueError:
                continue
            repl = {}
            for e in entries:
                name = e[0]
                if name in fonts:
                    repl[name] = fonts[name]
                if name.endswith('.pck') and pck_map:
                    old = fonts.get(name) or dave.get(buf, e)   # pck_out/ edits (static text) + string pools
                    new = translate_pck(old, pck_ascii if JOURNAL_PAGE.match(name) else pck_map)
                    if new != old:
                        assert len(new) == len(old)
                        repl[name] = new
                        stats['pck'] = stats.get('pck', 0) + 1
                if name.endswith('.rsc') and rsc_tex:
                    old = dave.get(buf, e)
                    new = rscpatch.patch(old, rsc_tex, log=lambda m: stats.setdefault('rsc_log', set()).add(m))
                    if new != old:
                        repl[name] = new
                        stats['rsc'] = stats.get('rsc', 0) + 1
                if name.endswith('_en.txt') and subs:
                    old = dave.get(buf, e)
                    new = translate_subs(old, subs, subs_missing)
                    if new != old:
                        repl[name] = new
                        stats['subs'] = stats.get('subs', 0) + 1
                if '.swui' in name and swui_map:
                    old = dave.get(buf, e)
                    new = translate_swui(old, swui_map)
                    if new != old:
                        repl[name] = new
                        stats['swui'] = stats.get('swui', 0) + 1
                if not name.endswith('.strtbl') or SKIP.search(name):
                    continue
                t = strtbl.parse(dave.get(buf, e))
                changed = False
                for key, row in zip(strtbl.row_keys(t), t['rows']):
                    en = row['text']
                    if not en.strip():
                        continue
                    stats['rows'] += 1
                    pt = override.get(f'{name[:-7]}/{key}', tm.get(en))
                    if pt is None:
                        stats['missing'].add(en)
                        pt = en
                    else:
                        stats['translated'] += 1
                    if mark:
                        pt = MARK + pt
                    if pt != en:
                        row['text'] = pt
                        changed = True
                if name == 'swat.strtbl' and new_keys:
                    n = add_keys(t, new_keys)
                    stats['keys'] = n
                    changed = changed or n > 0
                if changed:
                    repl[name] = strtbl.build(t)
            if repl:
                new_files[path] = dave.rebuild(buf, repl)
    print(f'archives changed: {len(new_files)}  rows: {stats["rows"]}  translated: {stats["translated"]}  '
          f'missing unique: {len(stats["missing"])}  new keys/table: {stats.get("keys", 0)}  swui files: {stats.get("swui", 0)}  pck files: {stats.get("pck", 0)}  '
          f'rsc packs: {stats.get("rsc", 0)} {sorted(stats.get("rsc_log", []))}  '
          f'subtitle files: {stats.get("subs", 0)} (untranslated lines: {len(subs_missing)})  '
          f'({time.time() - t0:.0f}s)')
    tmp = dst + '.partial'
    shutil.copyfile(src, tmp)
    with open(tmp, 'r+b') as f:
        idx = iso9660.index(f)
        iso9660.replace_files(f, idx, new_files, force_append='--relocate-all' in sys.argv)
        if '--no-dub' not in sys.argv:
            dub_streams(f, idx)
    os.replace(tmp, dst)
    print(f'wrote {dst} ({os.path.getsize(dst) / 2**30:.2f} GiB)')


if __name__ == '__main__':
    main()
