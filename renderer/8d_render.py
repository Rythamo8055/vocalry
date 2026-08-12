#!/usr/bin/env python3
"""Binaural 3D (8D) renderer using MIT KEMAR HRTF data.
Each stem orbits the listener on its own circular path (azimuth rotates
continuously at per-stem speed/phase/elevation) and is filtered through
real head-related impulse responses for true headphone 3D.

Usage: render_8d.py <stems_dir> <out_wav> [--hrtf path/to/full.zip]
Stem files are matched by name: (Vocals|Drums|Bass|Guitar|Piano|Other).wav
"""
import argparse, io, os, re, sys, time, wave, zipfile
import numpy as np
from scipy.signal import fftconvolve

SR = 44100
BLOCK = 4096
HOP = 2048
CROSSFADE = 512

STEM_PRESETS = {
    "vocals": dict(speed=0.10, az0=0.0, elev=10.0, gain=1.00),
    "drums":  dict(speed=0.22, az0=180.0, elev=0.0, gain=0.85),
    "bass":   dict(speed=0.05, az0=0.0, elev=0.0, gain=1.00),
    "guitar": dict(speed=0.16, az0=90.0, elev=10.0, gain=0.75),
    "piano":  dict(speed=0.18, az0=270.0, elev=0.0, gain=0.60),
    "other":  dict(speed=0.13, az0=45.0, elev=-10.0, gain=0.85),
}

def load_hrtf(zip_path):
    z = zipfile.ZipFile(zip_path)
    hrtf = {}
    for n in z.namelist():
        if not n.endswith(".wav"):
            continue
        parts = n.split("/")
        if not parts[0].startswith("elev"):
            continue
        elev = int(parts[0].replace("elev", ""))
        fn = parts[-1]
        ear = fn[0]
        m = re.search(r"e(\d{3})", fn)
        az = int(m.group(1))
        w = wave.open(io.BytesIO(z.read(n)))
        ir = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        hrtf.setdefault((elev, az), {})[ear] = ir
    print(f"loaded {len(hrtf)} HRTF positions")
    return hrtf

def nearest_azimuth(hrtf, elev, az):
    elevs = sorted(set(k[0] for k in hrtf))
    e = min(elevs, key=lambda x: abs(x - elev))
    azs = sorted(k[1] for k in hrtf if k[0] == e)
    a = min(azs, key=lambda x: min(abs(x - az), 360 - abs(x - az)))
    irl = hrtf[(e, a)]["L"]
    irr = hrtf[(e, a)]["R"]
    return (irl, irr), e, a

def render_stem(hrtf, mono, speed, az0, elev, gain):
    n = len(mono)
    out_l = np.zeros(n + 512, dtype=np.float64)
    out_r = np.zeros(n + 512, dtype=np.float64)
    t_prev = None
    prev_l = prev_r = None
    t0 = time.time()
    for pos in range(0, n, HOP):
        seg = mono[pos:pos + BLOCK]
        if len(seg) < BLOCK:
            seg = np.pad(seg, (0, BLOCK - len(seg)))
        az = (az0 + 360.0 * speed * pos / SR) % 360.0
        (irl, irr), e, a = nearest_azimuth(hrtf, elev, az)
        l = fftconvolve(seg, irl)
        r = fftconvolve(seg, irr)
        if prev_l is not None:
            cf = np.minimum(np.arange(len(l)) / CROSSFADE, 1.0)
            l = prev_l * (1 - cf) + l * cf
            r = prev_r * (1 - cf) + r * cf
        out_l[pos:pos + len(l)] += l[:len(out_l) - pos]
        out_r[pos:pos + len(r)] += r[:len(out_r) - pos]
        prev_l, prev_r = l, r
    print(f"  rendered stem in {time.time() - t0:.1f}s")
    return out_l * gain, out_r * gain

def make_reverb_ir(tail=1.6, predelay=0.030, lp_hz=6000):
    n_tail = int(SR * tail)
    t = np.arange(n_tail) / SR
    noise = np.random.randn(n_tail)
    env = np.exp(-t / 0.35)
    ir = noise * env
    ir = np.concatenate([np.zeros(int(SR * predelay)), ir])
    freqs = np.fft.rfftfreq(len(ir), 1 / SR)
    filt = 1.0 / (1.0 + (freqs / lp_hz) ** 2)
    ir_l = np.fft.irfft(np.fft.rfft(ir) * filt)
    ir_r = np.fft.irfft(np.fft.rfft(np.roll(ir, 100)) * filt)
    return ir_l / np.max(np.abs(ir_l)), ir_r / np.max(np.abs(ir_r))

def render(stems_dir, out_wav, hrtf_zip, wet=0.35):
    print("loading HRTF...")
    hrtf = load_hrtf(hrtf_zip)
    ir_l, ir_r = make_reverb_ir()

    stems = {}
    for key in STEM_PRESETS:
        for fn in sorted(os.listdir(stems_dir)):
            if f"({key.capitalize()})" in fn and fn.endswith(".wav"):
                data, sr = sf_read(stems_dir, fn)
                if sr != SR:
                    raise SystemExit(f"bad sample rate {sr} in {fn}")
                mono = data.mean(axis=1) if data.ndim == 2 else data
                mono = mono / (np.max(np.abs(mono)) + 1e-9)
                stems[key] = mono
                print(f"stem {key}: {fn} ({len(mono)/SR:.1f}s)")
                break
    if not stems:
        raise SystemExit("no stems found")

    total_n = max(len(m) for m in stems.values()) + 4096
    mix_l = np.zeros(total_n)
    mix_r = np.zeros_like(mix_l)
    for key, mono in stems.items():
        p = STEM_PRESETS[key]
        l, r = render_stem(hrtf, mono, p["speed"], p["az0"], p["elev"], p["gain"])
        mix_l[:len(l)] += l
        mix_r[:len(r)] += r

    print("applying room reverb...")
    wet_l = fftconvolve(mix_l, ir_l)[:len(mix_l)]
    wet_r = fftconvolve(mix_r, ir_r)[:len(mix_r)]
    master_l = mix_l + wet * wet_l
    master_r = mix_r + wet * wet_r

    peak = max(np.max(np.abs(master_l)), np.max(np.abs(master_r)))
    master_l /= peak
    master_r /= peak
    stereo = np.stack([master_l, master_r], axis=1)
    sf_write(out_wav, stereo, SR)
    print(f"wrote {out_wav} ({len(stereo)/SR:.1f}s, peak 1.0)")
    return out_wav

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stems_dir")
    ap.add_argument("out_wav")
    ap.add_argument("--hrtf", default=None)
    ap.add_argument("--wet", type=float, default=0.35)
    args = ap.parse_args()
    hrtf = args.hrtf or os.path.join(os.path.dirname(__file__), "hrtf", "full.zip")
    render(args.stems_dir, args.out_wav, hrtf, args.wet)

def sf_read(d, fn):
    import soundfile as sf
    data, sr = sf.read(os.path.join(d, fn), dtype="float32")
    return data, sr

def sf_write(path, data, sr):
    import soundfile as sf
    sf.write(path, data, sr, subtype="FLOAT")

if __name__ == "__main__":
    main()
