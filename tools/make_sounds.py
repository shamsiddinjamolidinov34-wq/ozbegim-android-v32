#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O'zbegim: tovush signallari uchun tabiat tovushlarini sintez qiladi.

Barcha tovushlar shu skriptda matematik usulda yaratiladi (tarmoq, tashqi yozuv va mualliflik huquqi shartlari yo'q).
Natija: app/src/main/res/raw/snd_<id>.wav (bir kanalli, 44100 Hz, 16 bit).

Ishga tushirish (loyiha ildizidan):
    python3 tools/make_sounds.py                 # tovushlarni yozadi
    python3 tools/make_sounds.py --report        # o'lchovlar jadvalini ham chiqaradi
    python3 tools/make_sounds.py --plots /tmp/p  # spektrogramma rasmlarini ham saqlaydi (matplotlib kerak)

Talab: python3, numpy, scipy. Natija har safar bir xil (tasodifiy sonlar tovush nomiga bog'langan).

Balandlik: har tovush qabul qilingan sinfiga qarab "tik" ohangiga nisbatan tenglashtiriladi (A-vaznli, 250 ms oynada),
shunda bitta tovush ikkinchisidan baland yoki past eshitilmaydi. Foydalanuvchi balandligi ilovada (SoundPool) o'zgaradi.
"""
import argparse
import os
import sys
import wave
import zlib

import numpy as np
from scipy import signal

SR = 44100


# ---------------------------------------------------------------------------------------------------------------- yordamchilar

def n_of(sec):
    return int(round(sec * SR))


def axis(n):
    return np.arange(n) / SR


def seeded(name):
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


def _filt(x, kind, freqs, order):
    sos = signal.butter(order, freqs, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def bp(x, lo, hi, order=2):
    return _filt(x, "bandpass", [lo, hi], order)


def lp(x, fc, order=2):
    return _filt(x, "lowpass", fc, order)


def hp(x, fc, order=2):
    return _filt(x, "highpass", fc, order)


class Buf:
    """Vaqt bo'yicha tovushlarni joylashtiradigan bufer."""

    def __init__(self, dur):
        self.x = np.zeros(n_of(dur))

    def add(self, y, at=0.0, gain=1.0):
        i = n_of(at)
        j = i + len(y)
        if j > len(self.x):
            self.x = np.concatenate([self.x, np.zeros(j - len(self.x))])
        self.x[i:j] += gain * y
        return self


def decay_env(n, tau, attack=0.0006):
    t = axis(n)
    e = np.exp(-t / tau)
    if attack > 0:
        e = e * np.minimum(1.0, t / attack)
    return e


def fade_env(n, fin, fout):
    """Kirish va chiqishda kosinusli yumshoq o'zgarish (soniyada)."""
    e = np.ones(n)
    a = min(n, n_of(fin))
    r = min(n, n_of(fout))
    if a > 1:
        e[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 1:
        e[n - r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return e


def swell(n, lo=0.0, hi=1.0, power=2.0):
    """lo..hi oralig'ida (0..1) ko'tarilib tushuvchi sin^power to'lqin; tashqarisi nol."""
    t = np.linspace(0.0, 1.0, n)
    u = np.clip((t - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    return np.sin(np.pi * u) ** power


def slow_noise(rng, n, fc):
    """Birlik dispersiyali past chastotali shovqin (sekin tebranish uchun)."""
    x = lp(rng.standard_normal(n), fc, 2)
    s = np.std(x)
    return x / s if s > 0 else x


def pink(rng, n):
    """Pushti shovqin (1/f): oq shovqindan yumshoqroq, tabiiyroq eshitiladi. Birlik dispersiya."""
    w = rng.standard_normal(n)
    y = np.zeros(n)
    for a, g in [(0.99886, 0.0555179), (0.99332, 0.0750759), (0.96900, 0.1538520),
                 (0.86650, 0.3104856), (0.55000, 0.5329522), (-0.7616, -0.0168980)]:
        y += signal.lfilter([g], [1.0, -a], w)
    y += 0.5362 * w
    y[1:] += 0.115926 * w[:-1]
    y = hp(y, 45, 2)  # 1/f yaqinlashuvining past chastotali "siljishi" (dinamikda eshitilmaydi, faqat joy oladi) olib tashlanadi
    return y / (np.std(y) + 1e-12)


def modes(freqs, taus, amps, dur, attack=0.0005):
    """So'nuvchi sinusoidalar yig'indisi (qattiq jism zarbasi). Oxirida uzilish bo'lmasligi uchun yumshoq tugaydi."""
    n = n_of(dur)
    t = axis(n)
    y = np.zeros(n)
    for f, tau, a in zip(freqs, taus, amps):
        y += a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
    if attack > 0:
        y *= np.minimum(1.0, t / attack)
    y *= fade_env(n, 0.0, min(0.03, dur / 4.0))
    return y


def impact(rng, dur=0.008, lo=1500, hi=9000, tau=None):
    n = n_of(dur)
    x = bp(rng.standard_normal(n), lo, hi, 2)
    return x * decay_env(n, tau or dur / 3.0, 0.0002)


def bubble(f0, tau, rise=0.5, dur=None, harm2=0.0):
    """
    Havo pufakchasining Minnaert tebranishi: chastota so'nish paytida ko'tariladi ("tomchi" ovozining asosi).
    f0: boshlang'ich chastota (Hz), tau: so'nish vaqti (s), rise: chastotaning nisbiy ko'tarilishi.
    """
    n = n_of(dur if dur else tau * 6.0)
    t = axis(n)
    f = f0 * (1.0 + rise * (1.0 - np.exp(-t / (1.8 * tau))))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph)
    if harm2:
        x = x + harm2 * np.sin(2 * ph)
    return x * decay_env(n, tau, 0.0007)


def reverb(x, rng, wet=0.2, decay=0.25, pre=0.006, lo=250, hi=9000):
    """Kichik xona/g'or aks sadosi: eksponensial so'nuvchi shovqin bilan konvolyutsiya."""
    n = n_of(decay * 1.6)
    t = axis(n)
    ir = rng.standard_normal(n) * np.exp(-t / (decay / 6.9))
    ir = bp(ir, lo, hi, 1)
    ir[: n_of(pre)] = 0.0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
    w = signal.fftconvolve(x, ir)
    out = np.zeros(len(w))
    out[: len(x)] += x
    out += wet * w * (np.sqrt(np.sum(x ** 2)) / (np.sqrt(np.sum(w ** 2)) + 1e-12))
    return out


def syl(f0, f1, dur, vib_hz=0.0, vib_depth=0.0, harm=(1.0, 0.15, 0.04), shape=0.6):
    """Qush bo'g'ini: chastota f0 dan f1 gacha o'zgaradigan, yumshoq boshlanib tugaydigan ohang."""
    n = n_of(dur)
    t = axis(n)
    u = t / dur
    f = f0 + (f1 - f0) * (u ** shape if f1 >= f0 else u)
    if vib_hz:
        f = f + vib_depth * np.sin(2 * np.pi * vib_hz * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros(n)
    for k, h in enumerate(harm):
        x += h * np.sin((k + 1) * ph)
    return x * np.hanning(n)


def tone_seq(parts, fade=0.004, harm=(1.0,)):
    """Oddiy ohanlar ketma-ketligi: [(chastota, davomiylik, keyingi tovushgacha pauza), ...]."""
    b = Buf(0.0)
    at = 0.0
    for f, d, gap in parts:
        n = n_of(d)
        t = axis(n)
        x = np.zeros(n)
        for k, h in enumerate(harm):
            x += h * np.sin(2 * np.pi * f * (k + 1) * t)
        x *= fade_env(n, fade, fade)
        b.add(x, at)
        at += d + gap
    return b.x


# ----------------------------------------------------------------------------------------------------------------- tovushlar

def s_tone_tik(rng):
    return tone_seq([(1200, 0.018, 0.0)])


def s_tone_tuk(rng):
    return tone_seq([(900, 0.016, 0.0), (1500, 0.022, 0.0)])


def s_tone_edge(rng):
    return tone_seq([(330, 0.07, 0.0), (260, 0.09, 0.0)])


def s_tone_window(rng):
    return tone_seq([(660, 0.05, 0.0), (880, 0.07, 0.0)])


def s_tone_scroll(rng):
    return tone_seq([(820, 0.010, 0.026), (820, 0.010, 0.026), (820, 0.010, 0.0)], fade=0.002)


def s_tone_error(rng):
    return tone_seq([(250, 0.07, 0.015), (200, 0.12, 0.0)], fade=0.006, harm=(1.0, 0.5, 0.33))


def s_drop_tiny(rng):
    b = Buf(0.1)
    b.add(bubble(2300, 0.013, 0.30, 0.09), 0.0, 1.0)
    b.add(impact(rng, 0.003, 2000, 7000), 0.0, 0.10)
    return b.x


def s_drop_water(rng):
    b = Buf(0.3)
    b.add(bubble(950, 0.038, 0.75, 0.24, harm2=0.12), 0.004, 1.0)
    b.add(impact(rng, 0.006, 800, 5000), 0.0, 0.15)
    b.add(bubble(2100, 0.012, 0.4, 0.07), 0.052, 0.18)
    return b.x


def s_drop_deep(rng):
    b = Buf(0.5)
    b.add(bubble(360, 0.075, 0.8, 0.42, harm2=0.35), 0.003, 1.0)
    b.add(impact(rng, 0.008, 300, 2500), 0.0, 0.14)
    return reverb(b.x, rng, wet=0.35, decay=0.28)


def s_drop_pair(rng):
    b = Buf(0.4)
    b.add(bubble(1150, 0.030, 0.6, 0.2, harm2=0.10), 0.0, 1.0)
    b.add(impact(rng, 0.004, 1000, 5000), 0.0, 0.12)
    b.add(bubble(1550, 0.024, 0.5, 0.16, harm2=0.10), 0.115, 0.75)
    b.add(impact(rng, 0.004, 1200, 5000), 0.115, 0.09)
    return b.x


def s_water_splash(rng):
    b = Buf(0.34)
    n = n_of(0.16)
    b.add(bp(rng.standard_normal(n), 700, 7000, 2) * decay_env(n, 0.03, 0.0008), 0.0, 0.55)
    # past "gup": chastota tushuvchi sinus
    nl = n_of(0.09)
    tl = axis(nl)
    low = np.sin(2 * np.pi * np.cumsum(280.0 - 130.0 * tl / 0.09) / SR) * decay_env(nl, 0.03, 0.001)
    b.add(low, 0.0, 0.5)
    # pufakchalar: "plop-plop"
    onsets = [0.012, 0.035, 0.060, 0.092, 0.130]
    amps = [0.50, 0.42, 0.32, 0.24, 0.16]
    for at, a in zip(onsets, amps):
        f0 = float(rng.uniform(750, 2600))
        tau = float(rng.uniform(0.010, 0.026))
        b.add(bubble(f0, tau, float(rng.uniform(0.4, 0.9)), tau * 6.0), at, a)
    return b.x


def s_water_ripple(rng):
    dur = 0.46
    n = n_of(dur)
    b = Buf(dur)
    bed = bp(pink(rng, n), 450, 2400, 2) * swell(n, 0.0, 1.0, 2.0)
    trem = 1.0 + 0.35 * np.sin(2 * np.pi * 13.0 * axis(n) + 1.0)
    b.add(bed * trem, 0.0, 0.30)
    for at, f0, a in [(0.04, 880, 0.55), (0.14, 1180, 0.40), (0.25, 1020, 0.32)]:
        b.add(bubble(f0, 0.03, 0.55, 0.16, harm2=0.08), at, a)
    return b.x


def s_water_brook(rng):
    dur = 0.55
    n = n_of(dur)
    b = Buf(dur)
    bed = bp(pink(rng, n), 700, 4800, 2) * fade_env(n, 0.07, 0.15)
    b.add(bed, 0.0, 0.14)
    onsets = np.sort(rng.uniform(0.0, dur - 0.14, 18))
    for at in onsets:
        f0 = float(np.exp(rng.uniform(np.log(600), np.log(2900))))
        tau = float(rng.uniform(0.008, 0.02))
        a = float(rng.uniform(0.15, 0.5))
        b.add(bubble(f0, tau, float(rng.uniform(0.5, 1.2)), tau * 6.0), float(at), a)
    b.x[: n] *= fade_env(n, 0.04, 0.16)
    return b.x


def s_water_wave(rng):
    """To'lqin: avval past "gumburlash", keyin o'rta chastotalar, oxirida ko'pik shitirlashi. Pushti shovqin asosida (o'tkir emas)."""
    dur = 0.8
    n = n_of(dur)
    w = pink(rng, n)
    low = bp(w, 110, 450, 3) * swell(n, 0.0, 0.9, 2.0)
    mid = bp(w, 450, 1700, 2) * swell(n, 0.08, 0.93, 2.0)
    high = bp(w, 1700, 4800, 2) * swell(n, 0.30, 0.97, 3.0)
    y = 1.0 * low + 0.9 * mid + 0.55 * high
    b = Buf(dur)
    b.add(y * fade_env(n, 0.02, 0.15), 0.0, 1.0)
    # ko'pik: to'lqin qaytayotganda mayda pufakchalar
    for at in np.sort(rng.uniform(0.38, 0.70, 7)):
        f0 = float(np.exp(rng.uniform(np.log(1500), np.log(3600))))
        tau = float(rng.uniform(0.006, 0.012))
        b.add(bubble(f0, tau, float(rng.uniform(0.3, 0.7)), tau * 6.0), float(at), 0.10)
    return b.x


def rain_drop(rng, f):
    """Bitta yomg'ir tomchisi qattiq sirtga tushganda: qisqa "tink"."""
    y = modes([f, f * 1.62], [0.0050, 0.0030], [1.0, 0.35], 0.035)
    y = y + 0.22 * np.concatenate([impact(rng, 0.0025, 2000, 8000), np.zeros(len(y))])[: len(y)]
    return y


def s_rain_tap(rng):
    return rain_drop(rng, 3000.0)


def s_rain_leaves(rng):
    dur = 0.34
    b = Buf(dur)
    onsets = [0.0] + sorted(float(v) for v in rng.uniform(0.02, 0.28, 7))
    for at in onsets:
        b.add(rain_drop(rng, float(rng.uniform(2200, 4600))), at, float(rng.uniform(0.35, 1.0)))
    n = n_of(dur)
    b.add(bp(pink(rng, n), 1200, 6000, 1) * fade_env(n, 0.03, 0.1), 0.0, 0.07)
    return b.x


def s_rain_shower(rng):
    dur = 0.62
    n = n_of(dur)
    b = Buf(dur)
    env = fade_env(n, 0.12, 0.30)
    am = 1.0 + 0.30 * slow_noise(rng, n, 25)
    bed = bp(pink(rng, n), 600, 7000, 2) * np.clip(am, 0.2, None) * env
    b.add(bed, 0.0, 0.30)
    for at in np.sort(rng.uniform(0.02, dur - 0.1, 30)):
        g = float(rng.uniform(0.2, 0.7)) * float(env[min(n - 1, n_of(float(at)))])
        b.add(rain_drop(rng, float(rng.uniform(2200, 5000))), float(at), g)
    return b.x


def s_bird_tweet(rng):
    b = Buf(0.28)
    b.add(syl(2500, 3500, 0.060, harm=(1.0, 0.06)), 0.000, 0.8)
    b.add(syl(2900, 3800, 0.075, vib_hz=55, vib_depth=110, harm=(1.0, 0.06)), 0.085, 1.0)
    b.add(syl(2700, 3300, 0.050, harm=(1.0, 0.06)), 0.185, 0.55)
    return b.x


def s_bird_trill(rng):
    pulses = 8
    b = Buf(0.4)
    for i in range(pulses):
        amp = np.sin(np.pi * (i + 0.5) / pulses) ** 1.2
        f0 = 2300 + 50 * i + float(rng.uniform(-30, 30))
        b.add(syl(f0, f0 + 700, 0.028, harm=(1.0, 0.06)), i * 0.040, float(amp))
    return b.x


def coo(f0, f1, dur):
    n = n_of(dur)
    t = axis(n)
    f = f0 + (f1 - f0) * t / dur
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.1 * np.sin(4 * ph)
    return x * fade_env(n, 0.03, 0.05)


def s_bird_dove(rng):
    b = Buf(0.5)
    b.add(coo(440, 470, 0.07), 0.0, 0.55)
    b.add(coo(480, 520, 0.12), 0.095, 1.0)
    b.add(coo(500, 430, 0.20), 0.24, 0.85)
    return lp(b.x, 1800, 2)


def s_cricket(rng):
    b = Buf(0.32)
    for k in range(3):
        base = k * 0.095
        for p in range(4):
            n = n_of(0.009)
            x = np.sin(2 * np.pi * 3900 * axis(n)) * np.hanning(n)
            b.add(x, base + p * 0.019, 0.7 + 0.1 * p)
    return b.x


def s_leaf_rustle(rng):
    dur = 0.22
    n = n_of(dur)
    w = bp(pink(rng, n), 1500, 8000, 2)
    gate = np.clip(slow_noise(rng, n, 140) * 1.0 + 0.3, 0.0, None)
    env = fade_env(n, 0.006, 0.12) * np.exp(-axis(n) / 0.10)
    return w * gate * env


def s_wind_breeze(rng):
    dur = 0.55
    n = n_of(dur)
    w = pink(rng, n)
    y = (
        bp(w, 200, 700, 2) * swell(n, 0.0, 0.7, 2.0)
        + 1.2 * bp(w, 500, 1400, 2) * swell(n, 0.15, 0.85, 2.0)
        + 1.0 * bp(w, 900, 2400, 2) * swell(n, 0.30, 1.0, 2.0)
    )
    return y


def s_bamboo_tap(rng):
    b = Buf(0.32)
    b.add(modes([700, 700 * 2.54, 700 * 4.6, 700 * 6.9], [0.085, 0.035, 0.016, 0.008], [1.0, 0.5, 0.25, 0.1], 0.32))
    b.add(impact(rng, 0.003, 600, 4000), 0.0, 0.35)
    return b.x


def s_wood_block(rng):
    b = Buf(0.12)
    b.add(modes([1050, 1050 * 2.1, 1050 * 3.6], [0.022, 0.012, 0.006], [1.0, 0.45, 0.2], 0.12))
    b.add(impact(rng, 0.002, 800, 5000), 0.0, 0.25)
    return b.x


def s_pebble(rng):
    b = Buf(0.08)
    b.add(modes([1700, 2900, 430], [0.007, 0.004, 0.010], [0.6, 0.3, 0.25], 0.08))
    b.add(impact(rng, 0.0015, 1500, 8000), 0.0, 0.40)
    return b.x


def chime(f0, dur):
    """Shamol qo'ng'irog'i: metall naycha qismlari (1 : 2,756 : 5,404 : 8,933), biroz farqli ikkinchi nusxa "titrash" beradi."""
    ratios = [1.0, 2.756, 5.404, 8.933]
    taus = [0.30, 0.13, 0.06, 0.03]
    amps = [1.0, 0.33, 0.14, 0.05]
    a = modes([f0 * r for r in ratios], taus, amps, dur, attack=0.0008)
    c = modes([f0 * r * 1.0035 for r in ratios], taus, amps, dur, attack=0.0008)
    return a + 0.5 * c


def s_chime_wind(rng):
    b = Buf(0.9)
    b.add(chime(1318.5, 0.70), 0.0, 0.8)
    b.add(chime(987.8, 0.62), 0.12, 0.6)
    return reverb(b.x, rng, wet=0.18, decay=0.30)


def s_bowl_soft(rng):
    """Kosa: asosiy ohang va ikkita "uchlanish" beruvchi juft chastota."""
    f0 = 523.0
    ratios = [1.0, 2.71, 5.12]
    taus = [0.40, 0.20, 0.10]
    amps = [1.0, 0.4, 0.12]
    freqs = []
    fa = []
    ta = []
    for r, tau, a in zip(ratios, taus, amps):
        freqs += [f0 * r, f0 * r + 0.7]
        ta += [tau, tau]
        fa += [a, a * 0.9]
    return modes(freqs, ta, fa, 1.0, attack=0.015)


# id -> (yaratuvchi, sinf). Sinflar: "kls" (tik ohangi, qayta o'lchanmaydi), "tick", "cue", "long"
CATALOG = [
    ("tone_tik", s_tone_tik, "kls"),
    ("tone_tuk", s_tone_tuk, "kls"),
    ("tone_edge", s_tone_edge, "kls"),
    ("tone_window", s_tone_window, "kls"),
    ("tone_scroll", s_tone_scroll, "cue"),
    ("tone_error", s_tone_error, "cue"),
    ("drop_tiny", s_drop_tiny, "tick"),
    ("drop_water", s_drop_water, "cue"),
    ("drop_deep", s_drop_deep, "cue"),
    ("drop_pair", s_drop_pair, "cue"),
    ("water_splash", s_water_splash, "cue"),
    ("water_ripple", s_water_ripple, "long"),
    ("water_brook", s_water_brook, "long"),
    ("water_wave", s_water_wave, "long"),
    ("rain_tap", s_rain_tap, "tick"),
    ("rain_leaves", s_rain_leaves, "cue"),
    ("rain_shower", s_rain_shower, "long"),
    ("bird_tweet", s_bird_tweet, "long"),
    ("bird_trill", s_bird_trill, "long"),
    ("bird_dove", s_bird_dove, "long"),
    ("cricket", s_cricket, "cue"),
    ("leaf_rustle", s_leaf_rustle, "cue"),
    ("wind_breeze", s_wind_breeze, "long"),
    ("bamboo_tap", s_bamboo_tap, "cue"),
    ("wood_block", s_wood_block, "tick"),
    ("pebble", s_pebble, "tick"),
    ("chime_wind", s_chime_wind, "long"),
    ("bowl_soft", s_bowl_soft, "long"),
]

# "tik" ohangiga nisbatan nishon balandligi (dB): tik 0 dB, qolgan sinflar biroz baland
CLASS_OFFSET_DB = {"tick": 0.0, "cue": 2.0, "long": 3.0}
CLASSIC_PEAK = 0.46  # eski (v31) tik amplitudasi 0,275 edi; standart balandlik 60% da 0,46*0,6 = 0,276
PEAK_MAX = 0.88      # undan yuqori cho'qqilar yumshoq cheklanadi (tanh), qirqilmaydi


# ------------------------------------------------------------------------------------------------------------------ o'lchov

def a_weight_db(f):
    f = np.maximum(f, 1.0)
    f2 = f * f
    ra = (12194.0 ** 2 * f2 * f2) / (
        (f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2)
    )
    return 20 * np.log10(ra) + 2.0


def a_weighted(x):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.fft.irfft(spec * (10 ** (a_weight_db(f) / 20.0)), len(x))


def loudness_db(x):
    """Qisqa muddatli balandlik: A-vaznli signalning 250 ms oynadagi eng katta o'rtacha kvadrati (dB, to'liq shkalaga nisbatan)."""
    xa = a_weighted(np.concatenate([x, np.zeros(n_of(0.01))]))
    w = n_of(0.25)
    p = xa ** 2
    c = np.concatenate([[0.0], np.cumsum(p)])
    if len(p) <= w:
        ms = c[-1] / w
    else:
        ms = np.max((c[w:] - c[:-w]) / w)
    return 10 * np.log10(ms + 1e-12)


def centroid_hz(x):
    m = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return float(np.sum(f * m) / (np.sum(m) + 1e-12))


def finish(x, fade_in=0.0003, fade_out=0.006, trim_db=-55.0):
    """Oxiridagi jimlikni kesadi va boshi-oxiriga yumshoq o'tish beradi (bosilish ovozi bo'lmasligi uchun)."""
    x = x - np.mean(x[: max(1, min(len(x), 8))]) * 0.0  # DC ga tegilmaydi; faqat keyin tekshiriladi
    pk = np.max(np.abs(x)) + 1e-12
    thr = pk * 10 ** (trim_db / 20.0)
    idx = np.nonzero(np.abs(x) > thr)[0]
    end = (idx[-1] + 1) if len(idx) else len(x)
    x = x[:end].copy()
    n = len(x)
    fo = min(n // 2, n_of(fade_out))
    fi = min(n // 4, n_of(fade_in))
    if fi > 1:
        x[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
    if fo > 1:
        x[n - fo:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo)
    return x


def write_wav(path, x):
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render_all():
    raw = {}
    for name, fn, cls in CATALOG:
        raw[name] = finish(fn(seeded(name)))
    # mos kelish uchun "tik" ohangi nishon: eski amplituda
    ref = raw["tone_tik"] * (CLASSIC_PEAK / np.max(np.abs(raw["tone_tik"])))
    ref_db = loudness_db(ref)
    out = {}
    for name, fn, cls in CATALOG:
        x = raw[name]
        if cls == "kls":
            y = x * (CLASSIC_PEAK / np.max(np.abs(x)))
        else:
            target = ref_db + CLASS_OFFSET_DB[cls]
            g = 10 ** ((target - loudness_db(x)) / 20.0)
            # Cho'qqisi juda baland (zarbali) tovushda nishon balandlikka yetish uchun cheksiz kuchaytirilmaydi: cho'qqi
            # PEAK_MAX dan ko'pi bilan 3 dB oshishi mumkin va u yumshoq cheklagichdan (tanh) o'tadi. Shunda buzilish kam
            # bo'ladi, bunday tovush nishondan 1-2 dB past qolishi mumkin.
            g = min(g, PEAK_MAX * 1.4 / np.max(np.abs(x)))
            y = x * g
            if np.max(np.abs(y)) > PEAK_MAX:
                y = PEAK_MAX * np.tanh(y / PEAK_MAX)
        out[name] = y
    return out, ref_db


def low_ratio(x, below=80.0):
    """Energiyaning 80 Hz dan pastdagi ulushi (telefon dinamigi bu chastotalarni chiqarmaydi, faqat balandlikdan joy oladi)."""
    m = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return float(np.sum(m[f < below]) / (np.sum(m) + 1e-12))


def report_rows(sounds):
    rows = []
    for name, fn, cls in CATALOG:
        x = sounds[name]
        rows.append(
            (
                name,
                cls,
                1000.0 * len(x) / SR,
                float(np.max(np.abs(x))),
                loudness_db(x),
                centroid_hz(x),
                100.0 * low_ratio(x),
                float(abs(x[0])),
                float(abs(x[-1])),
                float(np.mean(x)),
            )
        )
    return rows


def plot_sheets(sounds, outdir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    names = [c[0] for c in CATALOG]
    per = 16
    for s in range(0, len(names), per):
        chunk = names[s:s + per]
        fig, axes = plt.subplots(4, 4, figsize=(16, 11))
        for ax in axes.ravel():
            ax.axis("off")
        for ax, name in zip(axes.ravel(), chunk):
            x = sounds[name]
            ax.axis("on")
            dither = 1e-6 * np.random.default_rng(1).standard_normal(len(x) + n_of(0.02))  # log10(0) ogohlantirishi bo'lmasligi uchun
            ax.specgram(np.concatenate([x, np.zeros(n_of(0.02))]) + dither, NFFT=512, Fs=SR, noverlap=448, cmap="magma", vmin=-120, vmax=-30)
            ax.set_ylim(0, 10000)
            ax.set_title("%s  %d ms  pk %.2f" % (name, round(1000 * len(x) / SR), np.max(np.abs(x))), fontsize=10)
            ax.tick_params(labelsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "sheet_%d.png" % (s // per + 1)), dpi=70)
        plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "..", "app", "src", "main", "res", "raw"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--plots", default=None)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    sounds, ref_db = render_all()
    if not args.no_write:
        os.makedirs(args.out, exist_ok=True)
        for name, x in sounds.items():
            write_wav(os.path.join(args.out, "snd_%s.wav" % name), x)
        print("yozildi: %d ta fayl -> %s" % (len(sounds), os.path.normpath(args.out)))
    if args.report:
        print("nishon (tik) balandligi: %.1f dB" % ref_db)
        print("%-13s %-5s %7s %6s %8s %8s %6s %8s %7s %9s" % ("id", "sinf", "ms", "pik", "dB(A)", "markaz", "<80Hz%", "birinchi", "oxirgi", "o'rtacha"))
        total = 0
        for r in report_rows(sounds):
            total += int(r[2] / 1000.0 * SR * 2)
            print("%-13s %-5s %7.0f %6.2f %8.1f %8.0f %6.2f %8.4f %7.4f %9.5f" % r)
        print("jami hajm: %.0f KB" % (total / 1024.0))
    if args.plots:
        plot_sheets(sounds, args.plots)
        print("rasmlar:", args.plots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
