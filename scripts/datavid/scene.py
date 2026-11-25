import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import engine as E
import hud as Hd
from engine import (W, H, FPS, PEOPLE, HEIGHTS, H_MIN, font, tw, draw_ls, mix, clamp, lerp,
                    smoothstep, ease_out, BEBAS, I_BLACK, I_BOLD, I_SEMI, I_MED, I_REG, I_LIGHT,
                    GOLD, WHITE, MUTED, tier_color, cam_state, bar_base, CFG, N, DUR, NF,
                    TOTAL, SECOND, MAXW, T_INTRO, T_COUNT_END, T_FINALE_END, T_ENDCARD, PER_BAR)

_rng = np.random.default_rng(11)
_GRAIN = [_rng.normal(0, 3.0, (H, W, 1)).astype(np.float32) for _ in range(6)]


def u_of_t(t):
    if t <= T_INTRO:
        return 0.0
    tt = (t - T_INTRO) / PER_BAR
    if tt >= N:
        return float(N - 1)
    i = math.floor(tt)
    s = tt - i
    s2 = smoothstep((s - 0.10) / 0.78)
    return min(float(N - 1), i + s2)


def reveal_of(t, i):
    return smoothstep((t - (6.0 + i * 0.016)) / 1.05)


def scene_cam(t, u):
    if t < T_INTRO:
        p = smoothstep((t - 2.8) / 8.6)
        e = (1 - p) ** 2
        return cam_state(0, rise=52 * e, back=105 * e, side=18 * e, tilt=6 * e, fov=37 + 6 * e)
    if t > T_COUNT_END:
        p = smoothstep((t - T_COUNT_END) / 8.0)
        return cam_state(u, rise=-2.6 * p, back=7.0 * p, tilt=-1.8 * p)
    return cam_state(u)


def draw_title(im, t):
    """Intro typography."""
    d = ImageDraw.Draw(im, 'RGBA')
    p0 = clamp(t / 0.9, 0, 1)
    if 0.15 < t < 7.0:
        wdt = 520 * ease_out(p0)
        cy = 300
        a = int(255 * clamp((7.0 - t) / 0.8, 0, 1))
        d.line([(W / 2 - wdt, cy), (W / 2 + wdt, cy)], fill=(255, 194, 88, a), width=2)
    if 0.6 < t < 7.4:
        a1 = int(255 * clamp((t - 0.6) / 0.8, 0, 1) * clamp((7.1 - t) / 0.9, 0, 1))
        off = 26 * (1 - ease_out(clamp((t - 0.6) / 1.1, 0, 1)))
        s1 = CFG.get('title_top', "THE  WORLD'S")
        f1 = font(BEBAS, 74)
        while tw(d, s1, f1, 14) > W - 320 and f1.size > 30:
            f1 = font(BEBAS, f1.size - 4)
        x1 = W / 2 - tw(d, s1, f1, 14) / 2
        draw_ls(d, (x1, 330 + off), s1, f1, (176, 192, 214), 14, alpha=a1)
        s2 = CFG.get('title_big', "RICHEST")
        f2 = font(BEBAS, 196)
        while tw(d, s2, f2, 6) > W - 260 and f2.size > 60:
            f2 = font(BEBAS, f2.size - 8)
        x2 = W / 2 - tw(d, s2, f2, 6) / 2
        draw_ls(d, (x2, 396 + off), s2, f2, (244, 248, 255), 6, alpha=a1)
    if 2.0 < t < 7.2:
        a2 = int(255 * clamp((t - 2.0) / 0.9, 0, 1) * clamp((6.9 - t) / 0.9, 0, 1))
        s3 = CFG.get('title_sub', "")
        f3 = font(I_SEMI, 20)
        while tw(d, s3, f3, 5.2) > W - 360 and f3.size > 11:
            f3 = font(I_SEMI, f3.size - 1)
        x3 = W / 2 - tw(d, s3, f3, 5.2) / 2
        draw_ls(d, (x3, 636), s3, f3, (150, 166, 188), 5.2, alpha=a2)
    # lower third during city rise
    if 7.2 < t < 12.2:
        a3 = int(255 * clamp((t - 7.2) / 0.8, 0, 1) * clamp((12.1 - t) / 0.7, 0, 1))
        d.rectangle([96, 862, 100, 942], fill=(255, 194, 88, a3))
        draw_ls(d, (122, 866), CFG.get('lower_kicker', f"RANKED #1 TO #{N}"), font(I_SEMI, 17),
                (255, 194, 88), 3.6, alpha=a3)
        draw_ls(d, (122, 896), CFG.get('lower_mid', "BY ESTIMATED NET WORTH"), font(I_MED, 17),
                (198, 210, 226), 3.0, alpha=a3)
        draw_ls(d, (122, 926), CFG.get('source_line', ""), font(I_REG, 15), (126, 142, 164), 2.4,
                alpha=int(a3 * 0.9))


def draw_finale(im, t, u):
    d = ImageDraw.Draw(im, 'RGBA')
    p = clamp((t - T_COUNT_END - 0.9) / 1.4, 0, 1)
    if p <= 0:
        return
    a = int(255 * p)
    X = 1090
    top = PEOPLE[-1]
    d.rectangle([X, 236, X + 44, 240], fill=(255, 194, 88, a))
    draw_ls(d, (X, 260), CFG.get('finale_kicker', "WORLD  #1"), font(I_SEMI, 17), (255, 194, 88), 4.4,
            alpha=a)
    lines = CFG.get('finale_lines', ["THE RICHEST", "PERSON", "ON EARTH"])
    f = font(BEBAS, 108)
    widest = max(lines, key=lambda s: tw(d, s, f, 2.0))
    while tw(d, widest, f, 2.0) > 630 and f.size > 54:
        f = font(BEBAS, f.size - 4)
    lh = f.size * 0.93
    for i, line in enumerate(lines):
        aa = int(255 * clamp((t - T_COUNT_END - 0.9 - i * 0.12) / 1.2, 0, 1))
        draw_ls(d, (X - 4, 296 + i * lh), line, f, (244, 248, 255), 2.0, alpha=aa)
    p2 = clamp((t - T_COUNT_END - 2.4) / 1.3, 0, 1)
    if p2 > 0:
        a2 = int(255 * p2)
        d.line([(X, 640), (X + 620, 640)], fill=(255, 255, 255, int(a2 * 0.20)), width=1)
        draw_ls(d, (X, 664), top['name'].upper(), font(I_BOLD, 34), (236, 242, 255), 1.2, alpha=a2)
        draw_ls(d, (X, 712), Hd.fmt_money_long(top['worth']), font(BEBAS, 86), (255, 194, 88), 1.4,
                alpha=a2)
        meta = top['source'] or top['industry']
        draw_ls(d, (X, 812), meta, font(I_MED, 17), (140, 156, 178), 2.6, alpha=int(a2 * 0.95))
    p3 = clamp((t - T_COUNT_END - 3.8) / 1.3, 0, 1)
    if p3 > 0:
        a3 = int(255 * p3)
        stats = CFG.get('finale_stats') or [
            [f"{top['worth'] / max(SECOND, 1e-6):.1f}x", "THE NEXT PERSON"],
            [Hd.fmt_money(TOTAL), f"ALL {N} COMBINED"],
        ]
        for i, (val, lab) in enumerate(stats[:2]):
            draw_ls(d, (X + i * 300, 878), val, font(BEBAS, 46), (255, 194, 88), 1.2, alpha=a3)
            draw_ls(d, (X + i * 300, 930), lab, font(I_SEMI, 12), (126, 142, 164), 2.6,
                    alpha=int(a3 * 0.9))


def draw_endcard(im, t):
    p = clamp((t - T_ENDCARD - 0.2) / 1.2, 0, 1)
    if p <= 0:
        return
    d = ImageDraw.Draw(im, 'RGBA')
    a = int(255 * p)
    n = len(PEOPLE)
    total_w = 1080
    x0 = W / 2 - total_w / 2
    base_y = 792
    max_h = 168
    for i, pp in enumerate(PEOPLE):
        bx = x0 + total_w * i / n
        bw = total_w / n + 0.6
        hh = 8 + max_h * (HEIGHTS[i] - H_MIN) / (max(HEIGHTS) - H_MIN)
        col = tier_color(pp['worth'])
        d.rectangle([bx, base_y - hh, bx + bw, base_y], fill=col + (int(a * 0.92),))
    d.line([(x0, base_y + 1), (x0 + total_w, base_y + 1)], fill=(255, 255, 255, int(a * 0.22)), width=1)
    f5 = font(I_MED, 13)
    draw_ls(d, (x0, base_y + 13), "01", f5, (118, 134, 156), 2.0, alpha=int(a * 0.8))
    s6 = str(n)
    draw_ls(d, (x0 + total_w - tw(d, s6, f5, 2.0), base_y + 13), s6, f5, (255, 194, 88), 2.0,
            alpha=int(a * 0.9))
    s1 = CFG.get('end_title', f"{n} ENTRIES")
    f = font(BEBAS, 56)
    while tw(d, s1, f, 7) > W - 300 and f.size > 24:
        f = font(BEBAS, f.size - 2)
    draw_ls(d, (W / 2 - tw(d, s1, f, 7) / 2, 300), s1, f, (222, 232, 246), 7, alpha=a)
    s2 = CFG.get('end_total') or (Hd.fmt_money_long(TOTAL) if TOTAL < 1000 else
                                  f"{CFG.get('value_prefix', '$')}{TOTAL / 1000:.2f} TRILLION")
    f2 = font(BEBAS, 150)
    while tw(d, s2, f2, 3) > W - 300 and f2.size > 60:
        f2 = font(BEBAS, f2.size - 6)
    draw_ls(d, (W / 2 - tw(d, s2, f2, 3) / 2, 356), s2, f2, (255, 194, 88), 3, alpha=a)
    f3 = font(I_SEMI, 17)
    s3 = CFG.get('end_caption', "COMBINED VALUE")
    draw_ls(d, (W / 2 - tw(d, s3, f3, 5.0) / 2, 528), s3, f3, (136, 152, 174), 5.0, alpha=a)
    d.line([(W / 2 - 90, 592), (W / 2 + 90, 592)], fill=(255, 255, 255, int(a * 0.22)), width=1)
    f4 = font(I_MED, 14)
    s4 = CFG.get('source_note', CFG.get('source_line', ""))
    draw_ls(d, (W / 2 - tw(d, s4, f4, 2.8) / 2, 620), s4, f4, (112, 128, 150), 2.8, alpha=int(a * 0.95))
    s5 = CFG.get('credit', "EVERY FRAME GENERATED IN CODE")
    draw_ls(d, (W / 2 - tw(d, s5, f4, 2.8) / 2, 648), s5, f4, (92, 106, 126), 2.8, alpha=int(a * 0.85))


def bloom(arr, strength=0.85, thresh=0.30):
    f = arr.astype(np.float32) / 255.0
    lum = f.max(axis=2, keepdims=True)
    bright = f * np.clip((lum - thresh) / (1 - thresh + 1e-4), 0, 1)
    small = bright.reshape(arr.shape[0] // 4, 4, arr.shape[1] // 4, 4, 3).mean(axis=(1, 3))
    im = Image.fromarray((np.clip(small, 0, 1) * 255).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(6))
    im = im.filter(ImageFilter.GaussianBlur(6))
    up = np.array(im.resize((arr.shape[1], arr.shape[0]), Image.BILINEAR), np.float32) / 255.0
    out = f + up * strength
    return np.clip(out, 0, 1)


def render(t, fi=0):
    if t >= T_ENDCARD:
        return render_end(t)
    u = u_of_t(t)
    cam = scene_cam(t, u)
    far = cam.pos + np.array([cam.fwd[0], 0, cam.fwd[2]]) * 8000
    hy = float(cam.project(np.array([far]))[0][1])
    bg = E.background(cam, hy)
    im = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), 'RGB')
    E.draw_floor(im, cam, u)

    order = []
    for i in range(len(PEOPLE)):
        vz = cam.view([bar_base(i)])[0][2]
        if vz < 9.5 or vz > 190:
            continue
        order.append((vz, i))
    order.sort(reverse=True)

    em = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    E.draw_ground_fx(im, em, cam, u, order)

    if t < T_INTRO:
        for vz, i in reversed(order):
            rv = reveal_of(t, i)
            if rv <= 0.002:
                continue
            E.draw_one_bar(im, em, cam, i, HEIGHTS[i] * rv, u, vz)
    else:
        E.draw_bars(im, cam, u, em, order)

    im.paste(em, (0, 0), em)
    arr = np.array(im.convert('RGB'), np.float32) * E.vignette()

    sf = 1.0
    if t < 8.0:
        sf = 0.10 + 0.90 * smoothstep((t - 4.4) / 2.5)
    arr = arr * sf
    arr = bloom(arr) * 255.0

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB')

    # ---- typography on top of the graded scene
    if t < T_INTRO:
        a = int(255 * clamp((t - 8.4) / 1.0, 0, 1))
        if a > 0:
            Hd.draw_topbar(out, PEOPLE[0], 1, alpha=a, total=N)
    elif t < T_COUNT_END:
        idx = int(clamp(int(round(u)) + 1, 1, N))
        p = PEOPLE[idx - 1]
        appear = clamp((t - T_INTRO) / 0.7, 0, 1)
        Hd.draw_topbar(out, p, idx, alpha=int(255 * appear), total=N)
        Hd.draw_card(out, p, alpha=255, appear=appear)
        Hd.draw_scale(out, p['worth'], alpha=int(235 * appear))
        Hd.draw_progress(out, (idx - 1) / max(1, N - 1), tier_color(p['worth']), alpha=int(220 * appear))
        Hd.draw_plate(out, cam, p, idx, alpha=int(255 * appear), scale=1.0)
    else:
        p = PEOPLE[-1]
        Hd.draw_topbar(out, p, N, alpha=255, total=N)
        Hd.draw_card(out, p, alpha=255, appear=clamp(1 - (t - T_COUNT_END) / 1.0, 0, 1))
        pr = int(220 * (1 - clamp((t - T_FINALE_END) / 1.0, 0, 1)))
        Hd.draw_progress(out, 1.0, tier_color(p['worth']), alpha=pr)

    draw_title(out, t)
    if t >= T_COUNT_END:
        draw_finale(out, t, u)

    a = np.array(out, np.float32)
    a = a + _GRAIN[fi % len(_GRAIN)] * 0.8
    a = np.clip(a, 0, 255)
    if t > T_ENDCARD - 2.2:
        k = clamp((t - (T_ENDCARD - 2.2)) / 2.0, 0, 1)
        a = a * (1 - k)
    return a.astype(np.uint8)


def render_end(t):
    im = Image.new('RGB', (W, H), (2, 3, 7))
    # soft radial glow behind
    g = Image.new('RGB', (W, H), (2, 3, 7))
    dd = ImageDraw.Draw(g, 'RGBA')
    dd.ellipse([W / 2 - 700, 420 - 420, W / 2 + 700, 420 + 420], fill=(16, 34, 58, 90))
    g = g.filter(ImageFilter.GaussianBlur(160))
    im = g
    draw_endcard(im, t)
    a = np.array(im, np.float32)
    a = a + _GRAIN[0] * 0.8
    a = np.clip(a, 0, 255)
    if t > 178.4:
        a = a * (1.0 - clamp((t - 178.4) / 1.45, 0, 1))
    return a.astype(np.uint8)
