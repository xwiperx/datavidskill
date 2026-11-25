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
        p = smoothstep((t - 0.5) / 9.8)
        e = (1 - p) ** 2
        return cam_state(0, rise=27 * e, back=72 * e, side=0, tilt=3.0 * e, fov=39)
    if t > T_COUNT_END:
        p = smoothstep((t - T_COUNT_END) / 8.0)
        return cam_state(u, rise=-1.8 * p, back=4.0 * p, side=0, tilt=-0.8 * p)
    return cam_state(u, side=0)


def draw_youtube_mark(d, cx, cy, width=64, alpha=255):
    """Simple red rounded play mark used beside the channel name."""
    w=float(width); h=w*0.69
    x0,y0=cx-w/2,cy-h/2
    d.rounded_rectangle([x0,y0,x0+w,y0+h],radius=h*0.24,fill=(255,0,0,int(alpha)))
    d.polygon([(cx-w*0.10,cy-h*0.23),(cx-w*0.10,cy+h*0.23),(cx+w*0.29,cy)],
              fill=(255,255,255,int(alpha)))
def draw_title(im, t):
    """Cinematic opening: kinetic numeric motif, editorial title, portrait teaser."""
    d = ImageDraw.Draw(im, 'RGBA')
    # Keep the title lockup clear: no decorative words or numerals behind text.
    d = ImageDraw.Draw(im, 'RGBA')
    # Sweeping circular reticle and tick marks establish a documentary/data tone.
    ring_a = int(115 * clamp(t/0.8, 0, 1) * clamp((7.6-t)/1.0, 0, 1))
    if ring_a > 0:
        cx, cy = W/2, 438
        rr = 294 + 10*math.sin(t*1.1)
        d.arc([cx-rr, cy-rr, cx+rr, cy+rr], start=204 + t*10, end=336 + t*10,
              fill=(90, 172, 228, ring_a), width=2)
        d.arc([cx-rr-16, cy-rr-16, cx+rr+16, cy+rr+16], start=30-t*8, end=95-t*8,
              fill=(255, 194, 88, int(ring_a*0.82)), width=2)
        for j in range(61):
            ang = (j/60.0)*math.tau - math.pi/2 + t*0.12
            r0, r1 = rr + (8 if j % 5 == 0 else 13), rr + 19
            x0, y0 = cx+math.cos(ang)*r0, cy+math.sin(ang)*r0
            x1, y1 = cx+math.cos(ang)*r1, cy+math.sin(ang)*r1
            d.line([(x0,y0),(x1,y1)], fill=(152,190,226,int(ring_a*(0.8 if j%5==0 else 0.35))), width=2 if j%5==0 else 1)
    # Thin gold sweep moves across the image as the title resolves.
    if 0.25 < t < 7.5:
        p = ease_out(clamp((t-0.25)/1.4,0,1))
        half = 640*p
        yline = 302 + 5*math.sin(t*1.2)
        a = int(210*clamp((7.5-t)/0.8,0,1))
        d.line([(W/2-half,yline),(W/2+half,yline)], fill=(255,194,88,a), width=2)
        d.ellipse([W/2+half-4,yline-4,W/2+half+4,yline+4], fill=(255,238,192,a))
    # Main title rises into its editorial lockup.
    if 0.55 < t < 7.5:
        a = int(255*clamp((t-0.55)/0.8,0,1)*clamp((7.35-t)/0.8,0,1))
        slide = 42*(1-ease_out(clamp((t-0.55)/1.2,0,1)))
        kicker = CFG.get('title_top', "THE WORLD'S")
        fk = font(I_SEMI, 19)
        draw_ls(d,(W/2-tw(d,kicker,fk,6)/2,326+slide),kicker,fk,(200,215,235),6,alpha=a)
        title = CFG.get('title_big','RICHEST')
        ft = font(BEBAS,194)
        while tw(d,title,ft,5)>W-300 and ft.size>66:
            ft=font(BEBAS,ft.size-8)
        draw_ls(d,(W/2-tw(d,title,ft,5)/2,348+slide),title,ft,(246,249,255),5,alpha=a)
        sub = str(CFG.get('title_sub','')).strip()
        if sub:
            fs = font(I_MED,17)
            while tw(d,sub,fs,3.5)>W-360 and fs.size>10:
                fs=font(I_MED,fs.size-1)
            draw_ls(d,(W/2-tw(d,sub,fs,3.5)/2,568),sub,fs,(152,172,196),3.5,alpha=int(a*0.88))
    # Channel wordmark and YouTube play mark are the hero signature beneath RICHEST.
    if 1.3 < t < 7.6:
        ba=int(255*clamp((t-1.3)/0.65,0,1)*clamp((7.6-t)/0.6,0,1))
        brand=CFG.get('brand','DATA ZED')
        fb=font(I_BLACK,42)
        textw=tw(d,brand,fb,3.2)
        markw=62
        gap=22
        left=W/2-(textw+gap+markw)/2
        draw_ls(d,(left,550),brand,fb,(245,248,255),3.2,alpha=ba)
        draw_youtube_mark(d,left+textw+gap+markw/2,572,markw,ba)
    # Four rounded portrait windows briefly preview the range of the countdown.
    if 2.7 < t < 7.1:
        from PIL import ImageOps
        alpha = int(225*clamp((t-2.7)/0.65,0,1)*clamp((7.1-t)/0.55,0,1))
        ids = [max(0,N-1), max(0,int(N*0.74)), max(0,int(N*0.49)), 0]
        card_w, card_h = 146, 122
        gap = 24
        previews = [(idx, E.item_image(idx)) for idx in ids]
        previews = [(idx, imsrc) for idx, imsrc in previews if imsrc is not None]
        x0 = W/2 - (len(previews)*card_w+max(0,len(previews)-1)*gap)/2
        for k, (idx, imsrc) in enumerate(previews):
            label = f'#{idx+1:02d}'
            x = int(x0+k*(card_w+gap))
            pane = ImageOps.fit(imsrc,(card_w,card_h),method=Image.Resampling.LANCZOS,centering=(0.5,0.34)).convert('RGBA')
            mask = Image.new('L',pane.size,0)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,card_w-1,card_h-1),radius=16,fill=alpha)
            pane.putalpha(mask)
            im.paste(pane,(x,655),pane)
            d.rounded_rectangle([x,655,x+card_w,655+card_h],radius=16,outline=(255,255,255,int(alpha*0.62)),width=2)
            d.rounded_rectangle([x+7,663,x+52,690],radius=9,fill=(4,8,15,int(alpha*0.82)))
            draw_ls(d,(x+16,667),label,font(BEBAS,20),(255,205,110),0,alpha=alpha)
    # Source lower third settles before the first rank appears.
    if 7.15 < t < 12.1:
        a = int(255*clamp((t-7.15)/0.75,0,1)*clamp((12.05-t)/0.65,0,1))
        d.rounded_rectangle([94,850,98,958],radius=2,fill=(255,194,88,a))
        draw_ls(d,(122,858),CFG.get('lower_kicker',f'RANKED #1 TO #{N}'),font(I_SEMI,17),(255,194,88),3.6,alpha=a)
        draw_ls(d,(122,890),CFG.get('lower_mid','BY ESTIMATED NET WORTH'),font(I_MED,16),(205,218,236),3.0,alpha=a)
        draw_ls(d,(122,922),CFG.get('source_line',''),font(I_REG,14),(126,142,164),2.4,alpha=int(a*0.9))
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
    brand = CFG.get('brand', "DATA ZED")
    fb = font(I_BOLD, 40)
    bw=tw(d,brand,fb,5); markw=62; gap=22
    left=W/2-(bw+gap+markw)/2
    draw_ls(d,(left,678),brand,fb,(238,244,255),5,alpha=int(a*0.98))
    draw_youtube_mark(d,left+bw+gap+markw/2,703,markw,int(a*0.98))


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
        # A single rounded hero-column rises in the opening; the montage hints at
        # the range without prematurely revealing the count.
        for vz, i in reversed(order):
            if i != 0:
                continue
            rv = smoothstep((t - 1.1) / 5.8)
            if rv > 0.002:
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
        idx = int(clamp(int(u) + 1, 1, N))
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
