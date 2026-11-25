"""STREAMS.DAT voice/music streams (.stm, header 'STMA').

Header (little endian): 'STMA', version, header size (0x40 mono / 0x80 stereo), sample rate (24000),
codec? (4), channels, data size, ?; audio data starts at 0x800. Codec: IMA/DVI ADPCM, 4 bits per sample,
no block headers (predictor and step start at 0), high nibble first.
24000 Hz mono for voices; the _PLII cutscene mixes are stereo (layout not mapped yet).

usage: stma.py decode in.stm out.wav
       stma.py prep recording.(wav|m4a|mp3...) ref.stm out.wav   (ffmpeg: mono, stream rate, trimmed, levelled)
       stma.py refs ORIGINAL.iso dublagem/<roteiro>.json   (original lines -> work/audio, for the studio)
       stma.py prepall ORIGINAL.iso   (every take in work/dub/raw/<stream>.<ext>, e.g. from dublagem/estudio.html)
       stma.py encode in.wav ref.stm out.stm   (mono 16-bit WAV at the reference rate)
build.py writes work/dub/<stream>.wav over the stream in STREAMS.DAT.
"""
import sys, struct, wave

STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80,
        88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598,
        658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327,
        3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289,
        16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
INDEX = [-1, -1, -1, -1, 2, 4, 6, 8]
DATA = 0x800


def header(d):
    magic, ver, hsize, rate, codec, ch, size = struct.unpack_from('<4s6I', d, 0)
    assert magic == b'STMA', 'not an STMA stream'
    return dict(rate=rate, channels=ch, size=size, codec=codec)


def _step(n, pred, idx):
    s = STEP[idx]
    diff = s >> 3
    if n & 4: diff += s
    if n & 2: diff += s >> 1
    if n & 1: diff += s >> 2
    pred = max(-32768, min(32767, pred - diff if n & 8 else pred + diff))
    idx = max(0, min(88, idx + INDEX[n & 7]))
    return pred, idx


def decode(d, high_first=True):
    h = header(d)
    assert h['channels'] == 1, 'mono only'   # shortcut: stereo (cutscene _PLII) layout not mapped yet
    pred = idx = 0
    out = []
    for b in d[DATA:DATA + h['size']]:
        for n in ((b >> 4, b & 15) if high_first else (b & 15, b >> 4)):
            pred, idx = _step(n, pred, idx)
            out.append(pred)
    return h, out


def encode(samples):
    """Standard IMA encoder (same decoder state), high nibble first like the game (DVI order)."""
    pred = idx = 0
    out = bytearray()
    nib = []
    for x in samples:
        s = STEP[idx]
        diff = x - pred
        n = 8 if diff < 0 else 0
        diff = abs(diff)
        if diff >= s: n |= 4; diff -= s
        if diff >= s >> 1: n |= 2; diff -= s >> 1
        if diff >= s >> 2: n |= 1
        pred, idx = _step(n, pred, idx)
        nib.append(n)
    if len(nib) % 2:
        nib.append(0)
    for a, b in zip(nib[::2], nib[1::2]):
        out.append(a << 4 | b)
    return bytes(out)


def write_wav(path, rate, samples):
    w = wave.open(path, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    w.close()


def build(ref, wav_path):
    """New stream with ref's header and the WAV's audio. Header +0x18: data size (padded to 0x200),
    +0x1c: about half the sample count in the shipped files (written so)."""
    h = header(ref)
    w = wave.open(wav_path, 'rb')
    if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, h['rate']):
        raise ValueError(f'{wav_path}: need mono 16-bit WAV at {h["rate"]} Hz (use stma.py prep)')
    s = struct.unpack(f'<{w.getnframes()}h', w.readframes(w.getnframes()))
    data = encode(s)
    data += b'\x08' * (-len(data) % 0x200)   # nibbles 0/8 alternate +-step/8: silence without drift
    hdr = bytearray(ref[:DATA])
    struct.pack_into('<II', hdr, 0x18, len(data), len(s) // 2)
    return bytes(hdr) + data


def main():
    cmd = sys.argv[1]
    if cmd == 'decode':
        d = open(sys.argv[2], 'rb').read()
        h, s = decode(d)
        write_wav(sys.argv[3], h['rate'], s)
        print(f"{h['rate']} Hz, {len(s) / h['rate']:.2f} s")
    elif cmd == 'prep':   # any recording -> mono 16-bit at the stream rate, level close to the game's voices
        import subprocess
        h = header(open(sys.argv[3], 'rb').read())
        limit = h['size'] * 2 / h['rate']   # the take must fit the original slot

        def run(tempo):
            af = ('highpass=f=70,silenceremove=start_periods=1:start_threshold=-45dB,'
                  'areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,'
                  + (f'atempo={tempo:.4f},' if tempo > 1 else '')
                  # the shipped voices are heavily compressed (RMS about -11 dBFS): match them
                  + 'acompressor=threshold=-30dB:ratio=8:attack=3:release=80,loudnorm=I=-8:TP=-0.5:LRA=4')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', sys.argv[2], '-ac', '1', '-ar', str(h['rate']),
                            '-af', af, '-sample_fmt', 's16', sys.argv[4]], check=True)
            w = wave.open(sys.argv[4], 'rb')
            return w.getnframes() / w.getframerate()

        dur = run(1)
        if dur > limit:
            tempo = dur / limit * 1.01
            if tempo > 1.4:
                raise SystemExit(f'take is {dur:.2f} s, slot {limit:.2f} s: too long to speed up cleanly, record it shorter')
            dur = run(tempo)
            print(f'sped up x{tempo:.2f}')
        print(f'{dur:.2f} s (slot {limit:.2f} s)')
    elif cmd == 'prepall':   # every take in work/dub/raw (named <stream>.<ext>) -> work/dub/<stream>.wav
        import os, glob, subprocess
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import iso9660, dave
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        takes = [p for p in glob.glob(os.path.join(root, 'work', 'dub', 'raw', '*.*')) if not os.path.basename(p).startswith('tts_')]
        with open(sys.argv[2], 'rb') as f:   # original ISO: reference streams come from it
            idx = iso9660.index(f)
            base = idx['STREAMS.DAT'][1] * 2048
            f.seek(base)
            entries = {e[0].lower(): e for e in dave.parse(f.read(8 << 20))[1]}
            for t in sorted(takes):
                name = os.path.splitext(os.path.basename(t))[0]
                e = entries.get(name.lower() + '.stm')
                if not e:
                    print(f'{name}: no such stream, skipped')
                    continue
                ref = os.path.join(root, 'work', 'audio', name + '.stm')
                if not os.path.exists(ref):
                    os.makedirs(os.path.dirname(ref), exist_ok=True)
                    f.seek(base + e[1])
                    open(ref, 'wb').write(f.read(e[2]))
                print(name, end=': ', flush=True)
                subprocess.run([sys.executable, '-E', '-X', 'utf8', os.path.abspath(__file__), 'prep', t, ref,
                                os.path.join(root, 'work', 'dub', name + '.wav')], check=False)
    elif cmd == 'refs':   # originals of a script's lines -> work/audio/<stream>.stm + .wav (the studio plays them)
        import os, json
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import iso9660, dave
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        names = [x['stream'] for x in json.load(open(sys.argv[3], encoding='utf-8'))['falas']]
        out = os.path.join(root, 'work', 'audio')
        os.makedirs(out, exist_ok=True)
        with open(sys.argv[2], 'rb') as f:
            idx = iso9660.index(f)
            base = idx['STREAMS.DAT'][1] * 2048
            f.seek(base)
            entries = {e[0].lower(): e for e in dave.parse(f.read(8 << 20))[1]}
            for n in names:
                e = entries[n.lower() + '.stm']
                f.seek(base + e[1])
                d = f.read(e[2])
                open(os.path.join(out, n + '.stm'), 'wb').write(d)
                h, s = decode(d)
                write_wav(os.path.join(out, n + '.wav'), h['rate'], s)
                print(n, f"{len(s) / h['rate']:.2f} s")
    elif cmd == 'encode':
        ref = open(sys.argv[3], 'rb').read()
        out = build(ref, sys.argv[2])
        open(sys.argv[4], 'wb').write(out)
        print(f'{len(out)} bytes (original {len(ref)})')


if __name__ == '__main__':
    main()
